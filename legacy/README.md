# legacy/: the original AWS version

Before the local Redis stack, OrbitalNet ran each satellite as an AWS Lambda function talking over
SNS, with state in DynamoDB. That design is kept here for reference. Nothing in mission control or
research depends on it.

| File | What it is |
|---|---|
| `aws/lambda_function.py` | one satellite node as a Lambda handler |
| `aws/cloud_dashboard.py` | the Streamlit dashboard that read DynamoDB/SNS |
| `aws/config.py` | its own copy of the config (sectors, battery constants, AWS resource names) |
| `aws/TECHNICAL_SPEC.md` | the original technical specification |
| `aws/requirements.txt` | boto3 and friends |

The devcontainer (`.devcontainer/devcontainer.json`) still boots `legacy/aws/cloud_dashboard.py`. It needs AWS
credentials in `.env`, which is gitignored and must never be committed.
