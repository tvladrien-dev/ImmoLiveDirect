import streamlit as st
import requests
import pandas as pd
import numpy as np
from apify_client import ApifyClient

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="InvestImmo Bot PRO", layout="wide")

# --- FONCTION SCRAPER SPÉCIFIQUE (Ahmed Hrid) ---

def fetch_leboncoin_real_data(api_token, ville, budget_max):
    """Connexion directe à l'acteur ahmed_hrid/leboncoin-immobilier-scraper"""
    if not api_token:
        st.error("❌ Token Apify manquant.")
        return []
    
    client = ApifyClient(api_token)
    
    # Configuration selon la documentation de l'acteur ahmed_hrid
    run_input = {
        "location": ville,
        "category": "immobilier",
        "max_price": int(budget_max),
        "limit": 5, # On limite pour économiser tes crédits gratuits
        "sort": "time" # Plus récents en premier
    }
    
    try:
        with st.spinner(f"🔍 Recherche des meilleures opportunités à {ville}..."):
            # Appel de l'acteur spécifique
            run = client.actor("ahmed_hrid/leboncoin-immobilier-scraper").call(run_input=run_input)
            
            listings = []
            # Parcours des résultats
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                # On adapte les clés aux données renvoyées par Ahmed Hrid
                listings.append({
                    "titre": item.get("title", "Appartement"),
                    "prix": item.get("price", 0),
                    # On cherche la surface dans les attributs spécifiques
                    "surface": item.get("attributes", {}).get("square", 0) or item.get("square", 0),
                    "image": item.get("images", ["https://via.placeholder.com/400"])[0],
                    "url": item.get("url", "https://www.leboncoin.fr"),
                    "id": item.get("id", "N/A")
                })
            return listings
    except Exception as e:
        st.error(f"⚠️ Erreur lors du scraping : {str(e)}")
        return []

# --- ANALYSE PRIX DVF ---

def get_dvf_market_price(code_insee):
    """Prix moyen réel basé sur les ventes Notaires"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        res = requests.get(url, timeout=10).json()
        df = pd.DataFrame([f['properties'] for f in res['features']])
        df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
        df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
        df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
        df = df[df['surface_reelle_bati'] > 0]
        if not df.empty:
            return round((df['valeur_fonciere'] / df['surface_reelle_bati']).mean())
    except:
        pass
    return 0

# --- INTERFACE ---
st.title("🚀 Investisseur Immo : Données Live")

with st.sidebar:
    st.header("🔑 Accès")
    token = st.text_input("Apify Token", type="password")
    ville = st.text_input("Ville cible", "Versailles")
    budget = st.number_input("Budget Max (€)", value=400000)
    rechercher = st.button("Lancer l'analyse réelle", use_container_width=True)

if rechercher:
    # 1. Obtenir les infos Géo
    geo = requests.get(f"https://geo.api.gouv.fr/communes?nom={ville}&fields=code,population").json()
    
    if geo:
        v_data = geo[0]
        code_insee = v_data['code']
        st.subheader(f"📊 État du marché à {v_data['nom']} ({v_data['population']:,} hab.)")
        
        # Prix marché réel
        prix_marche = get_dvf_market_price(code_insee)
        if prix_marche > 0:
            st.metric("Prix m² Moyen (DVF)", f"{prix_marche} €")
        
        # 2. Lancer le scraper d'Ahmed Hrid
        annonces = fetch_leboncoin_real_data(token, ville, budget)
        
        if annonces:
            st.divider()
            for a in annonces:
                p_m2_a = round(a['prix'] / a['surface']) if a['surface'] > 0 else 0
                
                with st.container(border=True):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.image(a['image'], width='stretch')
                    with c2:
                        st.write(f"### {a['titre']}")
                        st.write(f"💰 **{a['prix']:,} €** | 📏 **{a['surface']} m²**")
                        
                        # Calcul de l'opportunité
                        if prix_marche > 0 and p_m2_a > 0:
                            if p_m2_a < prix_marche:
                                eco = round(((prix_marche - p_m2_a) / prix_marche) * 100)
                                st.success(f"🔥 Pépite : -{eco}% sous le prix marché ({p_m2_a}€/m²)")
                            else:
                                st.info(f"Prix : {p_m2_a}€/m² (Dans la moyenne)")
                        
                        st.link_button("Ouvrir sur Leboncoin", a['url'], use_container_width=True)
        else:
            st.warning("Aucune annonce trouvée. Vérifiez votre crédit Apify.")
    else:
        st.error("Ville non reconnue.")
