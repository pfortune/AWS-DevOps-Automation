import fire
import boto3
import sys
from botocore.exceptions import ClientError
from error_logging import error_handler, log
import datetime

@error_handler
def running_instances():
    """
    Retrieves all running EC2 instances.
    """
    ec2 = boto3.resource('ec2')
    instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    for instance in instances:
        log(f"Instance ID: {instance.id}, Public IP: {instance.public_ip_address}, State: {instance.state['Name']}")

@error_handler
def terminate_instance(instance):
    """
    Terminates a specific EC2 instance.
    """
    ec2 = boto3.resource('ec2')
    instance = ec2.Instance(instance)
    try:
        log(f"Terminating instance {instance.id}...")
        instance.terminate()
    except ClientError as e:
        log(f"Failed to terminate instance {instance.id}: {e}", "error")

@error_handler
def terminate_all_instances():
    """
    Terminates all running EC2 instances.
    """
    ec2 = boto3.resource('ec2')
    instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    for instance in instances:
        try:
            log(f"Terminating instance {instance.id}...")
            instance.terminate()
        except ClientError as e:
            log(f"Failed to terminate instance {instance.id}: {e}", "error")

@error_handler
def get_buckets():
    """
    Retrieves all S3 buckets.
    """
    s3 = boto3.resource('s3')
    for bucket in s3.buckets.all():
        log(f"Bucket: {bucket.name}, Created: {bucket.creation_date}, Region: {bucket.meta.client.meta.region_name}")

@error_handler
def delete_all_buckets():
    """
    Deletes all S3 buckets with error handling.
    """
    s3 = boto3.resource('s3')
    for bucket in s3.buckets.all():
        try:
            log(f"Deleted bucket: {bucket.name}")
            bucket.objects.all().delete()
            bucket.delete()
        except ClientError as e:
            log(f"Failed to delete bucket {bucket.name}: {e}", "error")

@error_handler
def cloudwatch_metrics(instance_id):
    """
    Retrieves and logs basic CloudWatch metrics for a specified EC2 instance.
    Formats and prints a summary of the metrics.
    """
    cloudwatch = boto3.client('cloudwatch')
    metrics = ['CPUUtilization', 'DiskReadOps', 'DiskWriteOps']  # Example metrics
    log(f"CloudWatch Metrics for instance: {instance_id}")
    for metric in metrics:
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName=metric,
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=datetime.datetime.utcnow() - datetime.timedelta(seconds=3600),
            EndTime=datetime.datetime.utcnow(),
            Period=300,
            Statistics=['Average']
        )
        if response['Datapoints']:
            # Sort the datapoints by Timestamp to get the latest
            latest_datapoint = sorted(response['Datapoints'], key=lambda x: x['Timestamp'], reverse=True)[0]
            log(f"{metric}: Average {latest_datapoint['Average']} {latest_datapoint['Unit']} (Last hour)")
        else:
            log(f"{metric}: No data available", "warning")

def main():
    if len(sys.argv) > 1:
        fire.Fire({
            "instances": running_instances,
            "terminate": terminate_instance,
            "terminate_all": terminate_all_instances,
            "buckets": get_buckets,
            "delete_buckets": delete_all_buckets,
            "cloudwatch": cloudwatch_metrics,
        })

        return True