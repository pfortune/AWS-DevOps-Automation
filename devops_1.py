#!/usr/bin/env python3

# Standard Library Imports
import requests
import random
import string
import subprocess
import os
import json
import stat
from time import sleep
import webbrowser
import configparser
from error_logging import log, error_handler
import cli

# Third Party Imports
import boto3
from botocore.exceptions import ClientError

@error_handler
def load_configuration(config_path='config.ini'):
    """
    Loads the configuration from the specified file.

    Parameters:
    - config_path: The path to the configuration file.

    Returns the configuration as a dictionary.
    """
    log("Loading configuration...")
    config = configparser.ConfigParser()
    config.read(config_path)
    log("Configuration loaded successfully.")

    return config['DEFAULT']

@error_handler
def generate_user_data():
    """
    Generates a user data script for EC2 instance initialization.
    This script updates the system, installs and starts Apache HTTP Server,
    and creates a custom index.html page with the instance's metadata.

    Returns the user data script as a string.
    """
    user_data = """#!/bin/bash
yum update -y
yum install -y httpd
systemctl start httpd.service
systemctl enable httpd.service
# Fetch instance metadata
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
INSTANCE_TYPE=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-type)
AVAILABILITY_ZONE=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
cat <<EOF > /var/www/html/index.html
<html>
<body>
<h1>Hello from Waterford</h1>
<p>Instance ID: $INSTANCE_ID</p>
<p>Instance Type: $INSTANCE_TYPE</p>
<p>Availability Zone: $AVAILABILITY_ZONE</p>
<hr>
<img src="https://cataas.com/cat/cute" alt="Cute cat" style="height: 500px;">
</body>
</html>
EOF
"""

    log("User data script generated successfully.")
    return user_data

@error_handler
def create_instance(**param):
    """
    Creates an EC2 instance with specified parameters.
    
    Parameters:
    - key_name: The name of the key pair for SSH access.
    - instance_type: The type of instance to launch.
    - instance_name: The name tag for the instance.
    - security_group: The security group ID to assign to the instance.
    - ami_id: The AMI ID for the instance's OS.
    - user_data: The user data script to run on instance initialisation.
    - security_group: The security group ID to assign to the instance.
    
    Returns the public IP address of the created instance.
    """
    created_instances = ec2.create_instances(
        ImageId=param['ami_id'],
        InstanceType=param['instance_type'],
        MinCount=1,
        MaxCount=1,
        KeyName=param['key_name'],
        SecurityGroupIds=[param['security_group']],
        UserData=param['user_data'],
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': param['instance_name']
                    },
                    {
                        'Key': 'Owner',
                        'Value': 'DevOps'
                    },
                    {
                        'Key': 'Environment',
                        'Value': 'Development'
                    }
                ]
            },
        ]
    )

    instance = created_instances[0]
    log("Waiting for the instance to enter running state...")
    instance.wait_until_running()  # Wait for the instance to be ready
    instance.reload()
    log(f"Instance running, Public IP: {instance.public_ip_address}")
    return instance.public_ip_address

@error_handler
def create_security_group(vpc_id, group_name="NewLaunchWizard", description="Allows access to HTTP and SSH ports"):
    """
    Creates a new security group in the specified VPC.
    
    Parameters:
    - vpc_id: The ID of the VPC where the security group will be created.
    - group_name: The name of the security group.
    - description: A description of the security group's purpose.
    
    Returns the ID of the created security group.
    """
    # Create the security group
    sg = ec2.create_security_group(GroupName=group_name, Description=description, VpcId=vpc_id)
    log(f"Security Group Created: {sg.id}")

    # Add inbound rules
    sg.authorize_ingress(
        IpPermissions=[
            # HTTP access
            {'FromPort': 80, 'ToPort': 80, 'IpProtocol': 'tcp', 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            # SSH access
            {'FromPort': 22, 'ToPort': 22, 'IpProtocol': 'tcp', 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        ]
    )
    log("Inbound rules added for HTTP and SSH.")

    return sg.id

@error_handler
def find_matching_sg(vpc_id):
    """
    Searches for an existing security group in the specified VPC that allows HTTP and SSH access.
    
    Parameters:
    - vpc_id: The ID of the VPC to search within.
    
    Returns the ID of the matching security group, if found.
    """
    response = ec2_client.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    for sg in response['SecurityGroups']:
        http_rules = [rule for rule in sg['IpPermissions'] if rule.get('FromPort') == 80 and rule.get('ToPort') == 80 and '0.0.0.0/0' in [ip['CidrIp'] for ip in rule.get('IpRanges', [])]]
        ssh_rules = [rule for rule in sg['IpPermissions'] if rule.get('FromPort') == 22 and rule.get('ToPort') == 22 and '0.0.0.0/0' in [ip['CidrIp'] for ip in rule.get('IpRanges', [])]]

        if http_rules and ssh_rules:
            log(f"Found matching security group: {sg['GroupId']}")
            return sg['GroupId']
    return None

@error_handler
def generate_unique_sg_name(base_name, vpc_id):
    """
    Generates a unique name for a security group within a VPC.
    
    Parameters:
    - base_name: The base name for the security group.
    - vpc_id: The ID of the VPC.
    
    Returns a unique security group name.
    """
    unique_name = base_name
    while True:
        existing_sgs = ec2_client.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}, {'Name': 'group-name', 'Values': [unique_name]}])
        if not existing_sgs['SecurityGroups']:
            # If no existing SG matches the unique_name, it's unique
            break
        attempt += 1
        unique_name = f"{base_name}-{random.choice(string.ascii_lowercase)}"

    log(f"Generated unique security group name: {unique_name}")
    return unique_name

@error_handler
def get_default_vpc_id():
    """
    Retrieves the default VPC ID for the AWS account.
    
    Returns the ID of the default VPC, if available.
    """
    response = ec2_client.describe_vpcs(
        Filters=[
            {'Name': 'isDefault', 'Values': ['true']}
        ]
    )
    vpcs = response.get('Vpcs', [])
    if vpcs:
        log(f"Found default VPC: {vpcs[0].get('VpcId')}")
        return vpcs[0].get('VpcId')
    else:
        log("No default VPC found.", "error")
        return None

@error_handler
def get_image(image_url):
    """
    Downloads an image from a specified URL and saves it locally.

    Parameters:
    - image_url: The URL of the image to download.

    Returns the file path of the downloaded image.
    """
    response = requests.get(image_url)
    if response.status_code == 200:
        with open("logo.png", "wb") as f:
            f.write(response.content)

        log("Image downloaded successfully.")
        return "logo.png"
    else:
        log("Failed to download image.", "error")

@error_handler
def create_new_bucket(bucket_name, region=None):
    """
    Creates a new S3 bucket with a unique name.
    
    Parameters:
    - bucket_name: The base name for the bucket.
    - region: The AWS region to create the bucket in.
    
    Returns True on successful creation.
    """    
    if region is None:
        s3.create_bucket(Bucket=bucket_name)
    else:
        location = {'LocationConstraint': region}
        s3.create_bucket(Bucket=bucket_name,
                                CreateBucketConfiguration=location)
        
    s3_client.delete_public_access_block(Bucket=bucket_name)
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": ["s3:GetObject"],
            "Resource": f"arn:aws:s3:::{bucket_name}/*"
        }]   
    }

    configuration = {
        'ErrorDocument': {'Key': 'error.html'},
        'IndexDocument': {'Suffix': 'index.html'},
    }

    s3.Bucket(bucket_name).Policy().put(Policy=json.dumps(bucket_policy))
    s3.BucketWebsite(bucket_name).put(WebsiteConfiguration=configuration)   
        
    log(f"Bucket {bucket_name} created successfully.")

    return True

@error_handler
def get_html():
    """
    Generates an HTML page to be uploaded to the S3 bucket.

    Returns the file path of the generated HTML page.
    """
    page = f"""<!DOCTYPE html>
<html>
<head>
    <title>Waterford</title>
</head>
<body>
    <h1>Welcome to my DevOps Website</h1>
    <img src="logo.png" alt="Logo">
</body>
</html>
"""
    try:
        with open("index.html", "w") as f:
            f.write(page)

        log("HTML page generated successfully.")
        return "index.html"
    except Exception as e:
        log(f"Failed to generate HTML page: {e}", "error")

@error_handler
def get_txt_file(ec2_url, s3_url):
    """
    Writes a list of URLs to a text file.

    Parameters:
    - ec2_url: The URL of the EC2 instance.
    - s3_url: The URL of the S3 bucket.

    Returns the file path of the generated text file.
    """
    urls = f"EC2 Instance: {ec2_url}\nS3 Bucket: {s3_url}"
    try:
        with open("urls.txt", "w") as f:
            f.write(urls)
        log("URLs written to file successfully.")
        # Return the file path
        return "urls.txt"
    except Exception as e:
        log(f"Failed to write URLs to file: {e}", "error")
    
@error_handler
def get_latest_amazon_linux_ami(region):
    """
    Retrieves the latest Amazon Linux AMI ID using Systems Manager Parameter Store.

    Parameters:
    - region: The AWS region to search for the AMI.

    Returns the AMI ID of the latest Amazon Linux AMI.
    """
    ssm_client = boto3.client('ssm', region_name=region)
    parameter_name = '/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64'

    response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
    log(f"Retrieved latest Amazon Linux AMI ID: {response['Parameter']['Value']}")
    return response['Parameter']['Value']

@error_handler
def open_website(url, wait_time=5):
    """
    Opens a web browser to the specified url.

    Parameters:
    - url: The URL to open in the web browser.
    - wait_time: The time to wait between attempts to connect to the web server.

    Returns True if the web server is up and running.
    """
    while True:
        try:
            response = requests.get(f"{url}")
            log(f"Checking if web server is up at {url}...")
            if response.status_code == 200:
                log("Web server is up and running.")
                log(f"Opening web browser to {url}")
                webbrowser.open(f"{url}")
                return True
        except requests.ConnectionError:
            log(f"Error connecting to {url}.", "error")
            log(f"Web server not yet running, waiting {wait_time} seconds...")
            sleep(wait_time)

@error_handler
def upload_to_bucket(bucket_name, files):
    """
    Uploads a list of files to the specified S3 bucket with the correct MIME types.

    Parameters:
    - bucket_name: The name of the S3 bucket.
    - files: A list of file paths to upload.

    Returns True on successful upload.
    """
    for file_path in files:
        if file_path:  # Check if the file path is not None
            file_name = os.path.basename(file_path)
            content_type = ''

            if file_name.endswith('.html'):
                content_type = 'text/html'
            elif file_name.endswith('.txt'):
                content_type = 'text/plain'
            elif file_name.endswith('.png'):
                content_type = 'image/png'
            try:
                # Specify ContentType in the upload
                s3_client.upload_file(
                    Filename=file_path,
                    Bucket=bucket_name,
                    Key=file_name,
                    ExtraArgs={'ContentType': content_type} if content_type else None
                )
                log(f"Uploaded {file_name} to {bucket_name} successfully.")
            except ClientError as e:
                log(f"Failed to upload {file_name} to {bucket_name}: {e}", "error")

@error_handler
def url(string):
    """
    Creates a URL from a string.

    Parameters:
    - string: The string to convert to a URL.

    Returns a URL.
    """
    return f"http://{string}"

@error_handler
def generate_bucket_name(name):
    """
    Generates a unique name for an S3 bucket by appending random characters to the base name.
    
    Parameters:
    - name: The base name for the bucket.
    
    Returns a unique bucket name.
    """
    characters = string.ascii_lowercase + string.digits
    random_characters = ('').join([random.choice(characters) for i in range(6)])
    log(f"Generated unique bucket name: {random_characters}-{name}")
    return f"{random_characters}-{name}"

@error_handler
def check_credentials():
    """
    Checks if the AWS credentials are valid and not expired.
    """
    log("Checking AWS credentials...")
    try:
        session = boto3.Session()
        sts = session.client('sts')
        sts.get_caller_identity()
        log("AWS credentials are valid.")
    except ClientError as e:
        log(f"AWS credentials are invalid: Update your credentials with the latest details.", "error")
        exit(1)

@error_handler
def check_pem_key(key_name):
    """
    Checks if the pem key file exists and has the correct permissions.

    Parameters:
    - key_name: The name of the SSH key pair.

    Exits the script if the pem key file is not found or has incorrect permissions.
    """
    pem_file = f"{key_name}.pem"

    # Check if the file exists
    log(f"Checking for pem key file: {pem_file}")
    if not os.path.exists(pem_file):
        log(f"Pem key file {pem_file} not found.", "error")
        exit(1)

    # Check if the file has the correct permissions
    current_permissions = stat.S_IMODE(os.lstat(pem_file).st_mode)
    desired_permissions = stat.S_IRUSR | stat.S_IWUSR  # This is 0600

    # Compare current permissions with desired permissions
    if current_permissions != desired_permissions:
        log(f"Updating permissions of {pem_file} to 0600...")
        os.chmod(pem_file, desired_permissions)
        log("Permissions updated.")
    else:
        log(f"Permissions of {pem_file} are already set correctly.")

@error_handler
def ssh_interact(key_name, public_ip, user="ec2-user"):
    """
    Interacts with the SSH server on the EC2 instance to copy and execute monitoring.sh.

    Parameters:
    - key_name: The name of the SSH key pair.
    - public_ip: The public IP address of the EC2 instance.
    - user: The username to use for SSH authentication.

    Returns True on successful execution.
    """
    pem_file = f"{key_name}.pem"  # Ensure this path is correct and the file has appropriate permissions (chmod 400)
    
    log("Copying monitoring.sh to the EC2 instance...")
    try:
        subprocess.run(["scp", "-i", pem_file, "-o", "StrictHostKeyChecking=no",
                        "monitoring.sh", f"{user}@{public_ip}:~/"], check=True)
        log("monitoring.sh copied successfully.")
    except subprocess.CalledProcessError as e:
        log(f"Failed to copy monitoring.sh to the EC2 instance: {e}", "error")
        return  # Exit if copying fails

    log("Running monitoring.sh on the EC2 instance...")
    try:
        subprocess.run(["ssh", "-i", pem_file, "-o", "StrictHostKeyChecking=no",
                        f"{user}@{public_ip}", "chmod +x ~/monitoring.sh && ~/monitoring.sh"], check=True)
        log("monitoring.sh executed successfully.")
    except subprocess.CalledProcessError as e:
        log(f"Failed to execute monitoring.sh: {e}", "error")

if __name__ == '__main__':
    """
    Main entry point for the script.
    """
    cli.header()

    check_credentials()

    cli_used = cli.main()
    
    # If cli was not used, the following code will run
    if not cli_used:
        # Load the configuration
        config = load_configuration()

        # Check if a key name is specified, exit if not
        if not config['key_name']:
            log("No pem key name specified, exiting.", "error")
            exit(1)

        # Check if the pem key file exists and has the correct permissions
        check_pem_key(config['key_name'])

        # Set the instance type to a default value if not specified
        if not config['instance_type']:
            config['instance_type'] = "t2.nano"
        
        # Set the instance name to a default value if not specified
        if not config['instance_name']:
            config['instance_name'] = "Web Server"

        # Set the region to a default value if not specified
        if not config['region']:
            config['region'] = "eu-east-1"

        # Set the bucket seed to a default value if not specified
        if not config['bucket_seed']:
            config['bucket_seed'] = "devops-bucket"

        # AWS Service Clients
        ec2 = boto3.resource('ec2', region_name=config['region'])
        s3 = boto3.resource('s3', region_name=config['region'])
        ec2_client = boto3.client('ec2', region_name=config['region'])
        s3_client = boto3.client('s3', region_name=config['region'])

        config['user_data'] = generate_user_data()

        # Get the latest Amazon Linux AMI
        if not config['ami_id']:
            config['ami_id'] = get_latest_amazon_linux_ami(config['region'])

        vpc_id = get_default_vpc_id()

        if not vpc_id:
            log("Unable to retrieve a valid VPC ID, exiting.", "error")
            exit(1)

        if not config['security_group']:
            security_group_id = find_matching_sg(vpc_id)
            if not security_group_id:
                security_group_name = generate_unique_sg_name("NewLaunchWizard", vpc_id)
                config['security_group'] = create_security_group(vpc_id, group_name=security_group_name)
            else:
                config['security_group'] = security_group_id

        instance_ip = create_instance(**config)
        instance_url = url(instance_ip)

        if instance_ip:
            open_website(instance_url)

        bucket_name = generate_bucket_name(config['bucket_seed'])
        bucket = create_new_bucket(bucket_name)
        bucket_url = url(f"{bucket_name}.s3-website-{config['region']}.amazonaws.com")

        if bucket:
            image = get_image(config['image_url'])
            html = get_html()
            txt_file = get_txt_file(instance_url, bucket_url)
            upload_to_bucket(bucket_name, [image, html, txt_file])
            log(f"Bucket URL: {bucket_url}", "info")
            open_website(bucket_url)

        ssh_interact(config['key_name'], instance_ip)

        log("Script execution complete.")