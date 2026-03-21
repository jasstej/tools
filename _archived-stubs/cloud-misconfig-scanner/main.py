import argparse
import json

import boto3


def check_s3_public(s3_client) -> list[dict]:
    findings = []
    for bucket in s3_client.list_buckets().get("Buckets", []):
        name = bucket["Name"]
        try:
            block = s3_client.get_public_access_block(Bucket=name)["PublicAccessBlockConfiguration"]
            if not all(block.values()):
                findings.append({"resource": name, "type": "S3", "severity": "high", "issue": "Public access block not fully enabled"})
        except Exception:
            findings.append({"resource": name, "type": "S3", "severity": "medium", "issue": "Public access block missing"})
    return findings


def check_sg_open_world(ec2_client) -> list[dict]:
    findings = []
    for sg in ec2_client.describe_security_groups().get("SecurityGroups", []):
        for perm in sg.get("IpPermissions", []):
            for ipr in perm.get("IpRanges", []):
                if ipr.get("CidrIp") == "0.0.0.0/0":
                    findings.append({"resource": sg.get("GroupId"), "type": "SecurityGroup", "severity": "high", "issue": "Ingress open to 0.0.0.0/0"})
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="AWS misconfiguration scanner starter")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--output", default="aws-risk-report.json")
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    findings = []
    findings.extend(check_s3_public(session.client("s3")))
    findings.extend(check_sg_open_world(session.client("ec2")))

    risk_score = sum(10 if f["severity"] == "high" else 5 for f in findings)
    report = {"region": args.region, "findings": findings, "risk_score": risk_score}

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Report written: {args.output} | Findings: {len(findings)} | Risk: {risk_score}")


if __name__ == "__main__":
    main()
