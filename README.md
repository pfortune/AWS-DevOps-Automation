# AWS DevOps Automation

This Python project automates the provisioning and monitoring of web servers on AWS, including EC2 instance launch, S3 bucket setup, and website deployment.

## Project Overview

* Utilises Python 3 and the Boto3 library to interact with AWS services.
* Creates and launches an Amazon Linux 2023 EC2 nano instance.
* Configures appropriate security groups and tags.
* Installs and configures a web server (Apache by default) with instance metadata.
* Creates an S3 bucket, uploads content, and enables static website hosting.
* Launches a browser displaying the EC2 and S3 website URLs.
* Provides a monitoring script for the EC2 instance.

## Prerequisites

* Python 3 ([https://www.python.org/](https://www.python.org/))
* Boto3 library (`pip install boto3`)
* AWS account with valid credentials configured in `~/.aws/credentials`
* Existing SSH key pair for EC2 access

## Usage

1. Clone this repository
2. Ensure your AWS credentials are correctly configured.
3. Run the Python script: `python3 devops_1.py`

## Monitoring

The included `monitoring.sh` script performs basic system monitoring on the EC2 instance. To utilise it:

1. After running `devops_1.py`, the script will be transferred to your instance.
2. SSH into your EC2 instance.
3. Make the script executable: `chmod +x monitoring.sh`
4. Run the script: `./monitoring.sh`

## Notes

* Customise the `monitoring.sh` script to include additional monitoring checks as needed.
* Replace image URLs and other parameters in the code as required. 