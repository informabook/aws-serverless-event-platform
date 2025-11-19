import urllib.request
import json

# --- REMETS TON URL API ICI ---
API_URL = "https://xldzvsaush.execute-api.eu-west-1.amazonaws.com/prod/"
# (Vérifie bien que c'est la bonne URL de ton dernier déploiement)

def buy_ticket():
    print("1. Récupération d'un concert...")
    try:
        # On fait un GET pour avoir un ID valide
        with urllib.request.urlopen(API_URL) as response:
            data = json.loads(response.read().decode())
            concerts = data.get('concerts', [])
            
            if not concerts:
                print("❌ Aucun concert trouvé dans DynamoDB ! Lance test_data.py d'abord.")
                return

            concert = concerts[0]
            event_id = concert['event_id']
            artist = concert['artist']
            print(f"✅ Concert trouvé : {artist} (ID: {event_id})")

    except Exception as e:
        print(f"❌ Erreur connexion API: {e}")
        return

    print("\n2. Tentative d'achat (Connexion SQL)...")
    # On prépare la commande
    buy_url = API_URL + "buy" # L'URL devient .../prod/buy
    payload = {
        "event_id": event_id,
        "email": "etudiant.aws@test.com"
    }
    
    req = urllib.request.Request(
        buy_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f"🎉 SUCCÈS ! {result['message']}")
            print(f"🧾 Numéro de commande SQL : {result['order_id']}")
    except urllib.error.HTTPError as e:
        print(f"❌ Erreur API ({e.code}) : {e.read().decode()}")
    except Exception as e:
        print(f"❌ Erreur Script : {e}")

if __name__ == "__main__":
    buy_ticket()