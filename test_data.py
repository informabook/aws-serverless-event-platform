import urllib.request
import json

# --- COLLE TON URL API CI-DESSOUS (Celle en bleu dans ton terminal) ---
API_URL = "https://xldzvsaush.execute-api.eu-west-1.amazonaws.com/prod/" 
# (J'ai recopié celle de ton screenshot, vérifie si c'est bien la même)

def add_concert(artist, date):
    data = {
        "artist": artist,
        "date": date
    }
    
    # Préparation de la requête POST
    req = urllib.request.Request(
        API_URL, 
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            print(f"✅ Ajouté : {artist} ({response.status})")
    except Exception as e:
        print(f"❌ Erreur pour {artist} : {e}")

# On ajoute 3 concerts
print("--- Remplissage de DynamoDB ---")
add_concert("Coldplay", "2025-06-20")
add_concert("Imagine Dragons", "2025-07-15")
add_concert("Dua Lipa", "2025-09-10")