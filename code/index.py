from __future__ import print_function

import json
import urllib
import boto3
import datetime
import os

max_runtime = int(os.environ['max_runtime'])
# Available methods: stop or terminate, anything else means only notification
method = os.environ['method']
sns_topic = os.environ['sns_topic']

client = boto3.client('ec2')


def lambda_handler(event, context):
    try:
        response = client.describe_instances(
            Filters=[
                {
                    'Name': 'key-name',
                    'Values': [
                        'packer_*'
                    ]
                },
                {
                    'Name': 'instance-state-name',
                    'Values': [
                        'running',
                    ]
                },
            ]
        )
        instances_to_terminate = []
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                launchTime = instance["LaunchTime"]
                tz_info = launchTime.tzinfo
                now = datetime.datetime.now(tz_info)
                delta = datetime.timedelta(hours=max_runtime)
                the_past = now - delta
                # If the instance was launched more than the max_runtime ago,
                # get rid of it
                if the_past > instance["LaunchTime"]:
                    instances_to_terminate.append(instance["InstanceId"])

        if len(instances_to_terminate) > 0:
            print("These instances were running too long: ")
            print(instances_to_terminate)
            # Decide how to handle the instances
            if method == "stop":
                client.stop_instances(
                    InstanceIds=instances_to_terminate
                )
            elif method == "terminate":
                client.terminate_instances(
                    InstanceIds=instances_to_terminate
                )
            # Send an SNS message if the topic is defined
            if sns_topic != "":
                send_sns(instances_to_terminate)
    except Exception as e:
        print(e)
        raise e


def send_sns(instances):
    snsclient = boto3.client("sns")
    message = "The following instances were running too long:"
    for instance in instances:
        message += "\n* " + instance
    if method == "stop":
        message += "\n\nThey have been stopped"
    if method == "terminate":
        message += "\n\nThe have been terminated"
    snsclient.publish(TopicArn=sns_topic,
                      Message=message,
                      Subject="Packer instances running too long")
