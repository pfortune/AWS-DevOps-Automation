# AWS DevOps Automation

This Python project automates the provisioning and monitoring of web servers on AWS, simplifying the process of EC2 instance launch, S3 bucket setup, and website deployment with an easy-to-use script.

## Project Overview

- Utilises Python 3 and the Boto3 library to interact with AWS services.
- Automates the launch of an Amazon Linux EC2 nano instance, automatically determining the latest AMI using AWS Systems Manager Parameter Store.
- Configures security groups and tags for easy management and security.
- Installs and starts a web server to display instance metadata (with potential customization).
- Configures an S3 bucket for static website hosting, enabling content uploads and public access.
- Opens a browser to show the newly deployed EC2 instance and S3 static website URLs.
- Facilitates enhanced EC2 instance monitoring with an included `monitoring.sh` script and SSH-based automation. 
- Integrates with AWS CloudWatch to list metrics, retrieve granular metric data over various time periods, and manage alarms.
- Utilises a configuration file (config.ini) for customisation.
- Includes error handling to improve robustness. 

## Prerequisites

- Python 3 installed on your local machine ([https://www.python.org/](https://www.python.org/)).
- Boto3 library installed (`pip3 install boto3`).
- Python Fire installed (`pip3 install fire`).
- An AWS account with properly configured credentials (typically in `~/.aws/credentials`).
- An existing SSH key pair for EC2 access, placed in the same directory as the script.

## Usage

1. **Clone the Repository**: Download the project to your local machine.

2. **Configure AWS Credentials**: Verify that your AWS credentials are correctly set up.

3. **Customise the Configuration**: Modify the `config.ini` file to customise the script's behaviour.  Before executing most commands, ensure you've updated `config.ini` with your AWS PEM key name and other desired settings.

4. **Getting Help:** To view available commands and get help with a specific command, use the `--help` or `-h` flag. For example: `python3 devops_1.py --help`

5. **Deployment**: To launch an EC2 instance, configure an S3 bucket, and deploy the web server, execute `python3 devops_1.py` with no arguments.

6. **CLI**: To interact with AWS resources using the command-line interface, try some of the commands below.

**AWS Resource Management**

* **AWS Management Commands:**
    * `python3 devops_1.py instances`
    * `python3 devops_1.py terminate <instance_id>` 
    * `python3 devops_1.py terminate_all` 
    * `python3 devops_1.py buckets` 
    * `python3 devops_1.py delete_buckets` 

* **CloudWatch Commands:**
  * `python3 devops_1.py cloudwatch --help`
  * `python3 devops_1.py cloudwatch list_metrics --instance_id <instance_id>` 
  * `python3 devops_1.py cloudwatch get_metric_data --instance_id <instance_id> --metric_name <metric_name> [--period <1h|8h|24h>]`
  * `python3 devops_1.py cloudwatch create_alarm --alarm_name <name> --metric_name <metric_name> --instance_id <instance_id> --threshold <threshold> [--comparison_operator <operator>] [--evaluation_periods <number>] [--period <seconds>] [--statistic <statistic>]`   
  * `python3 devops_1.py cloudwatch list_alarms`
  * `python3 devops_1.py cloudwatch delete_alarm --alarm_name <name>` 
  * `python3 devops_1.py cloudwatch metrics --instance_id <instance_id>` 

**Examples**

* **Retrieve an overview core metrics for an instance:**
    ```bash
    python3 devops_1.py cloudwatch metrics --instance_id i-0c86e59079b90dd57
    ```

* **Retrieve 24 hours of network traffic data:** 
    ```bash
    python3 devops_1.py cloudwatch get_metric_data --instance_id i-0c86e59079b90dd57 --metric_name NetworkIn --period 24h
    ```

* **Check disk read operations over the past hour:**
    ```bash
    python3 devops_1.py cloudwatch get_metric_data --instance_id i-0c86e59079b90dd57 --metric_name DiskReadOps --period 1h
    ```

* **Create an alarm that triggers if CPU usage exceeds 90%:**
    ```bash
    python3 devops_1.py cloudwatch create_alarm --alarm_name HighCPUAlert --metric_name CPUUtilization --instance_id i-0c86e59079b90dd57 --threshold 90
    ```

## Monitoring

To leverage the included `monitoring.sh` script for system monitoring on the EC2 instance:

1. The `devops_1.py` script will automatically transfer `monitoring.sh` to the instance upon execution.
2. SSH into the EC2 instance using the `.pem` key file.
3. Change the script's permissions to make it executable: `chmod +x monitoring.sh`.
4. Execute the script: `./monitoring.sh`.
