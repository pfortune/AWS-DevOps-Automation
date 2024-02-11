import boto3

ec2 = boto3.resource('ec2')

def generate_user_data():
    user_data = """#!/bin/bash
        yum update -y
        yum install -y httpd
        systemctl start httpd.service
        systemctl enable httpd.service
        # Fetch instance metadata
        INSTANCE_ID=$(curl http://169.254.169.254/latest/meta-data/instance-id)
        INSTANCE_TYPE=$(curl http://169.254.169.254/latest/meta-data/instance-type)
        AVAILABILITY_ZONE=$(curl http://169.254.169.254/latest/meta-data/placement/availability-zone)
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

def create_instance(instance_name, ami_id, key_name, security_group, instance_type="t2.nano"):
    user_data = generate_user_data()

    created_instances = ec2.create_instances(
        ImageId=ami_id,
        InstanceType=instance_type,
        MinCount=1,
        MaxCount=1,
        KeyName=key_name,
        SecurityGroupIds=[security_group],
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


if __name__ == '__main__':
    ami_id = "ami-0277155c3f0ab2930"
    key_name = "DesktopDevOps2023"
    security_group = "sg-00e70907b799fcdc6"
    instance_name = "Web Server"
    create_instance(instance_name, ami_id, key_name, security_group)