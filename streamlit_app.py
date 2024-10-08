import streamlit as st
import boto3
import json
from botocore.exceptions import ClientError

# Initialize Streamlit app
st.title("CloudWatch Log Analyzer")

# Create a session client for CloudWatch Logs
session = boto3.Session(
    aws_access_key_id=st.secrets.aws.aws_access_key_id,
    aws_secret_access_key=st.secrets.aws.aws_secret_access_key,
    region_name='us-east-1'
)

# Get the list of available regions with CloudWatch Logs access
available_regions = []
logs_client = session.client('logs')
try:
    response = logs_client.describe_log_groups()
    available_regions = [region for region in session.get_available_regions('logs')]
except ClientError as e:
    st.error(f"Error retrieving available regions: {e}")

# Set the default region to us-east-1 if available, otherwise use the first available region
default_region = 'us-east-1' if 'us-east-1' in available_regions else available_regions[0] if available_regions else None

# Create a dropdown menu for selecting the region
if available_regions:
    selected_region = st.selectbox("Select a region", available_regions, index=available_regions.index(default_region) if default_region else 0)

    # Create a client for CloudWatch Logs in the selected region
    logs_client = session.client('logs', region_name=selected_region)

# Get a list of log groups in the selected region
try:
    log_groups = logs_client.describe_log_groups()['logGroups']
except ClientError as e:
    st.error(f"Error retrieving log groups in {selected_region}: {e}")
    log_groups = []

# Check if log groups are available
if not log_groups:
    st.warning(f"No logs available in {selected_region}, please select another region.")
else:
    # Create a dropdown menu for selecting the log group
    selected_log_group = st.selectbox("Select a log group", [log_group['logGroupName'] for log_group in log_groups])

    # Get a list of log streams in the selected log group
    try:
        log_streams = logs_client.describe_log_streams(logGroupName=selected_log_group)['logStreams']
    except ClientError as e:
        st.error(f"Error retrieving log streams in {selected_region}/{selected_log_group}: {e}")
        log_streams = []

    # Check if log streams are available
    if not log_streams:
        st.warning(f"No log streams available in {selected_region}/{selected_log_group}, please select another log group.")
    else:
        # Create a dropdown menu for selecting the log stream
        selected_log_stream = st.selectbox("Select a log stream", [log_stream['logStreamName'] for log_stream in log_streams])

# Get the contents of the selected log stream
try:
    log_stream_data = logs_client.get_log_events(
        logGroupName=selected_log_group,
        logStreamName=selected_log_stream
    )
except ClientError as e:
    st.error(f"Error retrieving log events in {selected_region}/{selected_log_group}/{selected_log_stream}: {e}")
else:
    # Concatenate the log event messages into a single string
    prompt_data = ''.join([event['message'] + '\n' for event in log_stream_data['events']])

    # Create a Bedrock Runtime client
    bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-west-2")

    def summarize_article(prompt_data):
        try:
            prompt_config = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"You are a AWS log expert working with the AWS Cloud. Review the log data I am providing for AWS and explain and summarize in detail what you see, and if you have any recommendations on rules that could be configured based on what you see in the log data, please tell me.\n\n {prompt_data}"
                            }
                        ]
                    }
                ]
            }
            body = json.dumps(prompt_config)
            modelId = "anthropic.claude-3-sonnet-20240229-v1:0"
            contentType = "application/json"
            accept = "application/json"
            response = bedrock.invoke_model(
                modelId=modelId,
                contentType=contentType,
                accept=accept,
                body=body
            )
            response_body = json.loads(response.get("body").read())
            summary = response_body.get("content")[0]["text"]
            return summary
        except Exception as e:
            st.error(f"An error occurred with the Bedrock Runtime API: {e}")
            return None

    # Display the log data and LLM response on the Streamlit page
    st.markdown("**Log Data:**")
    st.code(prompt_data, language="text")
    response = summarize_article(prompt_data)
    if response:
        st.markdown("**Recommendations:**")
        st.write(response)
    else:
      st.warning("No regions available with CloudWatch Logs access.")

