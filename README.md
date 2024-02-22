# AWS DevOps Automation

This Python project automates the provisioning and monitoring of web servers on AWS, simplifying the process of EC2 instance launch, S3 bucket setup, and website deployment with an easy-to-use script.

## Project Overview

- Utilises Python 3 and the Boto3 library to interact with AWS services.
- Automatically creates and launches an Amazon Linux 2023 EC2 nano instance.
- Configures security groups and tags for easy management and security.
- Installs and starts a web server (Apache by default) that displays instance metadata.
- Sets up an S3 bucket for static website hosting, uploads content, and makes a website accessible.
- Opens a browser to show the newly deployed EC2 instance and S3 static website URLs.
- Includes a `monitoring.sh` script for enhanced monitoring of the EC2 instance.

## Prerequisites

- Python 3 installed on your local machine ([https://www.python.org/](https://www.python.org/)).
- Boto3 library installed (`pip3 install boto3`).
- Google Fire installed (`pip3 install fire`).
- An AWS account with properly configured credentials (typically in `~/.aws/credentials`).
- An existing SSH key pair for EC2 access, placed in the same directory as the script.

## CLI Usage

1. **Clone the Repository**: Download the project to your local machine.
2. **Configure AWS Credentials**: Verify that your AWS credentials are correctly set up.
3. **Prepare the SSH Key**: Place your `.pem` key file in the script's directory for SSH access.
4. **Execute the Script**: Use the following commands to manage AWS resources and deploy your web server:

    - **Launch the Script without Arguments**: Starts the default automation process.
      ```bash
      python3 devops_1.py
      ```
    - **List Running EC2 Instances**: Displays all running EC2 instances.
      ```bash
      python3 devops_1.py instances
      ```
    - **Terminate a Specific Instance**: Terminate an instance by specifying its ID.
      ```bash
      python3 devops_1.py terminate <instance_id>
      ```
    - **Terminate All Running Instances**: Stops all instances currently running.
      ```bash
      python3 devops_1.py terminate_all
      ```
    - **Delete All S3 Buckets**: Removes all S3 buckets.
      ```bash
      python3 devops_1.py delete_buckets

## Monitoring

To leverage the included `monitoring.sh` script for system monitoring on the EC2 instance:

1. The `devops_1.py` script will automatically transfer `monitoring.sh` to the instance upon execution.
2. SSH into the EC2 instance using the `.pem` key file.
3. Change the script's permissions to make it executable: `chmod +x monitoring.sh`.
4. Execute the script: `./monitoring.sh`.
