# Cloud Security Misconfiguration Scanner (AWS)

AWS CIS-style configuration scanner starter.

## Features

- S3 public-access-block checks
- Security group world-open ingress checks
- Aggregate risk score in JSON report

## Usage

```bash
python main.py --region us-east-1 --output aws-risk-report.json
```
