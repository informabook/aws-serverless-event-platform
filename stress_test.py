import requests
import concurrent.futures
import time
import random

# --- CONFIGURATION ---
# Remplace par ton URL d'API (avec le / à la fin)
API_URL = "https://xldzvsaush.execute-api.eu-west-1.amazonaws.com/prod/"
TOTAL_REQUESTS = 200   # Nombre total d'achats à tenter
CONCURRENCY = 10       # Nombre d'utilisateurs simultanés

def get_valid_event():
    """Récupère un ID de concert valide pour le test"""
    try:
        response = requests.get(API_URL)
        data = response.json()
        if 'concerts' in data and len(data['concerts']) > 0:
            # On prend le premier concert disponible
            return data['concerts'][0]
        return None
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des concerts: {e}")
        return None

def buy_ticket(session_id, event_id, artist):
    """Simule un achat pour un utilisateur"""
    endpoint = API_URL + "buy"
    payload = {
        "event_id": event_id,
        "email": f"stress_test_{session_id}@robot.com"
    }
    
    start_time = time.time()
    try:
        response = requests.post(endpoint, json=payload, timeout=10)
        duration = time.time() - start_time
        
        if response.status_code == 201:
            return "SUCCESS", duration
        elif response.status_code == 400:
            return "SOLD_OUT", duration
        else:
            return f"ERROR_{response.status_code}", duration
            
    except Exception as e:
        return "TIMEOUT/FAIL", time.time() - start_time

def run_stress_test():
    print(f"🔥 Démarrage du Stress Test : {TOTAL_REQUESTS} requêtes avec {CONCURRENCY} threads.")
    
    # 1. Récupérer un concert
    concert = get_valid_event()
    if not concert:
        print("❌ Impossible de trouver un concert. Arrêt.")
        return

    print(f"🎯 Cible : {concert['artist']} (ID: {concert['event_id']}) - Places restantes avant test : {concert['tickets_left']}")
    print("--- Lancement de l'attaque ---")

    results = {"SUCCESS": 0, "SOLD_OUT": 0, "ERRORS": 0}
    times = []

    # 2. Exécution parallèle
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = []
        for i in range(TOTAL_REQUESTS):
            futures.append(executor.submit(buy_ticket, i, concert['event_id'], concert['artist']))

        # Récupération des résultats au fur et à mesure
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            status, duration = future.result()
            times.append(duration)
            
            if status == "SUCCESS":
                results["SUCCESS"] += 1
                print("✅", end="", flush=True)
            elif status == "SOLD_OUT":
                results["SOLD_OUT"] += 1
                print("⛔", end="", flush=True) # Concert complet
            else:
                results["ERRORS"] += 1
                print("❌", end="", flush=True)

            # Retour à la ligne tous les 50
            if (i + 1) % 50 == 0:
                print()

    # 3. Rapport
    avg_time = sum(times) / len(times) if times else 0
    print("\n\n--- 📊 RAPPORT FINAL ---")
    print(f"Commandes validées (Money in the bank 💰) : {results['SUCCESS']}")
    print(f"Refus 'Concert Complet' (Logique respectée 🛡️) : {results['SOLD_OUT']}")
    print(f"Erreurs Techniques (Crashes 💥) : {results['ERRORS']}")
    print(f"Temps moyen par requête : {avg_time:.3f} secondes")

if __name__ == "__main__":
    run_stress_test()