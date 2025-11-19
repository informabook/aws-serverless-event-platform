import json
import boto3
import os
import uuid
import psycopg2
from botocore.exceptions import ClientError # Pour gérer les erreurs DynamoDB

# Initialisation
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')
sqs = boto3.client('sqs')

# Variables
TABLE_NAME = os.environ['TABLE_NAME']
DB_SECRET_NAME = os.environ['DB_SECRET_NAME']
QUEUE_URL = os.environ['QUEUE_URL']
table = dynamodb.Table(TABLE_NAME)

def create_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(body, default=str)
    }

def get_db_connection():
    secret_response = secrets_client.get_secret_value(SecretId=DB_SECRET_NAME)
    secret = json.loads(secret_response['SecretString'])
    return psycopg2.connect(
        host=secret['host'], database=secret['dbname'],
        user=secret['username'], password=secret['password']
    )

def init_db_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id VARCHAR(50) PRIMARY KEY,
                event_id VARCHAR(50),
                user_email VARCHAR(100),
                amount DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

def handler(event, context):
    print("Event:", json.dumps(event))
    method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')

    # 1. LISTE DES CONCERTS
    if method == 'GET':
        try:
            response = table.scan()
            return create_response(200, {'concerts': response.get('Items', [])})
        except Exception as e:
            return create_response(500, {'error': str(e)})

    # 2. ACHAT
    elif method == 'POST' and 'buy' in path:
        try:
            body = json.loads(event.get('body', '{}'))
            event_id = body.get('event_id')
            email = body.get('email', 'client@test.com')
            
            # A. D'ABORD : On essaie de décrémenter le stock dans DynamoDB
            # Si tickets_left <= 0, ça plante et on annule tout.
            try:
                table.update_item(
                    Key={'event_id': event_id},
                    UpdateExpression="set tickets_left = tickets_left - :val",
                    ConditionExpression="tickets_left > :zero", # Vérifie qu'il reste des places
                    ExpressionAttributeValues={
                        ':val': 1,
                        ':zero': 0
                    },
                    ReturnValues="UPDATED_NEW"
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    return create_response(400, {'message': 'Désolé, concert complet ! 😱'})
                raise e

            # B. ENSUITE : On enregistre la commande SQL
            conn = get_db_connection()
            init_db_table(conn)
            
            order_id = str(uuid.uuid4())
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO orders (order_id, event_id, user_email, amount) VALUES (%s, %s, %s, %s)",
                    (order_id, event_id, email, 49.99)
                )
                conn.commit()
            conn.close()

            # C. ENFIN : On notifie SQS
            message = {
                "order_id": order_id,
                "email": email,
                "type": "CONFIRMATION_EMAIL"
            }
            sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message))

            return create_response(201, {
                'message': 'Achat validé ! Place décomptée.', 
                'order_id': order_id
            })
            
        except Exception as e:
            print(f"Erreur: {str(e)}")
            return create_response(500, {'error': str(e)})

    return create_response(404, {'message': 'Not Found'})