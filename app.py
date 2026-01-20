import streamlit as st
import requests
import pandas as pd
import numpy as np
from apify_client import ApifyClient

# --- CONFIGURATION STRICTE DE LA PAGE ---
st.set_page_config(
    page_title="InvestImmo Bot PRO - Live Scraping", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- MOTEUR DE CALCUL PRIX MARCHÉ (DVF RÉEL) ---

def get_dvf_prices_dynamic(code_insee):
    """Extraction et analyse statistique des transactions réelles de la commune"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        res = requests.get(url, timeout=15).json()
        if "features" in res and len(res["features"]) > 0:
            df = pd.DataFrame([f['properties'] for f in res['features']])
            # Conversion forcée en numérique pour les calculs
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            # Nettoyage des données aberrantes ou vides
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            
            if not df.empty:
                # Calcul du prix moyen au m2 pondéré
                df['price_m2'] = df['valeur_fonciere'] / df['surface_reelle_bati']
                return round(df['price_m2'].mean())
        return 0
    except Exception as e:
        st.sidebar.error(f"Erreur DVF : {e}")
        return 0

# --- MOTEUR DE SCRAPING LIVE (AHMED HRID) ---

def fetch_real_data_leboncoin(api_token, ville, budget_max):
    """Lancement du scraper ahmed_hrid et extraction des champs immobiliers"""
    if not api_token:
        return []
    
    client = ApifyClient(api_token)
    
    # Paramètres d'entrée spécifiques à l'acteur ahmed_hrid/leboncoin-immobilier-scraper
    run_input = {
        "location": ville,
        "category": "immobilier",
        "max_price": int(budget_max),
        "limit": 10,
        "sort": "time",
        "with_description": True
    }
    
    try:
        # Appel synchrone à l'API Apify
        run = client.actor("ahmed_hrid/leboncoin-immobilier-scraper").call(run_input=run_input)
        
        listings = []
        # Extraction depuis le Dataset généré par le scraper
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            # Extraction de la surface (souvent nichée dans les attributs chez Ahmed Hrid)
            surface = 0
            if "attributes" in item and isinstance(item["attributes"], dict):
                surface = item["attributes"].get("square", 0)
            elif "square" in item:
                surface = item["square"]
            
            listings.append({
                "id": item.get("id", "N/A"),
                "titre": item.get("title", "Appartement"),
                "prix": item.get("price", 0),
                "surface": surface,
                "image": item.get("images", ["https://via.placeholder.com/400"])[0] if item.get("images") else "https://via.placeholder.com/400",
                "url": item.get("url", "https://www.leboncoin.fr"),
                "description": item.get("description", "")
            })
        return listings
    except Exception as e:
        st.error(f"Erreur lors de l'exécution du scraper : {e}")
        return []

# --- INTERFACE UTILISATEUR ---

st.title("🏘️ Analyseur de Marché Immobilier Haute Précision")
st.markdown("---")

# Barre latérale technique
with st.sidebar:
    st.header("🔑 Paramètres de Connexion")
    apify_token = st.text_input("Apify API Token", type="password")
    
    st.header("🎯 Cible de Recherche")
    ville_input = st.text_input("Ville exacte (ex: Lyon 06)", "Versailles")
    budget_input = st.number_input("Budget Maximum (€)", value=500000, step=5000)
    
    st.divider()
    lancer_recherche = st.button("🚀 Lancer l'Analyse en Direct", use_container_width=True)

# Logique principale après clic
if lancer_recherche:
    if not apify_token:
        st.error("Veuillez renseigner votre Token Apify dans la barre latérale.")
    else:
        # 1. Identification Géo et Population (API GOUV)
        geo_url = f"https://geo.api.gouv.fr/communes?nom={ville_input}&fields=code,population,centre"
        geo_data = requests.get(geo_url).json()
        
        if geo_data:
            ville_info = geo_data[0]
            code_insee = ville_info['code']
            population = ville_info.get('population', 0)
            
            # 2. Analyse Comparative (DVF)
            with st.spinner("Calcul des prix du marché réel..."):
                prix_m2_moyen = get_dvf_prices_dynamic(code_insee)
            
            st.header(f"📍 Rapport pour {ville_info['nom']} ({code_insee})")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Population", f"{population:,} hab.")
            c2.metric("Prix m² Marché (Ventes réelles)", f"{prix_m2_moyen} €" if prix_m2_moyen > 0 else "Indisponible")
            c3.metric("Acteur Scraper", "Ahmed Hrid (LBC)")

            # 3. Scraping Live avec Ahmed Hrid
            st.divider()
            st.subheader("🌐 Opportunités détectées sur Leboncoin")
            
            with st.spinner("Le robot extrait les annonces actuelles..."):
                annonces_live = fetch_real_data_leboncoin(apify_token, ville_input, budget_input)
            
            if not annonces_live:
                st.warning("Aucune annonce trouvée avec ces critères. Vérifiez vos crédits Apify.")
            else:
                for ann in annonces_live:
                    # Calcul de la rentabilité / décote pour chaque annonce
                    p_m2_annonce = round(ann['prix'] / ann['surface']) if ann['surface'] > 0 else 0
                    
                    with st.container(border=True):
                        col_img, col_txt = st.columns([1, 2])
                        
                        with col_img:
                            st.image(ann['image'], width='stretch')
                            
                        with col_txt:
                            st.write(f"### {ann['titre']}")
                            st.write(f"💰 **{ann['prix']:,} €** | 📐 **{ann['surface']} m²** ({p_m2_annonce} €/m²)")
                            
                            # Logique de détection de "Bonne Affaire"
                            if prix_m2_moyen > 0 and p_m2_annonce > 0:
                                if p_m2_annonce < prix_m2_moyen:
                                    difference = round(((prix_m2_moyen - p_m2_annonce) / prix_m2_moyen) * 100)
                                    st.success(f"🔥 OPPORTUNITÉ : Cette annonce est **{difference}%** sous le prix du marché !")
                                else:
                                    st.info("Le prix est cohérent avec la moyenne locale.")
                            
                            with st.expander("Voir la description"):
                                st.write(ann['description'])
                                
                            st.link_button("🔗 Consulter sur Leboncoin", ann['url'], use_container_width=True)
        else:
            st.error("Ville non trouvée par l'API Géo. Essayez une orthographe différente.")

else:
    st.info("👋 Entrez vos paramètres et lancez l'analyse pour voir les annonces en temps réel.")
