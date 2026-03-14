# Cloud Security Misconfiguration Scanner

A Python-based AWS security auditing tool that checks your AWS environment against the **CIS AWS Foundations Benchmark v1.4** controls. It identifies misconfigurations across IAM, S3, and Security Groups, generates risk-scored findings, and produces both JSON and HTML reports.

---

## AWS Security Overview

Cloud misconfigurations are the leading cause of data breaches in AWS environments. This scanner automates the detection of the most critical security gaps:

- **Identity & Access Management (IAM)** — overprivileged users, missing MFA, stale credentials, root account exposure
- **S3 Storage** — publicly accessible buckets, missing encryption, absent access logging
- **Network Security** — security groups exposing sensitive ports to the internet (0.0.0.0/0)

---

## CIS Benchmark Alignment

| Control ID | Title | Severity |
|-----------|-------|----------|
| 1.2 | Ensure MFA is enabled for the root account | Critical |
| 1.3 | Ensure credentials unused for 90 days are disabled | High |
| 1.4 | Ensure MFA is enabled for all console IAM users | High |
| 1.5 | Ensure no root account access key exists | Critical |
| 1.6 | Ensure access keys are rotated every 90 days | High |
| 1.7 | Ensure IAM password policy meets complexity requirements | Medium |
| 2.1 | Ensure S3 Block Public Access is enabled | High |
| 2.2 | Ensure S3 bucket policy does not allow public access | High |
| 2.3 | Ensure S3 default encryption is enabled | Medium |
| 2.4 | Ensure S3 versioning is enabled | Low |
| 2.5 | Ensure S3 access logging is enabled | Low |
| 4.1 | Ensure no SG allows 0.0.0.0/0 ingress on port 22 | High |
| 4.2 | Ensure no SG allows 0.0.0.0/0 ingress on port 3389 | High |
| 4.3 | Ensure VPC flow logs are enabled | Medium |

---

## Required IAM Permissions

The scanning IAM user or role needs the following policy attached:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudScannerReadOnly",
      "Effect": "Allow",
      "Action": [
        "iam:GetAccountSummary",
        "iam:GetAccountPasswordPolicy",
        "iam:ListUsers",
        "iam:ListAccessKeys",
        "iam:GetAccessKeyLastUsed",
        "iam:ListMFADevices",
        "iam:GetLoginProfile",
        "iam:ListPolicies",
        "iam:GetPolicyVersion",
        "iam:ListAttachedUserPolicies",
        "s3:ListAllMyBuckets",
        "s3:GetBucketPublicAccessBlock",
        "s3:GetBucketEncryption",
        "s3:GetBucketVersioning",
        "s3:GetBucketLogging",
        "s3:GetBucketPolicy",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeVpcs",
        "ec2:DescribeFlowLogs"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Installation

```bash
# Clone or navigate to this directory
cd cloud-scanner

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate      # Linux/macOS
# venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt

# Verify AWS credentials are configured
aws configure list
```

---

## Usage

```bash
# Run with default AWS profile, all checks
python cloud_scanner.py

# Run demo mode (no AWS credentials needed)
python cloud_scanner.py --demo

# Use a specific AWS profile and region
python cloud_scanner.py --profile prod-audit --region eu-west-1

# Run only IAM checks, output JSON only
python cloud_scanner.py --checks iam --format json --output iam_report

# Run only S3 checks
python cloud_scanner.py --checks s3

# Run only Security Group checks
python cloud_scanner.py --checks sg

# Generate HTML report only
python cloud_scanner.py --format html --output security_report
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--profile` | default | AWS CLI profile name |
| `--region` | us-east-1 | Target AWS region |
| `--checks` | all | Checks to run: all / iam / s3 / sg |
| `--output` | scan_report | Output filename (without extension) |
| `--format` | both | Report format: json / html / both |
| `--demo` | false | Run with mock data (no credentials) |

---

## Finding Severity Guide

| Severity | Description | SLA for Remediation |
|----------|-------------|---------------------|
| **Critical** | Immediate risk of account compromise or data exposure (e.g., no root MFA, root access keys present) | 24 hours |
| **High** | Significant exposure, likely exploitable by an attacker (e.g., public S3 bucket, SSH open to internet) | 7 days |
| **Medium** | Configuration does not follow best practices and increases risk (e.g., weak password policy, no encryption) | 30 days |
| **Low** | Minor gaps in defense-in-depth posture (e.g., no access logging, no versioning) | 90 days |

---

## Interactive Dashboard

Open `index.html` in a browser for a full interactive security dashboard with:

- Animated scan progress terminal
- Executive summary with CIS compliance percentage
- Per-service findings tables (IAM, S3, Security Groups)
- CIS Benchmark scorecard (20 controls)
- Remediation accordion with step-by-step fixes
- Risk donut chart
- One-click JSON report export
