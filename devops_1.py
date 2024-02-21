#!/usr/bin/env python3

# TODO: Write URLs to File
# TODO: Upload to Bucket
# TODO: SSH Interactions
# TODO: Enhance monitoring.sh
# TODO: Flesh out Logging

# Standard Library Imports
import logging
import requests
import random
import string
import subprocess
import json
from time import sleep
import webbrowser
import configparser

# Third Party Imports
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ParamValidationError

# Logging Configuration
logging.basicConfig(filename='devops.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# AWS Service Clients
ec2 = boto3.resource('ec2', region_name='us-east-1')
s3 = boto3.resource('s3', region_name='us-east-1')
ec2_client = boto3.client('ec2', region_name='us-east-1')
s3_client = boto3.client('s3', region_name='us-east-1')

def error_handler(func):
    """
    A decorator that handles common AWS errors and exceptions.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NoCredentialsError:
            print("No AWS credentials found. Please configure your credentials.")
            logging.error("No AWS credentials found. Please configure your credentials.")
            exit(1)
        except ClientError as e:
            print(f"An error occurred: {e}")
            logging.error(f"An error occurred: {e}")
        except ParamValidationError as e:
            print(f"Invalid parameters: {e}") 
            logging.error(f"Invalid parameters: {e}")
        except TypeError as e:
            print(f"Invalid type: {e}")
            logging.error(f"Invalid type: {e}")
        except ImportError as e:
            print(f"Import error: {e}")
            logging.error(f"Import error: {e}")
    return wrapper

def log(message, level="info"):
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "error":
        logging.error(message)

def load_configuration(config_path='config.ini'):
    """
    Loads the configuration from the specified file.
    """
    log("Loading configuration...")
    config = configparser.ConfigParser()
    config.read(config_path)

    return config['DEFAULT']

def generate_user_data():
    """
    Generates a user data script for EC2 instance initialization.
    This script updates the system, installs and starts Apache HTTP Server,
    and creates a custom index.html page with the instance's metadata.
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
# Create a custom index.html
cat <<EOF > /var/www/html/index.html
<html>
<body>
<h1>Hello from Waterford</h1>
<p>Instance ID: $INSTANCE_ID</p>
<p>Instance Type: $INSTANCE_TYPE</p>
<p>Availability Zone: $AVAILABILITY_ZONE</p>
</body>
</html>
EOF
"""
    return user_data

@error_handler
def create_instance(**config):
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
        ImageId=config['ami_id'],
        InstanceType=config['instance_type'],
        MinCount=1,
        MaxCount=1,
        KeyName=config['key_name'],
        SecurityGroupIds=[config['security_group']],
        UserData=config['user_data'],
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': config['instance_name']
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
        return vpcs[0].get('VpcId')
    else:
        log("No default VPC found.")
        return None

@error_handler
def get_image(image_url):
    """
    Downloads an image from a specified URL and saves it locally.
    
    The URL is taken from the 'image_url' configuration variable.
    """
    response = requests.get(image_url)
    if response.status_code == 200:
        with open("logo.png", "wb") as f:
            f.write(response.content)
        log("Image downloaded successfully.")
    else:
        log("Failed to download image.")

@error_handler
def get_buckets():
    """
    Retrieves a list of all S3 buckets in the account.
    
    Returns a list of bucket names.
    """
    buckets = [bucket.name for bucket in s3.buckets.all()]
    log(f"Found {len(buckets)} buckets: {', '.join(buckets)}")
    return buckets

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

    return bucket_name

@error_handler
def get_latest_amazon_linux_ami():
    """
    Retrieves the latest Amazon Linux AMI ID available for use.
    
    Returns the AMI ID.
    """
    filters = [
        {
            'Name': 'name',
            'Values': ['amzn2-ami-hvm-*-x86_64-gp2']
        },
        {
            'Name': 'state',
            'Values': ['available']
        },
        {
            'Name': 'architecture',
            'Values': ['x86_64']
        }
    ]

    # Fetch the latest Amazon Linux AMI
    amis = ec2_client.describe_images(Owners=['amazon'], Filters=filters)

    # Sort by creation date
    amis['Images'].sort(key=lambda x: x['CreationDate'], reverse=True)

    if amis['Images']:
        latest_ami = amis['Images'][0]
        log(f"Retrieved the latest Amazon Linux AMI ID: {latest_ami['ImageId']}")
        return latest_ami['ImageId']
    else:
        log("Couldn't find the latest Amazon Linux AMI. Try adjusting your filters!")
        return None

def open_website(instance_ip, wait_time=5):
    """
    Opens a web browser to the specified instance's public IP address.

    Parameters:
    - instance_ip: The public IP address of the instance.
    - wait_time: The time to wait between attempts to connect to the web server.

    Returns True if the web server is up and running.
    """
    while True:
        try:
            response = requests.get(f"http://{instance_ip}")
            if response.status_code == 200:
                log("Web server is up and running.")
                log(f"Opening web browser to http://{instance_ip}")
                webbrowser.open(f"http://{instance_ip}")
                return True
        except requests.ConnectionError:
            log(f"Web server not yet running, waiting {wait_time} seconds...")
            sleep(wait_time)

def generate_bucket_name(name):
    """
    Generates a unique name for an S3 bucket by appending random characters to the base name.
    
    Parameters:
    - name: The base name for the bucket.
    
    Returns a unique bucket name.
    """
    characters = string.ascii_lowercase + string.digits
    random_characters = ('').join([random.choice(characters) for i in range(6)])
    return f"{name}-{random_characters}"

if __name__ == '__main__':
    config = load_configuration()
    config['user_data'] = generate_user_data()

    # Get the latest Amazon Linux AMI
    if not config['ami_id']:
        config['ami_id'] = get_latest_amazon_linux_ami()

    vpc_id = get_default_vpc_id()

    if not vpc_id:
        log("Unable to retrieve a valid VPC ID, exiting.")
        exit(1)

    if not config['security_group']:
        security_group_id = find_matching_sg(vpc_id)
        log(f"Matching security group found: {security_group_id}")
        if not security_group_id:
            security_group_name = generate_unique_sg_name("NewLaunchWizard", vpc_id)
            config['security_group'] = create_security_group(vpc_id, group_name=security_group_name)
        else:
            config['security_group'] = security_group_id

    instance_ip = create_instance(**config)
    bucket_name = generate_bucket_name(config['bucket_seed'])

    create_new_bucket(bucket_name)
    if instance_ip:
        open_website(instance_ip)