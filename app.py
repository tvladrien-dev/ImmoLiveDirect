import streamlit as st
import requests
import pandas as pd
import numpy as np
from apify_client import ApifyClient

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="InvestImmo Bot PRO - Live", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- FONCTIONS TECHNIQUES ---

def get_dvf_prices_dynamic(code_insee):
    """Calcule le prix m2 moyen réel sur les dernières ventes enregistrées (API cquest)"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        res = requests.get(url, timeout=15).json()
        if "features" in res and len(res["features"]) > 0:
            df = pd.DataFrame([f['properties'] for f in res['features']])
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            
            if not df.empty:
                df['price_m2'] = df['valeur_fonciere'] / df['surface_reelle_bati']
                return round(df['price_m2'].mean())
        return 0
    except Exception:
        return 0

def fetch_leboncoin_data(api_token, ville, budget_max):
    """Configuration et récupération via l'Actor OiU5ThXkp3gfs8fhG avec mapping flexible"""
    if not api_token:
        st.error("❌ Token Apify manquant.")
        return []
    
    client = ApifyClient(api_token)
    
    # Input tel qu'exécuté avec succès dans tes logs
    run_input = {
        "category": "9",
        "immo_sell_type": "all",
        "location": ville,
        "real_estate_type": "all",
        "max_price": int(budget_max),
        "maxItems": 15,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
            "apifyProxyCountry": "FR"
        }
    }
    
    try:
        with st.spinner(f"🚀 Récupération des résultats pour {ville}..."):
            run = client.actor("OiU5ThXkp3gfs8fhG").call(run_input=run_input)
            
            listings = []
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                
                # --- MAPPING FLEXIBLE DES DONNÉES (POUR ÉVITER LES 'N/A') ---
                
                # 1. Gestion du Prix (certains acteurs renvoient des centimes ou des listes)
                raw_price = item.get("price")
                price = 0
                if isinstance(raw_price, list) and len(raw_price) > 0:
                    price = raw_price[0]
                elif isinstance(raw_price, (int, float)):
                    price = raw_price
                
                # 2. Gestion de la Surface (Clé critique)
                attr = item.get("attributes", {})
                surface = 0
                if isinstance(attr, dict):
                    # Cherche 'square', 'm2', 'surface' dans les attributs
                    surface = attr.get("square") or attr.get("m2") or attr.get("surface") or 0
                if not surface:
                    surface = item.get("square") or item.get("surface") or 0
                
                # 3. Gestion de l'Image
                img_list = item.get("images", [])
                image_url = img_list[0] if img_list else "https://via.placeholder.com/400"

                listings.append({
                    "id": item.get("id", "N/A"),
                    "titre": item.get("title") or item.get("subject") or "Annonce Immobilière",
                    "prix": int(price),
                    "surface": float(surface),
                    "image": image_url,
                    "url": item.get("url", "https://www.leboncoin.fr"),
                    "description": item.get("description", "Pas de description.")
                })
            return listings
    except Exception as e:
        st.error(f"❌ Erreur lors de la lecture des données : {str(e)}")
        return []

# --- INTERFACE UTILISATEUR ---

st.title("🤖 InvestImmo Bot PRO : Analyse Directe")
st.markdown("---")

with st.sidebar:
    st.header("🔑 Configuration")
    apify_token = st.text_input("Apify API Token", type="password")
    
    st.header("🔍 Critères")
    ville_nom = st.text_input("Ville cible", "Versailles")
    budget_max = st.number_input("Budget Max (€)", value=500000, step=10000)
    
    st.divider()
    lancer = st.button("🚀 Lancer l'analyse réelle", use_container_width=True)

if lancer:
    # 1. Recherche Code INSEE
    geo_res = requests.get(f"https://geo.api.gouv.fr/communes?nom={ville_nom}&fields=code,population").json()
    
    if geo_res:
        ville_data = geo_res[0]
        code_insee = ville_data['code']
        
        # 2. Prix Marché DVF
        prix_m2_moyen = get_dvf_prices_dynamic(code_insee)
        
        st.header(f"📍 Marché : {ville_data['nom']} ({code_insee})")
        st.metric("Prix m² Moyen (Historique DVF)", f"{prix_m2_moyen} €" if prix_m2_moyen > 0 else "Indisponible")

        # 3. Affichage Annonces
        st.divider()
        annonces = fetch_leboncoin_data(apify_token, ville_nom, budget_max)
        
        if annonces:
            for ann in annonces:
                # Calcul de la décote
                p_m2_ann = round(ann['prix'] / ann['surface']) if ann['surface'] > 0 else 0
                
                with st.container(border=True):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.image(ann['image'], use_container_width=True)
                    with c2:
                        st.subheader(ann['titre'])
                        st.write(f"💰 **{ann['prix']:,} €** | 📐 **{ann['surface']} m²**")
                        
                        if p_m2_ann > 0:
                            st.write(f"Prix au m² de l'annonce : **{p_m2_ann} €**")
                            if prix_m2_moyen > 0 and p_m2_ann < prix_m2_moyen:
                                decote = round(((prix_m2_moyen - p_m2_ann) / prix_m2_moyen) * 100)
                                st.success(f"🔥 OPPORTUNITÉ : -{decote}% sous le prix marché")
                            else:
                                st.info("Prix conforme au secteur.")
                        
                        with st.expander("📝 Lire la description"):
                            st.write(ann['description'])
                            
                        st.link_button("🔗 Voir sur Leboncoin", ann['url'], use_container_width=True)
        else:
            st.warning("Annonces extraites mais illisibles ou vides. Vérifiez le format de sortie de l'Actor.")
    else:
        st.error("Ville non trouvée.")
else:
    st.info("Saisissez vos paramètres et cliquez sur 'Lancer'.")
