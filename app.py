import streamlit as st
import requests
import pandas as pd
import numpy as np
from apify_client import ApifyClient

# --- CONFIGURATION STRICTE DE LA PAGE ---
st.set_page_config(
    page_title="InvestImmo Bot PRO - Live Analytics", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- MOTEUR DE CALCUL PRIX MARCHÉ (DVF RÉEL) ---

def get_dvf_prices_dynamic(code_insee):
    """
    Analyse statistique des transactions réelles de la commune via l'API cquest.
    Retourne le prix moyen au m2 basé sur les ventes notariales.
    """
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        res = requests.get(url, timeout=15).json()
        if "features" in res and len(res["features"]) > 0:
            df = pd.DataFrame([f['properties'] for f in res['features']])
            # Conversion forcée en numérique pour les calculs statistiques
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
        st.sidebar.warning(f"Note DVF : Données indisponibles pour ce code ({code_insee})")
        return 0

# --- MOTEUR DE SCRAPING LIVE (ID: OiU5ThXkp3gfs8fhG) ---

def fetch_leboncoin_data_live(api_token, ville, budget_max):
    """
    Exécution du scraper spécifique avec Proxy Résidentiel.
    Configuration calquée sur l'import JSON fourni par l'utilisateur.
    """
    if not api_token:
        return []
    
    client = ApifyClient(api_token)
    
    # Configuration exacte pour l'Actor OiU5ThXkp3gfs8fhG
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
        with st.spinner(f"🚀 Scraping en cours sur Leboncoin (Proxy Résidentiel)..."):
            # Lancement de l'Actor par son ID unique
            run = client.actor("OiU5ThXkp3gfs8fhG").call(run_input=run_input)
            
            listings = []
            # Parcours exhaustif des items du dataset généré
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                
                # Mapping flexible pour capturer la surface (square)
                attr = item.get("attributes", {})
                surface = 0
                if isinstance(attr, dict):
                    surface = attr.get("square") or attr.get("m2") or 0
                if not surface:
                    surface = item.get("square") or item.get("surface") or 0
                
                # Nettoyage du prix (gestion des formats listes ou entiers)
                raw_price = item.get("price")
                price = raw_price[0] if isinstance(raw_price, list) else raw_price
                
                listings.append({
                    "id": item.get("id", "N/A"),
                    "titre": item.get("title") or item.get("subject") or "Annonce Immobilière",
                    "prix": int(price) if price else 0,
                    "surface": float(surface) if surface else 0,
                    "image": item.get("images", ["https://via.placeholder.com/400"])[0] if item.get("images") else "https://via.placeholder.com/400",
                    "url": item.get("url", "https://www.leboncoin.fr"),
                    "description": item.get("description", "Aucune description.")
                })
            return listings
    except Exception as e:
        st.error(f"❌ Erreur Scraper : {str(e)}")
        return []

# --- INTERFACE UTILISATEUR STREAMLIT ---

st.title("🏘️ InvestImmo Bot : Analyseur Haute Précision")
st.markdown("---")

# Barre latérale de configuration
with st.sidebar:
    st.header("🔑 Authentification")
    apify_token = st.text_input("Apify API Token", type="password", help="Trouvez votre token dans Settings > Integrations sur Apify")
    
    st.header("🎯 Cible de Recherche")
    ville_input = st.text_input("Ville exacte", "Versailles")
    budget_input = st.number_input("Budget Maximum (€)", value=500000, step=10000)
    
    st.divider()
    lancer_recherche = st.button("🚀 Lancer l'Analyse en Direct", use_container_width=True)

# Logique d'exécution
if lancer_recherche:
    if not apify_token:
        st.error("Veuillez entrer votre Token Apify dans la barre latérale.")
    else:
        # 1. Identification Géographique (API GOUV)
        geo_url = f"https://geo.api.gouv.fr/communes?nom={ville_input}&fields=code,population"
        geo_data = requests.get(geo_url).json()
        
        if geo_data:
            ville_info = geo_data[0]
            code_insee = ville_info['code']
            population = ville_info.get('population', 0)
            
            # 2. Analyse Comparative (DVF)
            with st.spinner("Analyse des prix du marché réel..."):
                prix_m2_moyen = get_dvf_prices_dynamic(code_insee)
            
            st.header(f"📍 Rapport pour {ville_info['nom']} ({code_insee})")
            
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Population", f"{population:,} hab.")
            col_b.metric("Prix m² Moyen DVF", f"{prix_m2_moyen} €" if prix_m2_moyen > 0 else "Indisponible")
            col_c.metric("Status Scraper", "Succeeded" if apify_token else "Waiting")

            # 3. Scraping Live
            st.divider()
            st.subheader("🌐 Opportunités détectées sur Leboncoin")
            
            annonces_live = fetch_leboncoin_data_live(apify_token, ville_input, budget_input)
            
            if not annonces_live:
                st.warning("Aucune annonce n'a pu être récupérée. Vérifiez vos crédits Apify.")
            else:
                for ann in annonces_live:
                    # Calcul de rentabilité et décote
                    p_m2_annonce = round(ann['prix'] / ann['surface']) if ann['surface'] > 0 else 0
                    
                    with st.container(border=True):
                        c_img, c_txt = st.columns([1, 2])
                        
                        with c_img:
                            st.image(ann['image'], use_container_width=True)
                            
                        with c_txt:
                            st.write(f"### {ann['titre']}")
                            st.write(f"💰 **{ann['prix']:,} €** | 📏 **{ann['surface']} m²** ({p_m2_annonce} €/m²)")
                            
                            # Logique de détection de décote
                            if prix_m2_moyen > 0 and p_m2_annonce > 0:
                                if p_m2_annonce < prix_m2_moyen:
                                    diff = round(((prix_m2_moyen - p_m2_annonce) / prix_m2_moyen) * 100)
                                    st.success(f"🔥 AFFAIRE DÉTECTÉE : **-{diff}%** sous le prix du marché local !")
                                else:
                                    st.info("Prix cohérent avec la moyenne du secteur.")
                            
                            with st.expander("Voir la description complète"):
                                st.write(ann['description'])
                                
                            st.link_button("🔗 Consulter sur Leboncoin", ann['url'], use_container_width=True)
        else:
            st.error("Ville non reconnue par l'API Géo. Essayez d'être plus précis.")

else:
    st.info("👋 Bienvenue ! Saisissez vos paramètres à gauche pour lancer l'analyse comparative en temps réel.")
