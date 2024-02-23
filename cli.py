import fire
import boto3
import sys
from botocore.exceptions import ClientError
from error_logging import error_handler, log
import datetime

cloudwatch = boto3.client('cloudwatch')
ec2 = boto3.resource('ec2')
s3 = boto3.resource('s3')

@error_handler
def running_instances():
    """
    Retrieves all running EC2 instances.
    """
    instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    for instance in instances:
        log(f"Instance ID: {instance.id}, Public IP: {instance.public_ip_address}, State: {instance.state['Name']}")

@error_handler
def terminate_instance(instance):
    """
    Terminates a specific EC2 instance.
    """
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
    for bucket in s3.buckets.all():
        log(f"Bucket: {bucket.name}, Created: {bucket.creation_date}, Region: {bucket.meta.client.meta.region_name}")

@error_handler
def delete_all_buckets():
    """
    Deletes all S3 buckets with error handling.
    """
    for bucket in s3.buckets.all():
        try:
            log(f"Deleted bucket: {bucket.name}")
            bucket.objects.all().delete()
            bucket.delete()
        except ClientError as e:
            log(f"Failed to delete bucket {bucket.name}: {e}", "error")

@error_handler
def list_metrics(instance_id):
    """
    List available CloudWatch metrics for a specified EC2 instance.
    """
    metrics = cloudwatch.list_metrics(
        Namespace='AWS/EC2',
        Dimensions=[
            {
                'Name': 'InstanceId',
                'Value': instance_id
            }
        ]
    )
    for metric in metrics['Metrics']:
        print(metric['MetricName'])

@error_handler
def get_metric_data(instance_id, metric_name, period='1h'):
    """
    Retrieve and display specific metric data for an EC2 instance for the last 1 hour, 8 hours, or 24 hours.

    Parameters:
    - instance_id: The ID of the EC2 instance.
    - metric_name: The name of the CloudWatch metric.
    - period: The time period to retrieve data for ('1h', '8h', '24h').
    """
    period_mapping = {
        '1h': 3600,
        '8h': 28800,
        '24h': 86400,
    }

    # Calculate StartTime and EndTime
    end_time = datetime.datetime.utcnow()
    start_time = end_time - datetime.timedelta(seconds=period_mapping.get(period, 3600))
    
    if period == '1h':
        granularity = 300  # 5 minutes
    elif period == '8h':
        granularity = 1800  # 30 minutes
    else:  # '24h'
        granularity = 3600  # 1 hour

    response = cloudwatch.get_metric_statistics(
        Namespace='AWS/EC2',
        MetricName=metric_name,
        Dimensions=[
            {
                'Name': 'InstanceId',
                'Value': instance_id
            }
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=granularity,
        Statistics=['Average']
    )

    if response['Datapoints']:
        for point in sorted(response['Datapoints'], key=lambda x: x['Timestamp']):
            log(f"Time: {point['Timestamp']}, Average: {point['Average']} {point['Unit']}")
    else:
        log(f"No data available for {metric_name} in the last {period}.")


@error_handler
def create_alarm(alarm_name, metric_name, instance_id, threshold, comparison_operator='GreaterThanThreshold', evaluation_periods=1, period=300, statistic='Average'):
    """
    Create a CloudWatch alarm based on specified parameters.
    """
    cloudwatch.put_metric_alarm(
        AlarmName=alarm_name,
        ComparisonOperator=comparison_operator,
        EvaluationPeriods=evaluation_periods,
        MetricName=metric_name,
        Namespace='AWS/EC2',
        Period=period,
        Statistic=statistic,
        Threshold=float(threshold),
        ActionsEnabled=False,
        AlarmDescription="Alarm created by CLI",
        Dimensions=[
            {
                'Name': 'InstanceId',
                'Value': instance_id
            }
        ]
    )
    print(f"Alarm {alarm_name} created.")

@error_handler
def delete_alarm(alarm_name):
    """
    Delete a specified CloudWatch alarm.
    """
    cloudwatch.delete_alarms(
        AlarmNames=[alarm_name]
    )
    log(f"Alarm {alarm_name} deleted.")

def cloudwatch_command(subcommand, **kwargs):
    """
    Route CloudWatch CLI commands to the appropriate function.
    
    Subcommands:
        metrics --instance_id <instance_id>
            Retrieve and display basic CloudWatch metrics for a specified EC2 instance.

        list_metrics --instance_id <instance_id>
            List available CloudWatch metrics for a specified EC2 instance.

        get_metric_data --instance_id <instance_id> --metric_name <metric_name>
            Retrieve and display specific metric data for an EC2 instance.
            
        create_alarm --alarm_name <name> --metric_name <metric_name> --instance_id <instance_id> --threshold <threshold> [...additional flags]
            Create a CloudWatch alarm based on specified parameters.
            
        delete_alarm --alarm_name <name>
            Delete a specified CloudWatch alarm.
    """
    if subcommand == 'list_metrics':
        list_metrics(**kwargs)
    elif subcommand == 'get_metric_data':
        get_metric_data(**kwargs)
    elif subcommand == 'create_alarm':
        create_alarm(**kwargs)
    elif subcommand == 'delete_alarm':
        delete_alarm(**kwargs)
    elif subcommand == 'metrics':
        cloudwatch_metrics(**kwargs)
    else:
        log(f"Invalid CloudWatch subcommand: {subcommand}", "error")

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
            "cloudwatch": cloudwatch_command,
        })

        return True