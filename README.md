# AWS DevOps Automation

This Python project automates the provisioning and monitoring of web servers on AWS, simplifying the process of EC2 instance launch, S3 bucket setup, and website deployment with an easy-to-use script.

## Project Overview

- Utilises Python 3 and the Boto3 library to interact with AWS services.
- Automates the launch of an Amazon Linux (latest available) EC2 nano instance.
- Configures security groups and tags for easy management and security.
- Installs and starts a web server (Apache by default) that displays instance metadata.
- Configures an S3 bucket for static website hosting, enabling content uploads and public access.
- Opens a browser to show the newly deployed EC2 instance and S3 static website URLs.
- Facilitates enhanced EC2 instance monitoring with an included `monitoring.sh` script and SSH-based automation.
- Integrates with AWS CloudWatch to list metrics, retrieve metric data, and manage alarms.
- Utilises a configuration file (config.ini) for customisation.

## Prerequisites

- Python 3 installed on your local machine ([https://www.python.org/](https://www.python.org/)).
- Boto3 library installed (`pip3 install boto3`).
- Python Fire installed (`pip3 install fire`).
- An AWS account with properly configured credentials (typically in `~/.aws/credentials`).
- An existing SSH key pair for EC2 access, placed in the same directory as the script.

## CLI Usage

1.  **Clone the Repository**: Download the project to your local machine.
2.  **Configure AWS Credentials**: Verify that your AWS credentials are correctly set up.
3.  **Prepare the SSH Key**: Place your `.pem` key file in the script's directory for SSH access.
4.  **Execute the Script**: Use the following commands to manage AWS resources, deploy your web server, and monitor resources:

**AWS Management Commands:**

*   `python3 devops_1.py instances` : Lists running EC2 instances.
*   `python3 devops_1.py terminate <instance_id>` :  Terminates a specific EC2 instance.
*   `python3 devops_1.py terminate_all` : Terminates all running EC2 instances.
*   `python3 devops_1.py buckets` : Lists all S3 buckets.
*   `python3 devops_1.py delete_buckets` : Deletes all S3 buckets.

**CloudWatch Commands:**

*   `python3 devops_1.py cloudwatch list_metrics --instance_id <instance_id>` : Lists available CloudWatch metrics for an instance.
*   `python3 devops_1.py cloudwatch get_metric_data --instance_id <instance_id> --metric_name <metric_name> [--period <1h|8h|24h>]`: Retrieves specific metric data (default period: 1 hour).
*  `python3 devops_1.py cloudwatch create_alarm --alarm_name <name> --metric_name <metric_name> --instance_id <instance_id> --threshold <threshold> [...additional flags]` : Creates a CloudWatch alarm.
*  `python3 devops_1.py cloudwatch delete_alarm --alarm_name <name>` : Deletes a CloudWatch alarm.
*  `python3 devops_1.py cloudwatch metrics --instance_id <instance_id>` : Retrieves and displays basic CloudWatch metrics for a specified EC2 instance.

**Example:**

```bash
python3 devops_1.py cloudwatch get_metric_data --instance_id i-0123456789 --metric_name CPUUtilization --period 8h
## Monitoring

To leverage the included `monitoring.sh` script for system monitoring on the EC2 instance:

1. The `devops_1.py` script will automatically transfer `monitoring.sh` to the instance upon execution.
2. SSH into the EC2 instance using the `.pem` key file.
3. Change the script's permissions to make it executable: `chmod +x monitoring.sh`.
4. Execute the script: `./monitoring.sh`.
