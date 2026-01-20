import streamlit as st
import requests
import pandas as pd
import numpy as np
from apify_client import ApifyClient

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="InvestImmo Bot PRO - Version Intégrale", 
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
            # Nettoyage et conversion stricte
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
    """
    Exécution du scraper via l'ID OiU5ThXkp3gfs8fhG
    Configuration exacte basée sur l'input utilisateur fourni
    """
    if not api_token:
        st.error("❌ Token Apify manquant dans la barre latérale.")
        return []
    
    client = ApifyClient(api_token)
    
    # Input exact correspondant à la documentation de l'Actor OiU5ThXkp3gfs8fhG
    run_input = {
        "category": "9",
        "immo_sell_type": "all",
        "location": ville,
        "real_estate_type": "all",
        "max_price": int(budget_max),
        "maxItems": 10,  # Limité pour économiser vos crédits
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
            "apifyProxyCountry": "FR"
        }
    }
    
    try:
        with st.spinner(f"🚀 Scraping en cours sur Leboncoin (Proxy Résidentiel)..."):
            # Appel de l'Actor par son ID unique
            run = client.actor("OiU5ThXkp3gfs8fhG").call(run_input=run_input)
            
            listings = []
            # Extraction des résultats depuis le dataset de l'exécution
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                # On cherche la surface dans les attributs ou à la racine
                attr = item.get("attributes", {})
                surface = attr.get("square") if isinstance(attr, dict) else item.get("square", 0)
                
                listings.append({
                    "id": item.get("id", "N/A"),
                    "titre": item.get("title", "Appartement"),
                    "prix": item.get("price", 0),
                    "surface": surface if surface else 0,
                    "image": item.get("images", ["https://via.placeholder.com/400"])[0] if item.get("images") else "https://via.placeholder.com/400",
                    "url": item.get("url", "https://www.leboncoin.fr"),
                    "description": item.get("description", "Aucune description disponible.")
                })
            return listings
    except Exception as e:
        st.error(f"❌ Erreur Apify : {str(e)}")
        return []

# --- INTERFACE UTILISATEUR ---

st.title("🤖 InvestImmo Bot PRO")
st.markdown("---")

with st.sidebar:
    st.header("🔑 Configuration")
    apify_token = st.text_input("Apify API Token", type="password", help="Récupérez-le dans Settings > Integrations sur Apify")
    
    st.header("🔍 Paramètres de Recherche")
    ville_cible = st.text_input("Ville cible", "Versailles")
    budget_max = st.number_input("Budget Maximum (€)", value=500000, step=10000)
    
    st.divider()
    lancer = st.button("🚀 Lancer l'analyse en direct", use_container_width=True)

if lancer:
    # 1. Validation de la ville et récupération des données Géo
    geo_url = f"https://geo.api.gouv.fr/communes?nom={ville_cible}&fields=code,population,centre"
    geo_res = requests.get(geo_url).json()
    
    if geo_res:
        ville_data = geo_res[0]
        code_insee = ville_data['code']
        population = ville_data.get('population', 0)
        
        # 2. Analyse des prix du marché réel (DVF)
        with st.spinner("Analyse du marché local (DVF)..."):
            prix_m2_moyen = get_dvf_prices_dynamic(code_insee)
        
        st.header(f"📍 Marché : {ville_data['nom']} ({code_insee})")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Population", f"{population:,} hab.")
        c2.metric("Prix m² Moyen DVF", f"{prix_m2_moyen} €" if prix_m2_moyen > 0 else "Indisponible")
        c3.metric("ID Actor", "OiU5ThXkp3gfs8fhG")

        # 3. Scraping des annonces réelles
        st.divider()
        st.subheader("🔎 Annonces détectées en temps réel")
        
        annonces = fetch_leboncoin_data(apify_token, ville_cible, budget_max)
        
        if not annonces:
            st.info("Aucune annonce trouvée. Vérifiez votre budget ou vos crédits Apify.")
        else:
            for ann in annonces:
                # Calcul de la décote potentielle
                p_m2_ann = round(ann['prix'] / ann['surface']) if ann['surface'] and ann['surface'] > 0 else 0
                
                with st.container(border=True):
                    col_img, col_txt = st.columns([1, 2])
                    
                    with col_img:
                        st.image(ann['image'], width='stretch')
                    
                    with col_txt:
                        st.write(f"### {ann['titre']}")
                        st.write(f"💰 **{ann['prix']:,} €** | 📐 **{ann['surface']} m²**")
                        
                        if p_m2_ann > 0:
                            st.write(f"Prix au m² : **{p_m2_ann} €**")
                            if prix_m2_moyen > 0 and p_m2_ann < prix_m2_moyen:
                                decote = round(((prix_m2_moyen - p_m2_ann) / prix_m2_moyen) * 100)
                                st.success(f"🔥 AFFAIRE DÉTECTÉE : -{decote}% par rapport au marché local")
                            else:
                                st.info("Le prix est conforme aux moyennes du secteur.")
                        
                        with st.expander("📝 Voir la description"):
                            st.write(ann['description'])
                            
                        st.link_button("🌐 Voir l'annonce sur Leboncoin", ann['url'], use_container_width=True)
    else:
        st.error("Ville non trouvée par l'API Géo. Vérifiez l'orthographe.")
else:
    st.info("Configurez vos accès et cliquez sur 'Lancer' pour démarrer l'analyse.")
