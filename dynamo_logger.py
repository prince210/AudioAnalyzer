import datetime
import os
import traceback
import uuid
import boto3
from botocore.exceptions import ClientError

STAGE_NAME = "AudioAnalyzer"

LOGS_TABLE_NAME = "Logs"
ABSTRACT_LOGS_TABLE_NAME = "AbstractLogs"

from botocore.config import Config

def get_dynamodb_resource():
    """
    Returns a boto3 DynamoDB resource configured for local or AWS production environment.
    Uses fast connection timeouts locally to ensure zero latency when local DynamoDB is offline.
    """
    use_local = os.getenv("USE_LOCAL_DYNAMODB", "true").lower() in ("true", "1", "yes")
    endpoint_url = os.getenv("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")

    if use_local:
        # Fast 1-second timeout so API never hangs if local DynamoDB is not running
        fast_config = Config(connect_timeout=1, read_timeout=1, retries={'max_attempts': 0})
        return boto3.resource(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "dummy"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "dummy"),
            config=fast_config
        )
    else:
        # AWS Production DynamoDB
        region = os.getenv("AWS_REGION", "us-east-1")
        return boto3.resource("dynamodb", region_name=region)



def ensure_tables_exist():
    """
    Checks if 'Logs' and 'AbstractLogs' tables exist and creates them if missing.
    """
    try:
        dynamodb = get_dynamodb_resource()
        existing_tables = [table.name for table in dynamodb.tables.all()]

        # 1. Ensure Logs Table
        if LOGS_TABLE_NAME not in existing_tables:
            print(f"[DynamoDB] Creating table '{LOGS_TABLE_NAME}'...")
            dynamodb.create_table(
                TableName=LOGS_TABLE_NAME,
                KeySchema=[
                    {"AttributeName": "log_id", "KeyType": "HASH"}
                ],
                AttributeDefinitions=[
                    {"AttributeName": "log_id", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST"
            )
            print(f"[DynamoDB] Table '{LOGS_TABLE_NAME}' created successfully.")

        # 2. Ensure AbstractLogs Table
        if ABSTRACT_LOGS_TABLE_NAME not in existing_tables:
            print(f"[DynamoDB] Creating table '{ABSTRACT_LOGS_TABLE_NAME}'...")
            dynamodb.create_table(
                TableName=ABSTRACT_LOGS_TABLE_NAME,
                KeySchema=[
                    {"AttributeName": "abstract_log_id", "KeyType": "HASH"}
                ],
                AttributeDefinitions=[
                    {"AttributeName": "abstract_log_id", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST"
            )
            print(f"[DynamoDB] Table '{ABSTRACT_LOGS_TABLE_NAME}' created successfully.")

    except Exception as e:
        print(f"[DynamoDB Warning] Unable to ensure tables exist: {e}")


def log_technical(stage: str, step: str, level: str, message: str, details: str = ""):
    """
    Logs technical & debugging info into the 'Logs' DynamoDB table.
    """
    try:
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(LOGS_TABLE_NAME)
        log_entry = {
            "log_id": str(uuid.uuid4()),
            "stage": stage,
            "step": step,
            "level": level.upper(),
            "message": message,
            "details": str(details) if details else "",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
        table.put_item(Item=log_entry)
    except Exception as e:
        print(f"[DynamoDB Log Error] Failed to write to {LOGS_TABLE_NAME}: {e}")


def log_abstract(stage: str, step: str, status: str, user_message: str, metadata: dict = None, execution_id: str = ""):
    """
    Logs execution flow state into the 'AbstractLogs' DynamoDB table for user-facing status.
    """
    try:
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(ABSTRACT_LOGS_TABLE_NAME)
        log_id = str(uuid.uuid4())
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        log_entry = {
            "log_id": log_id,
            "abstract_log_id": log_id,  # Primary key for AbstractLogs
            "stage": stage,
            "step": step,
            "status": status.upper(),
            "user_message": user_message,
            "metadata": str(metadata) if metadata else "{}",
            "execution_id": execution_id,
            "timestamp": timestamp
        }
        table.put_item(Item=log_entry)
        return log_entry
    except Exception as e:
        print(f"[DynamoDB Log Error] Failed to write to {ABSTRACT_LOGS_TABLE_NAME}: {e}")
        return {
            "log_id": str(uuid.uuid4()),
            "abstract_log_id": str(uuid.uuid4()),
            "stage": stage,
            "step": step,
            "status": status.upper(),
            "user_message": user_message,
            "metadata": str(metadata) if metadata else "{}",
            "execution_id": execution_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
