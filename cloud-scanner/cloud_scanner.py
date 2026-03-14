#!/usr/bin/env python3
"""
Cloud Security Misconfiguration Scanner
AWS CIS Foundations Benchmark v1.4 compliance checker
"""

import argparse
import json
import os
import sys
import datetime
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False

# ─── Colour helpers ─────────────────────────────────────────────────────────

def clr(text, color):
    if not COLORAMA_AVAILABLE:
        return text
    colors = {
        "red": Fore.RED, "green": Fore.GREEN, "yellow": Fore.YELLOW,
        "blue": Fore.BLUE, "cyan": Fore.CYAN, "white": Fore.WHITE,
        "bright": Style.BRIGHT,
    }
    return colors.get(color, "") + str(text) + Style.RESET_ALL


def severity_color(severity):
    mapping = {"Critical": "red", "High": "red", "Medium": "yellow", "Low": "cyan"}
    return mapping.get(severity, "white")


def result_color(result):
    mapping = {"PASS": "green", "FAIL": "red", "WARN": "yellow", "ERROR": "yellow"}
    return mapping.get(result, "white")

# ─── Finding builder ─────────────────────────────────────────────────────────

def finding(check, resource, result, severity, cis_control, description, remediation):
    return {
        "check": check,
        "resource": resource,
        "result": result,
        "severity": severity,
        "cis_control": cis_control,
        "description": description,
        "remediation": remediation,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

# ─── IAM Checks ──────────────────────────────────────────────────────────────

class IAMAuditor:
    def __init__(self, session):
        self.iam = session.client("iam")
        self.findings = []

    def check_root_mfa(self):
        """CIS 1.2 – MFA on root account."""
        try:
            summary = self.iam.get_account_summary()["SummaryMap"]
            mfa_enabled = summary.get("AccountMFAEnabled", 0)
            result = "PASS" if mfa_enabled else "FAIL"
            self.findings.append(finding(
                "Root Account MFA", "root",
                result, "Critical", "1.2",
                "Root account should have MFA enabled.",
                "Enable virtual or hardware MFA for the root account via IAM > Security credentials.",
            ))
        except ClientError as e:
            self.findings.append(finding("Root Account MFA", "root", "ERROR", "Critical", "1.2",
                                         str(e), "Check IAM permissions."))

    def check_password_policy(self):
        """CIS 1.7/1.8 – IAM password policy."""
        try:
            policy = self.iam.get_account_password_policy()["PasswordPolicy"]
            issues = []
            if policy.get("MinimumPasswordLength", 0) < 14:
                issues.append("minimum length < 14")
            if not policy.get("RequireUppercaseCharacters", False):
                issues.append("no uppercase requirement")
            if not policy.get("RequireLowercaseCharacters", False):
                issues.append("no lowercase requirement")
            if not policy.get("RequireNumbers", False):
                issues.append("no number requirement")
            if not policy.get("RequireSymbols", False):
                issues.append("no symbol requirement")
            if policy.get("MaxPasswordAge", 9999) > 90:
                issues.append("password age > 90 days")
            if not policy.get("PasswordReusePrevention", False):
                issues.append("no reuse prevention")

            result = "FAIL" if issues else "PASS"
            desc = "Password policy issues: " + ", ".join(issues) if issues else "Password policy meets CIS requirements."
            self.findings.append(finding(
                "IAM Password Policy", "account",
                result, "Medium", "1.7",
                desc,
                "Navigate to IAM > Account settings and configure the password policy to meet CIS standards.",
            ))
        except ClientError as e:
            if "NoSuchEntity" in str(e):
                self.findings.append(finding("IAM Password Policy", "account", "FAIL", "Medium", "1.7",
                                             "No password policy is configured.", "Configure an IAM password policy."))
            else:
                self.findings.append(finding("IAM Password Policy", "account", "ERROR", "Medium", "1.7",
                                             str(e), "Check IAM permissions."))

    def check_unused_access_keys(self, days=90):
        """CIS 1.3 – Disable credentials unused for >= 90 days."""
        try:
            users = self.iam.list_users()["Users"]
            now = datetime.datetime.now(datetime.timezone.utc)
            for user in users:
                username = user["UserName"]
                try:
                    keys = self.iam.list_access_keys(UserName=username)["AccessKeyMetadata"]
                    for key in keys:
                        if key["Status"] != "Active":
                            continue
                        key_id = key["AccessKeyId"]
                        try:
                            last_used = self.iam.get_access_key_last_used(AccessKeyId=key_id)
                            lu_date = last_used["AccessKeyLastUsed"].get("LastUsedDate")
                            if lu_date is None:
                                create_date = key["CreateDate"]
                                age = (now - create_date).days
                                result = "FAIL" if age >= days else "WARN"
                                self.findings.append(finding(
                                    "Unused Access Key", f"{username}/{key_id}",
                                    result, "High", "1.3",
                                    f"Access key never used; created {age} days ago.",
                                    "Disable or delete access keys that have never been used.",
                                ))
                            else:
                                age = (now - lu_date).days
                                result = "FAIL" if age >= days else "PASS"
                                if result == "FAIL":
                                    self.findings.append(finding(
                                        "Unused Access Key", f"{username}/{key_id}",
                                        result, "High", "1.3",
                                        f"Access key not used in {age} days.",
                                        "Disable or delete access keys unused for 90+ days.",
                                    ))
                        except ClientError:
                            pass
                except ClientError:
                    pass
        except ClientError as e:
            self.findings.append(finding("Unused Access Keys", "iam", "ERROR", "High", "1.3",
                                         str(e), "Check IAM permissions."))

    def check_user_mfa(self):
        """CIS 1.4 – MFA enabled for all console users."""
        try:
            users = self.iam.list_users()["Users"]
            for user in users:
                username = user["UserName"]
                try:
                    login_profile = self.iam.get_login_profile(UserName=username)
                    # User has console access
                    mfa_devices = self.iam.list_mfa_devices(UserName=username)["MFADevices"]
                    result = "PASS" if mfa_devices else "FAIL"
                    if result == "FAIL":
                        self.findings.append(finding(
                            "User MFA", username,
                            result, "High", "1.4",
                            f"IAM user {username} has console access but no MFA device.",
                            "Assign a virtual or hardware MFA device to this user.",
                        ))
                except ClientError as e:
                    if "NoSuchEntity" in str(e):
                        pass  # No console access
        except ClientError as e:
            self.findings.append(finding("User MFA", "iam", "ERROR", "High", "1.4",
                                         str(e), "Check IAM permissions."))

    def check_root_access_keys(self):
        """CIS 1.5 – No root access keys."""
        try:
            summary = self.iam.get_account_summary()["SummaryMap"]
            key_count = summary.get("AccountAccessKeysPresent", 0)
            result = "FAIL" if key_count > 0 else "PASS"
            self.findings.append(finding(
                "Root Access Keys", "root",
                result, "Critical", "1.5",
                f"Root account has {key_count} active access key(s)." if key_count else "No root access keys found.",
                "Delete all root account access keys immediately.",
            ))
        except ClientError as e:
            self.findings.append(finding("Root Access Keys", "root", "ERROR", "Critical", "1.5",
                                         str(e), "Check IAM permissions."))

    def check_wildcard_policies(self):
        """Detect inline/managed policies with Action: *."""
        try:
            paginator = self.iam.get_paginator("list_policies")
            for page in paginator.paginate(Scope="Local"):
                for policy in page["Policies"]:
                    try:
                        version = self.iam.get_policy_version(
                            PolicyArn=policy["Arn"],
                            VersionId=policy["DefaultVersionId"],
                        )["PolicyVersion"]
                        doc = version["Document"]
                        for stmt in doc.get("Statement", []):
                            if stmt.get("Effect") == "Allow":
                                actions = stmt.get("Action", [])
                                if isinstance(actions, str):
                                    actions = [actions]
                                if "*" in actions:
                                    self.findings.append(finding(
                                        "Wildcard Policy", policy["PolicyName"],
                                        "FAIL", "High", "1.9",
                                        f"Policy grants Action:* (full admin access).",
                                        "Replace wildcard actions with specific required permissions.",
                                    ))
                                    break
                    except ClientError:
                        pass
        except ClientError as e:
            self.findings.append(finding("Wildcard Policies", "iam", "ERROR", "High", "1.9",
                                         str(e), "Check IAM permissions."))

    def check_admin_policies(self):
        """Flag users/roles directly attached to AdministratorAccess."""
        try:
            users = self.iam.list_users()["Users"]
            for user in users:
                username = user["UserName"]
                try:
                    attached = self.iam.list_attached_user_policies(UserName=username)["AttachedPolicies"]
                    for policy in attached:
                        if "AdministratorAccess" in policy["PolicyName"]:
                            self.findings.append(finding(
                                "Admin Policy Attached", username,
                                "WARN", "High", "1.9",
                                f"User {username} has AdministratorAccess policy directly attached.",
                                "Attach admin policies to groups/roles, not directly to users.",
                            ))
                except ClientError:
                    pass
        except ClientError as e:
            self.findings.append(finding("Admin Policies", "iam", "ERROR", "High", "1.9",
                                         str(e), "Check IAM permissions."))

    def run_all(self):
        print(clr("  [*] Checking root MFA...", "cyan"))
        self.check_root_mfa()
        print(clr("  [*] Checking password policy...", "cyan"))
        self.check_password_policy()
        print(clr("  [*] Checking unused access keys...", "cyan"))
        self.check_unused_access_keys()
        print(clr("  [*] Checking user MFA...", "cyan"))
        self.check_user_mfa()
        print(clr("  [*] Checking root access keys...", "cyan"))
        self.check_root_access_keys()
        print(clr("  [*] Checking wildcard policies...", "cyan"))
        self.check_wildcard_policies()
        print(clr("  [*] Checking admin policies...", "cyan"))
        self.check_admin_policies()
        return self.findings

# ─── S3 Checks ───────────────────────────────────────────────────────────────

class S3Auditor:
    def __init__(self, session):
        self.s3 = session.client("s3")
        self.findings = []

    def list_buckets(self):
        return [b["Name"] for b in self.s3.list_buckets().get("Buckets", [])]

    def check_public_access(self, bucket):
        """CIS 2.1 – S3 Block Public Access."""
        try:
            config = self.s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
            all_blocked = all([
                config.get("BlockPublicAcls", False),
                config.get("IgnorePublicAcls", False),
                config.get("BlockPublicPolicy", False),
                config.get("RestrictPublicBuckets", False),
            ])
            result = "PASS" if all_blocked else "FAIL"
            self.findings.append(finding(
                "S3 Public Access Block", bucket,
                result, "High", "2.1",
                "All block public access settings are enabled." if all_blocked else "Block public access is not fully enabled.",
                "Enable all four Block Public Access settings for the bucket.",
            ))
        except ClientError as e:
            if "NoSuchPublicAccessBlockConfiguration" in str(e):
                self.findings.append(finding("S3 Public Access Block", bucket, "FAIL", "High", "2.1",
                                             "No public access block configuration found.",
                                             "Enable all Block Public Access settings."))
            else:
                self.findings.append(finding("S3 Public Access Block", bucket, "ERROR", "High", "2.1",
                                             str(e), "Check S3 permissions."))

    def check_bucket_encryption(self, bucket):
        """CIS 2.3 – S3 server-side encryption."""
        try:
            self.s3.get_bucket_encryption(Bucket=bucket)
            self.findings.append(finding(
                "S3 Encryption", bucket,
                "PASS", "Medium", "2.3",
                "Default server-side encryption is enabled.",
                "No action required.",
            ))
        except ClientError as e:
            if "ServerSideEncryptionConfigurationNotFoundError" in str(e):
                self.findings.append(finding("S3 Encryption", bucket, "FAIL", "Medium", "2.3",
                                             "Default encryption is not enabled.",
                                             "Enable default encryption (SSE-S3 or SSE-KMS) on the bucket."))
            else:
                self.findings.append(finding("S3 Encryption", bucket, "ERROR", "Medium", "2.3",
                                             str(e), "Check S3 permissions."))

    def check_bucket_versioning(self, bucket):
        """CIS 2.4 – S3 versioning."""
        try:
            versioning = self.s3.get_bucket_versioning(Bucket=bucket)
            status = versioning.get("Status", "Disabled")
            result = "PASS" if status == "Enabled" else "WARN"
            self.findings.append(finding(
                "S3 Versioning", bucket,
                result, "Low", "2.4",
                f"Versioning is {status}.",
                "Enable versioning to protect against accidental deletion.",
            ))
        except ClientError as e:
            self.findings.append(finding("S3 Versioning", bucket, "ERROR", "Low", "2.4",
                                         str(e), "Check S3 permissions."))

    def check_bucket_logging(self, bucket):
        """Ensure S3 access logging is enabled."""
        try:
            logging_cfg = self.s3.get_bucket_logging(Bucket=bucket)
            enabled = "LoggingEnabled" in logging_cfg
            result = "PASS" if enabled else "WARN"
            self.findings.append(finding(
                "S3 Access Logging", bucket,
                result, "Low", "2.5",
                "Access logging is enabled." if enabled else "Access logging is not enabled.",
                "Enable access logging to track requests made to the bucket.",
            ))
        except ClientError as e:
            self.findings.append(finding("S3 Access Logging", bucket, "ERROR", "Low", "2.5",
                                         str(e), "Check S3 permissions."))

    def check_bucket_policy_public(self, bucket):
        """CIS 2.2 – S3 bucket policy does not grant public access."""
        try:
            policy_str = self.s3.get_bucket_policy(Bucket=bucket)["Policy"]
            policy = json.loads(policy_str)
            public = False
            for stmt in policy.get("Statement", []):
                principal = stmt.get("Principal", "")
                if principal == "*" or (isinstance(principal, dict) and principal.get("AWS") == "*"):
                    if stmt.get("Effect") == "Allow":
                        public = True
                        break
            result = "FAIL" if public else "PASS"
            self.findings.append(finding(
                "S3 Bucket Policy Public", bucket,
                result, "High", "2.2",
                "Bucket policy grants public access." if public else "Bucket policy does not grant public access.",
                "Remove any statements granting Principal: * with Effect: Allow.",
            ))
        except ClientError as e:
            if "NoSuchBucketPolicy" in str(e):
                self.findings.append(finding("S3 Bucket Policy Public", bucket, "PASS", "High", "2.2",
                                             "No bucket policy found.", "No action required."))
            else:
                self.findings.append(finding("S3 Bucket Policy Public", bucket, "ERROR", "High", "2.2",
                                             str(e), "Check S3 permissions."))

    def run_all(self):
        print(clr("  [*] Listing S3 buckets...", "cyan"))
        try:
            buckets = self.list_buckets()
            print(clr(f"  [*] Found {len(buckets)} buckets", "cyan"))
            for bucket in buckets:
                print(clr(f"  [*] Auditing bucket: {bucket}", "cyan"))
                self.check_public_access(bucket)
                self.check_bucket_encryption(bucket)
                self.check_bucket_versioning(bucket)
                self.check_bucket_logging(bucket)
                self.check_bucket_policy_public(bucket)
        except ClientError as e:
            self.findings.append(finding("S3 List Buckets", "s3", "ERROR", "High", "2.1",
                                         str(e), "Check S3 permissions."))
        return self.findings

# ─── Security Group Checks ───────────────────────────────────────────────────

SENSITIVE_PORTS = {
    22: ("SSH", "Critical"),
    3389: ("RDP", "Critical"),
    3306: ("MySQL", "High"),
    5432: ("PostgreSQL", "High"),
    27017: ("MongoDB", "High"),
    6379: ("Redis", "High"),
    9200: ("Elasticsearch", "High"),
    5601: ("Kibana", "Medium"),
}


class SecurityGroupAuditor:
    def __init__(self, session):
        self.ec2 = session.client("ec2")
        self.findings = []

    def check_sg_rules(self, sg):
        sg_id = sg["GroupId"]
        sg_name = sg.get("GroupName", sg_id)
        for permission in sg.get("IpPermissions", []):
            from_port = permission.get("FromPort", 0)
            to_port = permission.get("ToPort", 65535)
            for ip_range in permission.get("IpRanges", []):
                cidr = ip_range.get("CidrIp", "")
                if cidr in ("0.0.0.0/0",):
                    for port, (service, sev) in SENSITIVE_PORTS.items():
                        if from_port <= port <= to_port:
                            cis = "4.1" if port == 22 else "4.2" if port == 3389 else "4.3"
                            self.findings.append(finding(
                                f"Open {service} Port", f"{sg_id} ({sg_name})",
                                "FAIL", sev, cis,
                                f"Security group allows inbound {service} (port {port}) from 0.0.0.0/0.",
                                f"Restrict port {port} to known IP ranges or use a VPN/bastion host.",
                            ))
            for ip_range in permission.get("Ipv6Ranges", []):
                cidr = ip_range.get("CidrIpv6", "")
                if cidr == "::/0":
                    for port, (service, sev) in SENSITIVE_PORTS.items():
                        if from_port <= port <= to_port:
                            cis = "4.1" if port == 22 else "4.2" if port == 3389 else "4.3"
                            self.findings.append(finding(
                                f"Open {service} Port (IPv6)", f"{sg_id} ({sg_name})",
                                "FAIL", sev, cis,
                                f"Security group allows inbound {service} (port {port}) from ::/0.",
                                f"Restrict port {port} to known IPv6 ranges.",
                            ))

    def run_all(self):
        print(clr("  [*] Listing security groups...", "cyan"))
        try:
            paginator = self.ec2.get_paginator("describe_security_groups")
            for page in paginator.paginate():
                for sg in page["SecurityGroups"]:
                    self.check_sg_rules(sg)
            print(clr(f"  [*] Checked {sum(1 for _ in [])} security groups", "cyan"))
        except ClientError as e:
            self.findings.append(finding("Security Groups", "ec2", "ERROR", "High", "4.1",
                                         str(e), "Check EC2 permissions."))
        return self.findings

# ─── Demo Mode ───────────────────────────────────────────────────────────────

def get_demo_findings():
    return [
        finding("Root Account MFA", "root", "FAIL", "Critical", "1.2",
                 "Root account does not have MFA enabled.", "Enable MFA for the root account immediately."),
        finding("Root Access Keys", "root", "FAIL", "Critical", "1.5",
                 "Root account has active access keys.", "Delete all root account access keys."),
        finding("IAM Password Policy", "account", "FAIL", "Medium", "1.7",
                 "Password policy: minimum length < 14, no symbol requirement.", "Update IAM password policy."),
        finding("User MFA", "alice", "FAIL", "High", "1.4",
                 "User alice has console access but no MFA device.", "Assign MFA device to alice."),
        finding("User MFA", "bob", "PASS", "High", "1.4",
                 "User bob has MFA enabled.", "No action required."),
        finding("Unused Access Key", "alice/AKIAIOSFODNN7EXAMPLE", "FAIL", "High", "1.3",
                 "Access key not used in 120 days.", "Disable or delete this access key."),
        finding("Admin Policy Attached", "alice", "WARN", "High", "1.9",
                 "AdministratorAccess policy directly attached to user.", "Use IAM groups/roles for admin access."),
        finding("S3 Public Access Block", "my-company-data", "FAIL", "High", "2.1",
                 "Block public access is not fully enabled.", "Enable all Block Public Access settings."),
        finding("S3 Bucket Policy Public", "my-company-data", "FAIL", "High", "2.2",
                 "Bucket policy grants public access via Principal: *.", "Remove public access statement."),
        finding("S3 Encryption", "my-company-data", "FAIL", "Medium", "2.3",
                 "Default encryption is not enabled.", "Enable SSE-S3 or SSE-KMS encryption."),
        finding("S3 Versioning", "my-company-data", "WARN", "Low", "2.4",
                 "Versioning is Disabled.", "Enable versioning to protect against accidental deletion."),
        finding("S3 Access Logging", "my-company-data", "WARN", "Low", "2.5",
                 "Access logging is not enabled.", "Enable S3 access logging."),
        finding("S3 Public Access Block", "static-assets", "PASS", "High", "2.1",
                 "Block public access is fully enabled.", "No action required."),
        finding("S3 Encryption", "static-assets", "PASS", "Medium", "2.3",
                 "Default encryption is enabled.", "No action required."),
        finding("Open SSH Port", "sg-0abc123 (web-servers)", "FAIL", "Critical", "4.1",
                 "Security group allows SSH (port 22) from 0.0.0.0/0.", "Restrict SSH to trusted IP ranges."),
        finding("Open RDP Port", "sg-0abc123 (web-servers)", "FAIL", "Critical", "4.2",
                 "Security group allows RDP (port 3389) from 0.0.0.0/0.", "Restrict RDP to trusted IP ranges."),
        finding("Open MySQL Port", "sg-0def456 (database)", "FAIL", "High", "4.3",
                 "Security group allows MySQL (port 3306) from 0.0.0.0/0.", "Restrict MySQL to application subnet CIDR."),
        finding("Open Elasticsearch Port", "sg-0def456 (database)", "FAIL", "High", "4.3",
                 "Security group allows Elasticsearch (port 9200) from 0.0.0.0/0.", "Restrict Elasticsearch to VPC CIDR."),
    ]

# ─── CIS Scoring ─────────────────────────────────────────────────────────────

def score_findings(findings):
    total = len(findings)
    passes = sum(1 for f in findings if f["result"] == "PASS")
    fails = sum(1 for f in findings if f["result"] == "FAIL")
    warns = sum(1 for f in findings if f["result"] == "WARN")
    errors = sum(1 for f in findings if f["result"] == "ERROR")
    by_severity = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        if f["result"] == "FAIL" and f["severity"] in by_severity:
            by_severity[f["severity"]] += 1
    pct = round((passes / total) * 100, 1) if total > 0 else 0.0
    return {
        "total": total, "pass": passes, "fail": fails,
        "warn": warns, "error": errors,
        "by_severity": by_severity,
        "cis_compliance_pct": pct,
    }

# ─── Reporting ───────────────────────────────────────────────────────────────

def print_findings(findings, score):
    if TABULATE_AVAILABLE:
        rows = [
            [
                f["check"][:35],
                f["resource"][:30],
                clr(f["result"], result_color(f["result"])),
                f["cis_control"],
                clr(f["severity"], severity_color(f["severity"])),
            ]
            for f in findings
        ]
        print(tabulate(rows, headers=["Check", "Resource", "Result", "CIS", "Severity"],
                       tablefmt="rounded_outline"))
    else:
        for f in findings:
            print(f"  [{f['result']}] {f['check']} | {f['resource']} | CIS {f['cis_control']} | {f['severity']}")
    print()
    print(clr(f"  CIS Compliance Score: {score['cis_compliance_pct']}%", "bright"))
    print(f"  Total: {score['total']}  PASS: {score['pass']}  "
          f"FAIL: {score['fail']}  WARN: {score['warn']}")
    sev = score["by_severity"]
    print(f"  Failures by severity – "
          f"Critical: {clr(sev['Critical'], 'red')}  "
          f"High: {clr(sev['High'], 'red')}  "
          f"Medium: {clr(sev['Medium'], 'yellow')}  "
          f"Low: {clr(sev['Low'], 'cyan')}")


def save_json_report(findings, score, output_path):
    report = {
        "generated": datetime.datetime.utcnow().isoformat() + "Z",
        "tool": "Cloud Security Misconfiguration Scanner",
        "score": score,
        "findings": findings,
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(clr(f"\n  [+] JSON report saved to {output_path}", "green"))


def save_html_report(findings, score, output_path):
    rows = ""
    for f in findings:
        badge_class = {"PASS": "pass", "FAIL": "fail", "WARN": "warn"}.get(f["result"], "warn")
        sev_class = {"Critical": "critical", "High": "high", "Medium": "medium", "Low": "low"}.get(f["severity"], "low")
        rows += f"""<tr>
          <td>{f['check']}</td>
          <td class="mono">{f['resource']}</td>
          <td><span class="badge {badge_class}">{f['result']}</span></td>
          <td>{f['cis_control']}</td>
          <td><span class="badge {sev_class}">{f['severity']}</span></td>
          <td class="small">{f['description']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Cloud Security Scan Report</title>
<style>
body{{font-family:Inter,sans-serif;background:#0f1117;color:#c9d1d9;margin:0;padding:24px}}
h1{{color:#58a6ff}} table{{width:100%;border-collapse:collapse;margin-top:24px}}
th{{background:#161b22;color:#8b949e;padding:10px;text-align:left;font-size:12px;text-transform:uppercase}}
td{{padding:10px;border-bottom:1px solid #21262d;font-size:13px}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:12px}}
.small{{font-size:12px;color:#8b949e}}
.badge{{padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600}}
.pass{{background:#0f2d1a;color:#3fb950}} .fail{{background:#2d1018;color:#f85149}}
.warn{{background:#2d1f0a;color:#f0883e}} .critical{{background:#2d1018;color:#f85149}}
.high{{background:#2d1018;color:#f0883e}} .medium{{background:#2d1f0a;color:#f0883e}}
.low{{background:#0d1d3b;color:#58a6ff}}
.summary{{display:flex;gap:16px;margin:24px 0}}
.stat{{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:16px 24px;text-align:center}}
.stat .val{{font-size:28px;font-weight:700}} .stat .lbl{{font-size:12px;color:#8b949e;margin-top:4px}}
</style></head>
<body>
<h1>Cloud Security Scan Report</h1>
<p style="color:#8b949e">Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
<div class="summary">
  <div class="stat"><div class="val">{score['cis_compliance_pct']}%</div><div class="lbl">CIS Compliance</div></div>
  <div class="stat"><div class="val" style="color:#3fb950">{score['pass']}</div><div class="lbl">PASS</div></div>
  <div class="stat"><div class="val" style="color:#f85149">{score['fail']}</div><div class="lbl">FAIL</div></div>
  <div class="stat"><div class="val" style="color:#f0883e">{score['warn']}</div><div class="lbl">WARN</div></div>
  <div class="stat"><div class="val" style="color:#f85149">{score['by_severity']['Critical']}</div><div class="lbl">Critical</div></div>
  <div class="stat"><div class="val" style="color:#f0883e">{score['by_severity']['High']}</div><div class="lbl">High</div></div>
</div>
<table>
  <thead><tr><th>Check</th><th>Resource</th><th>Result</th><th>CIS</th><th>Severity</th><th>Description</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
</body></html>"""
    with open(output_path, "w") as f:
        f.write(html)
    print(clr(f"\n  [+] HTML report saved to {output_path}", "green"))

# ─── Main ─────────────────────────────────────────────────────────────────────

BANNER = r"""
   _____ _                 _   _____
  / ____| |               | | / ____|
 | |    | | ___  _   _  __| || (___   ___  __ _ _ __  _ __   ___ _ __
 | |    | |/ _ \| | | |/ _` | \___ \ / __|/ _` | '_ \| '_ \ / _ \ '__|
 | |____| | (_) | |_| | (_| | ____) | (__| (_| | | | | | | |  __/ |
  \_____|_|\___/ \__,_|\__,_||_____/ \___|\__,_|_| |_|_| |_|\___|_|

  AWS CIS Foundations Benchmark Scanner  |  github.com/jasstejsingh
"""


def main():
    parser = argparse.ArgumentParser(
        description="Cloud Security Misconfiguration Scanner – AWS CIS Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--profile", default=None, help="AWS profile name")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--checks", choices=["all", "iam", "s3", "sg"], default="all",
                        help="Which checks to run (default: all)")
    parser.add_argument("--output", default="scan_report", help="Output file base name")
    parser.add_argument("--format", choices=["json", "html", "both"], default="both",
                        help="Output format (default: both)")
    parser.add_argument("--demo", action="store_true", help="Run with mock data (no AWS credentials needed)")
    args = parser.parse_args()

    print(clr(BANNER, "green"))

    all_findings = []

    if args.demo:
        print(clr("  [DEMO MODE] Running with simulated findings...\n", "yellow"))
        all_findings = get_demo_findings()
    else:
        if not BOTO3_AVAILABLE:
            print(clr("  [!] boto3 is not installed. Run: pip install boto3", "red"))
            print(clr("  [!] Use --demo to run with simulated data.", "yellow"))
            sys.exit(1)

        try:
            session_kwargs = {"region_name": args.region}
            if args.profile:
                session_kwargs["profile_name"] = args.profile
            session = boto3.Session(**session_kwargs)

            if args.checks in ("all", "iam"):
                print(clr("\n[+] Running IAM checks...", "blue"))
                auditor = IAMAuditor(session)
                all_findings.extend(auditor.run_all())

            if args.checks in ("all", "s3"):
                print(clr("\n[+] Running S3 checks...", "blue"))
                auditor = S3Auditor(session)
                all_findings.extend(auditor.run_all())

            if args.checks in ("all", "sg"):
                print(clr("\n[+] Running Security Group checks...", "blue"))
                auditor = SecurityGroupAuditor(session)
                all_findings.extend(auditor.run_all())

        except (NoCredentialsError, ProfileNotFound) as e:
            print(clr(f"\n  [!] AWS credential error: {e}", "red"))
            print(clr("  [!] Use --demo to run with simulated data.", "yellow"))
            sys.exit(1)

    print(clr("\n[+] Scan complete. Results:\n", "blue"))
    score = score_findings(all_findings)
    print_findings(all_findings, score)

    if args.format in ("json", "both"):
        save_json_report(all_findings, score, args.output + ".json")
    if args.format in ("html", "both"):
        save_html_report(all_findings, score, args.output + ".html")


if __name__ == "__main__":
    main()
