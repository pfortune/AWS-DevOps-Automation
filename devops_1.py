import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import requests
import random
import string
import webbrowser

ec2 = boto3.resource('ec2')
ec2_client = boto3.client('ec2')

def generate_user_data():
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

def create_instance(ami_id, key_name, instance_name="Web Server", security_group=None, instance_type="t2.nano"):
    user_data = generate_user_data()

    try:
        security_group_id = get_security_group(security_group)

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
    except ClientError as e:
        print(f"An error occurred creating instance: {e}")

def get_security_group(security_group=None):
    # If a security group is provided, return it
    if security_group:
        return security_group

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
    response = ec2_client.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    for sg in response['SecurityGroups']:
        http_rules = [rule for rule in sg['IpPermissions'] if rule.get('FromPort') == 80 and rule.get('ToPort') == 80 and '0.0.0.0/0' in [ip['CidrIp'] for ip in rule.get('IpRanges', [])]]
        ssh_rules = [rule for rule in sg['IpPermissions'] if rule.get('FromPort') == 22 and rule.get('ToPort') == 22 and '0.0.0.0/0' in [ip['CidrIp'] for ip in rule.get('IpRanges', [])]]

        if http_rules and ssh_rules:
            return sg['GroupId']
    return None

# Function to generate a unique security group name
def generate_unique_sg_name(base_name, vpc_id):
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
    try:
        response = requests.get("http://devops.witdemo.net/logo.jpg")
        if response.status_code == 200:
            with open("logo.png", "wb") as f:
                f.write(response.content)
            print("Image downloaded successfully.")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred downloading the image: {e}")


if __name__ == '__main__':
    ami_id = "ami-0277155c3f0ab2930"
    key_name = "DesktopDevOps2023"
    create_instance(ami_id, key_name)