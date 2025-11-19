import json
import boto3
import os

# Client SNS
sns = boto3.client('sns')
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

def handler(event, context):
    print("📨 Worker activé via SQS")
    
    for record in event['Records']:
        try:
            # 1. On lit le message venant de la queue SQS
            payload = json.loads(record['body'])
            order_id = payload.get('order_id')
            email_client = payload.get('email')
            artist = payload.get('artist', 'Concert') # On pourrait passer l'artiste aussi
            
            # 2. On prépare le message pour l'email
            message_body = (
                f"Bonjour,\n\n"
                f"Votre commande a bien été reçue !\n"
                f"Numéro de commande : {order_id}\n"
                f"Email client renseigné : {email_client}\n\n"
                f"Merci d'utiliser GlobalEvent."
            )
            
            # 3. ENVOI RÉEL VIA SNS
           # response = sns.publish(
           #     TopicArn=SNS_TOPIC_ARN,
            #    Subject=f"GlobalEvent - Confirmation Commande {order_id}",
             #   Message=message_body
            #)
            
            #print(f"✅ Email envoyé via SNS ! MessageId: {response['MessageId']}")
            
        except Exception as e:
            print(f"❌ Erreur dans le worker : {str(e)}")
            raise e # On lève l'erreur pour que SQS réessaie plus tard si ça plante
            
    return {"status": "success"}