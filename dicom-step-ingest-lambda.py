import json
import boto3
import os

stepfunctions = boto3.client('stepfunctions')

def lambda_handler(event, context):
    # Get the object from the event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    
    # Get State Machine ARN from environment variable
    state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
    
    if not state_machine_arn:
        error_msg = "STATE_MACHINE_ARN environment variable is not set"
        print(error_msg)
        raise ValueError(error_msg)
    
    # Start Step Functions execution
    response = stepfunctions.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps({
            'bucket': bucket,
            'key': key
        })
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps('Step Function execution started!')
    }
