import streamlit as st
import requests
import pandas as pd
import numpy as np
from apify_client import ApifyClient

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="InvestImmo Bot PRO", 
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
    except Exception as e:
        st.error(f"Erreur de connexion DVF : {e}")
        return 0

def fetch_real_data_ahmed(api_token, ville, budget_max):
    """Exécution du scraper Ahmed Hrid sur Apify"""
    if not api_token:
        st.warning("⚠️ Token Apify manquant dans la barre latérale.")
        return []
    
    client = ApifyClient(api_token)
    
    # Configuration précise pour l'acteur ahmed_hrid/leboncoin-immobilier-scraper
    run_input = {
        "location": ville,
        "category": "immobilier",
        "max_price": int(budget_max),
        "limit": 10,
        "sort": "time",
        "with_description": True
    }
    
    try:
        with st.spinner("🚀 Le robot interroge Leboncoin..."):
            # Lancement de l'acteur
            run = client.actor("ahmed_hrid/leboncoin-immobilier-scraper").call(run_input=run_input)
            
            listings = []
            # Extraction des données du Dataset
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                # Extraction sécurisée de la surface (square) dans les attributs
                attr = item.get("attributes", {})
                surface = attr.get("square") if isinstance(attr, dict) else item.get("square", 0)
                
                listings.append({
                    "id": item.get("id", "N/A"),
                    "titre": item.get("title", "Appartement"),
                    "prix": item.get("price", 0),
                    "surface": surface if surface else 0,
                    "image": item.get("images", ["https://via.placeholder.com/400"])[0] if item.get("images") else "https://via.placeholder.com/400",
                    "url": item.get("url", "https://www.leboncoin.fr"),
                    "description": item.get("description", "Aucune description")
                })
            return listings
    except Exception as e:
        st.error(f"❌ Erreur Apify : {str(e)}")
        return []

# --- INTERFACE STREAMLIT ---

st.title("🤖 InvestImmo Bot PRO")
st.markdown("---")

with st.sidebar:
    st.header("🔑 Authentification")
    apify_token = st.text_input("Apify API Token", type="password")
    
    st.header("🔍 Paramètres")
    ville_nom = st.text_input("Ville cible", "Versailles")
    budget_max = st.number_input("Budget Max (€)", value=600000, step=10000)
    
    st.divider()
    lancer = st.button("🚀 Lancer l'analyse réelle", use_container_width=True)

if lancer:
    # 1. Validation de la ville via API Géo
    geo_res = requests.get(f"https://geo.api.gouv.fr/communes?nom={ville_nom}&fields=code,population").json()
    
    if geo_res:
        ville_data = geo_res[0]
        code_insee = ville_data['code']
        population = ville_data.get('population', 0)
        
        # 2. Analyse Prix du Marché
        prix_m2_moyen = get_dvf_prices_dynamic(code_insee)
        
        st.header(f"📍 Marché : {ville_data['nom']} ({code_insee})")
        
        col1, col2 = st.columns(2)
        col1.metric("Population", f"{population:,} hab.")
        col2.metric("Prix m² Moyen DVF", f"{prix_m2_moyen} €" if prix_m2_moyen > 0 else "Données DVF indisponibles")

        # 3. Scraping Live
        st.divider()
        st.subheader("🔎 Annonces détectées en temps réel")
        
        annonces = fetch_real_data_ahmed(apify_token, ville_nom, budget_max)
        
        if not annonces:
            st.info("Aucune annonce trouvée. Vérifiez vos crédits Apify ou vos critères.")
        else:
            for ann in annonces:
                # Calcul de la décote
                p_m2_ann = round(ann['prix'] / ann['surface']) if ann['surface'] and ann['surface'] > 0 else 0
                
                with st.container(border=True):
                    c_img, c_desc = st.columns([1, 2])
                    
                    with c_img:
                        st.image(ann['image'], width='stretch')
                    
                    with c_desc:
                        st.write(f"### {ann['titre']}")
                        st.write(f"💰 **{ann['prix']:,} €** | 📐 **{ann['surface']} m²**")
                        
                        if p_m2_ann > 0:
                            st.write(f"Prix au m² : {p_m2_ann} €")
                            if prix_m2_moyen > 0 and p_m2_ann < prix_m2_moyen:
                                decote = round(((prix_m2_moyen - p_m2_ann) / prix_m2_moyen) * 100)
                                st.success(f"🔥 SOUS-COTÉ : -{decote}% par rapport au marché")
                        
                        with st.expander("Lire la description"):
                            st.write(ann['description'])
                            
                        st.link_button("🌐 Voir l'annonce sur Leboncoin", ann['url'], use_container_width=True)
    else:
        st.error("Ville non trouvée par l'API Géo.")
else:
    st.info("Entrez votre Token Apify et une ville, puis cliquez sur le bouton pour démarrer.")
