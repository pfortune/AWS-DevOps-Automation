import boto3

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

def create_instance(instance_name, ami_id, key_name, security_group = None, instance_type="t2.nano"):
    user_data = generate_user_data()

    if not security_group:
        security_group_id = create_security_group()
        if security_group_id is None:
            print("Failed to create security group, exiting.")
            return
    else:
        security_group_id = security_group

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

def create_security_group(group_name="NewLaunchWizard", description="Allows access to HTTP and SSH ports"):
    # Get the default VPC ID
    vpc_id = get_default_vpc_id()
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

if __name__ == '__main__':
    ami_id = "ami-0277155c3f0ab2930"
    key_name = "DesktopDevOps2023" 
    instance_name = "Web Server"
    create_instance(instance_name, ami_id, key_name)