# Standard Library Imports
import logging
import requests
import random
import string
from time import sleep
import webbrowser
import configparser

# Third Party Imports
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# AWS Service Clients
ec2 = boto3.resource('ec2', region_name='us-east-1')
s3 = boto3.resource('s3')
ec2_client = boto3.client('ec2', region_name='us-east-1')

# Load configuration
print("Loading configuration...")
config = configparser.ConfigParser()
config.read('config.ini')

key_name = config['AWS']['key_name'] or None
ami_id = config['EC2']['ami_id'] or None
instance_type = config['EC2']['instance_type'] or "t2.nano"
security_group = config['EC2']['security_group'] or None
image_url = config['S3']['image_url'] or None


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

def create_instance(key_name, instance_name, security_group, ami_id, instance_type):
    """
    Creates an EC2 instance with specified parameters.
    
    Parameters:
    - key_name: The name of the key pair for SSH access.
    - instance_name: The name tag for the instance.
    - security_group: The security group ID to assign to the instance.
    - ami_id: The AMI ID for the instance's OS.
    - instance_type: The type of instance to launch.
    
    Returns the public IP address of the created instance.
    """
    
    user_data = generate_user_data()

    try:
        security_group_id = security_group or get_security_group()
        ami_id = ami_id or get_latest_amazon_linux_ami()

        created_instances = ec2.create_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            UserData=user_data,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': instance_name
                        },
                    ]
                },
            ]
        )

        instance = created_instances[0]
        print("Waiting for the instance to enter running state...")
        instance.wait_until_running()  # Wait for the instance to be ready
        instance.reload()
        print(f"Instance running, Public IP: {instance.public_ip_address}")
        return instance.public_ip_address
    except ClientError as e:
        logging.error(e)
        print(f"An error occured creating instance: {e}")
    except NoCredentialsError as e:
        print(f"An error occured with your credentials: {e}")

def get_security_group():
    """
    Retrieves an existing security group that matches specified criteria or creates a new one.
    
    Returns the ID of the security group.
    """

    # Get the default VPC ID
    vpc_id = get_default_vpc_id()
    if not vpc_id:
        print("Unable to retrieve a valid VPC ID, exiting.")
        return None

    # Check for an existing security group that matches the criteria
    security_group_id = find_matching_sg(vpc_id)
    if security_group_id:
        print(f"Found matching security group {security_group_id}, using it.")
    else:
        # Create a new security group if none found
        security_group_id = create_security_group(vpc_id=vpc_id)
        if security_group_id is None:
            print("Failed to create security group, exiting.")
            return None

    return security_group_id

def create_security_group(vpc_id, group_name="NewLaunchWizard", description="Allows access to HTTP and SSH ports"):
    """
    Creates a new security group in the specified VPC.
    
    Parameters:
    - vpc_id: The ID of the VPC where the security group will be created.
    - group_name: The name of the security group.
    - description: A description of the security group's purpose.
    
    Returns the ID of the created security group.
    """
    
    # Check if the security group name already exists
    group_name = generate_unique_sg_name(group_name, vpc_id)
    
    # Create the security group
    sg = ec2.create_security_group(GroupName=group_name, Description=description, VpcId=vpc_id)
    print(f"Security Group Created: {sg.id}")

    # Add inbound rules
    sg.authorize_ingress(
        IpPermissions=[
            # HTTP access
            {'FromPort': 80, 'ToPort': 80, 'IpProtocol': 'tcp', 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            # SSH access
            {'FromPort': 22, 'ToPort': 22, 'IpProtocol': 'tcp', 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        ]
    )
    print("Inbound rules added for HTTP and SSH.")

    return sg.id

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

# Function to generate a unique security group name
def generate_unique_sg_name(base_name: str, vpc_id: str) -> str:
    """
    Generates a unique name for a security group within a VPC.
    
    Parameters:
    - base_name: The base name for the security group.
    - vpc_id: The ID of the VPC.
    
    Returns a unique security group name.
    """

    unique_name = base_name
    attempt = 0
    while True:
        existing_sgs = ec2_client.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}, {'Name': 'group-name', 'Values': [unique_name]}])
        if not existing_sgs['SecurityGroups']:
            # If no existing SG matches the unique_name, it's unique
            break
        attempt += 1
        unique_name = f"{base_name}-{random.choice(string.ascii_lowercase)}{attempt}"
    return unique_name

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
        print("No default VPC found.")
        return None

def get_image():
    """
    Downloads an image from a specified URL and saves it locally.
    
    The URL is taken from the 'image_url' configuration variable.
    """

    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            with open("logo.png", "wb") as f:
                f.write(response.content)
            print("Image downloaded successfully.")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred downloading the image: {e}")

def get_buckets():
    pass

def create_new_bucket(bucket_name, region=None):
    """
    Creates a new S3 bucket with a unique name.
    
    Parameters:
    - bucket_name: The base name for the bucket.
    - region: The AWS region to create the bucket in.
    
    Returns True on successful creation.
    """

    new_bucket_name = generate_bucket_name(bucket_name)
    try:
        if region is None:
            s3.create_bucket(Bucket=new_bucket_name)
        else:
            location = {'LocationConstraint': region}
            s3.create_bucket(Bucket=new_bucket_name,
                                    CreateBucketConfiguration=location)
        print(f"Bucket {new_bucket_name} created successfully.")
    except ClientError as e:
        logging.error(e)
        print(f"An error occured creating instance: {e}")
    return True

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
        print(f"Latest Amazon Linux AMI ID: {latest_ami['ImageId']}")
        return latest_ami['ImageId']
    else:
        print("Couldn't find the latest Amazon Linux AMI. Try adjusting your filters!")


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
    instance_ip = create_instance()
    print(f"Instance IP: {instance_ip}")
    print("Waiting for web server to be ready...")
    sleep(10)
    while True:
        try:
            r = requests.get(f"http://{instance_ip}")
            if r.status_code == 200:
                print("Web server is up and running.")
                print(f"Opening web browser to http://{instance_ip}")
                webbrowser.open(f"http://{instance_ip}")
                break
        except requests.ConnectionError:
            print("Web server not yet running, waiting 5 seconds...")
            sleep(5)

    create_new_bucket("peterf")