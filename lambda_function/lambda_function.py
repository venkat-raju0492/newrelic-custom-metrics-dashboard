import boto3
import requests
import time
from datetime import datetime, timedelta
import logging
import os
import traceback
import json
import base64
from botocore.exceptions import ClientError

logs_client = boto3.client('logs')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_secret(secret_name):
    """Retrieve a secret from AWS Secrets Manager."""
    region_name = os.environ.get('AWS_REGION', 'us-west-2')

    # Create a Secrets Manager client
    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logger.error(f"Error retrieving secret: {e}")
        raise e

    # Decrypts secret using the associated KMS key.
    if 'SecretString' in get_secret_value_response:
        secret = get_secret_value_response['SecretString']
    else:
        secret = base64.b64decode(get_secret_value_response['SecretBinary'])

    return secret

def execute_cloudwatch_query(logGrpName,query,startTimeMs,endTimeMs):
    """Executes a CloudWatch Logs Insights query and returns the query ID."""
    logger.info("execute_cloudwatch_query called, for Query ::"+query)    
    try:
        response = logs_client.start_query(
            logGroupName=logGrpName,  # Replace with your log group name
            startTime=startTimeMs,  # Example: Query last hour (adjust as needed)
            endTime=endTimeMs,
            queryString=query
        )
        query_id = response['queryId']
        logger.info(f"Query started with ID: {query_id}")  # Keep this for Lambda logs
        return query_id
    except Exception as e:
        logger.info(f"Error starting query: {e}")  # Keep this for Lambda logs
        return None

def extract_query_results(query_id,metric_name):
    """Retrieves and extracts results from a CloudWatch Logs Insights query."""
    logger.info("extract_query_results called, for queryId::"+query_id)
    if query_id is None:
        return None

    try:
        results = None
        while results is None or results['status'] != 'Complete':
            time.sleep(5)  # Adjust sleep time as needed
            results = logs_client.get_query_results(queryId=query_id)
            logger.info(f"Query status: {json.dumps(results)}") # Keep this for Lambda logs

        if results['status'] == 'Complete':
            field_value_dict  = {}
            new_relic_resp_list = []
            for result_list in results['results']:
                for result_dict in result_list:
                    field = result_dict.get('field')
                    value = result_dict.get('value')
                    if field and value:
                        field_value_dict[field] = value 

                # Send data to new relic    
                timestamp = int(datetime.strptime(field_value_dict["eventTimestamp"], '%Y-%m-%d %H:%M:%S.%f').timestamp()*1000)
                connector_count = int(field_value_dict["metricValue"])
                new_relic_response = send_metric_to_newrelic(metric_name,timestamp,connector_count)
                logger.info(f"new_relic_response==> {json.dumps(new_relic_response)}")                        
                new_relic_resp_list.append(new_relic_response)
            return new_relic_resp_list
        else:
            logger.info(f"Query did not complete successfully. Status: {json.dumps(results['status'])}, metric_name={metric_name}") # Keep this for Lambda logs
            return None

    except Exception as e:
        logger.error(f"Error getting query results: {e}, metric_name={metric_name} ")  # Keep this for Lambda logs
        traceback.print_exc()  # Prints the full traceback
        return None

def send_metric_to_newrelic(metric_name,data_timestamp_millis,metric_val):
    """
    Sends a metric to New Relic using the provided API key and data.

    Args:
        None

    Returns:
        The response from the New Relic API.
    """

    url = "https://metric-api.newrelic.com/metric/v1"
    secret_name = os.environ.get('NEW_RELIC_SECRET_NAME', 'New_Relic_License')  # Replace with your actual secret name
    api_key = get_secret(secret_name)

    headers = {
        "Content-Type": "application/json",
        "Api-Key": api_key
    }
    data = [
        {
            "metrics": [
                {
                    "name": metric_name,
                    "type": "gauge",
                    "value": metric_val,
                    "timestamp": data_timestamp_millis,
                    "interval.ms": 30000
                }
            ]
        }
    ]

    try:
        logger.info("Sending data to metrics==>"+json.dumps(data))
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.info(f"Error sending metric to New Relic: {e}")
        return None

def lambda_handler(event, context):
    """AWS Lambda handler function."""

    # Initialize the logger
    request_id = context.aws_request_id

    # # Create a custom log formatter
    # formatter = logging.Formatter(f"[{request_id}] %(asctime)s - %(levelname)s - %(message)s") 
    # for handler in logger.handlers:
    #     handler.setFormatter(formatter)

    # Log messages with the request ID
    logger.info("Starting function execution.")

    # Set start and end time for hourly lambda
    startTimeMs = int((datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)).timestamp()*1000)
    endTimeMs = int(datetime.now().replace(minute=0, second=0, microsecond=0).timestamp()*1000)
    queryMetricList = event.get('queryMetricList')  # Get the query from the event payload
    lambda_response = []
    for queryMetric in queryMetricList:
        query = queryMetric.get('query')
        metricName = queryMetric.get('metricName')
        logGroupName = queryMetric.get('logGrpName')
   
        if not query:
            return {
                'statusCode': 400,
                'body': 'Error: "query" parameter is missing in the event.'
            }

        query_id = execute_cloudwatch_query(logGroupName,query,startTimeMs,endTimeMs)

        if query_id:
            query_data = extract_query_results(query_id,metricName)
    
            if query_data or query_data==[]:
                lambda_response.append({
                    'statusCode': 200,
                    'body': {'results': query_data} # Return the results
                })
            else:
                logger.error(f"Error: Failed to retrieve query results==>{json.dumps(lambda_response)}")
                return {
                    'statusCode': 500,
                    'body': 'Error: Failed to retrieve query results.'
                }
        else:
            logger.error("Error: Failed to start CloudWatch query==>{json.dumps(lambda_response)}")
            return {
                'statusCode': 500,
                'body': 'Error: Failed to start CloudWatch query.'
            }
    return lambda_respons