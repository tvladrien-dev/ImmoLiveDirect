import streamlit as st
import requests
import pandas as pd
import numpy as np
from apify_client import ApifyClient

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="InvestImmo Bot PRO - Live Data", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- LOGIQUE DATA HAUTE PRÉCISION ---

def get_sncf_times(token, start_coords, end_coords):
    """Calcule la durée de trajet réelle via l'API Navitia/SNCF"""
    # Navitia attend lon,lat
    url = f"https://api.sncf.com/v1/coverage/sncf/journeys?from={start_coords[0]};{start_coords[1]}&to={end_coords[0]};{end_coords[1]}"
    try:
        res = requests.get(url, auth=(token, ""))
        data = res.json()
        if "journeys" in data and len(data["journeys"]) > 0:
            duration = data["journeys"][0]["duration"]
            return round(duration / 60)
        return "N/A"
    except Exception:
        return "Erreur API"

def get_dvf_prices_dynamic(code_insee):
    """Extraction et calcul statistique des prix m2 réels (Base Notaires/DVF)"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        res = requests.get(url).json()
        if "features" in res and len(res["features"]) > 0:
            df = pd.DataFrame([f['properties'] for f in res['features']])
            # Nettoyage et conversion stricte
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            
            if not df.empty:
                # Calcul du prix au m2 par transaction puis moyenne
                df['price_m2'] = df['valeur_fonciere'] / df['surface_reelle_bati']
                return round(df['price_m2'].mean())
        return 0
    except Exception:
        return 0

def get_dynamic_piliers(population):
    """Algorithme de scoring des infrastructures basé sur la densité démographique réelle"""
    if population <= 0: return {k: 0 for k in ["Santé", "Écoles", "Commerces", "Transports", "Sécurité", "Sport", "Loisirs"]}
    
    # Logique basée sur la loi de Zipf (densité des services liée à la population)
    log_pop = np.log10(population)
    base = min(int(log_pop * 1.8), 10)
    
    return {
        "Santé": min(base + 1, 10),
        "Écoles": min(base, 10),
        "Commerces": min(base + 2, 10),
        "Transports": min(base + 1, 10),
        "Sécurité": max(10 - (base // 2), 2), # Score inverse à la densité urbaine
        "Sport": min(base, 10),
        "Loisirs": min(base + 1, 10)
    }

def get_real_listings_web(api_token, ville, budget_max):
    """
    Moteur de scraping réel via Apify. 
    Interroge Leboncoin/SeLoger et récupère les annonces fraîches.
    """
    if not api_token:
        return []
    
    client = ApifyClient(api_token)
    # Configuration du scraper (Actor ID à adapter selon votre choix sur Apify)
    run_input = {
        "location": ville,
        "max_price": int(budget_max),
        "category": "immobilier",
        "limit": 10
    }
    
    try:
        # Appel synchrone au scraper
        run = client.actor("dtrungtin/leboncoin-scraper").call(run_input=run_input)
        results = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append({
                "id": item.get("id", "N/A"),
                "titre": item.get("title", "Sans titre"),
                "prix": item.get("price", 0),
                "surface": item.get("attributes", {}).get("square", 0),
                "images": item.get("images", []),
                "url": item.get("url", "#"),
                "loc": [item.get("location", {}).get("lng", 0), item.get("location", {}).get("lat", 0)]
            })
        return results
    except Exception:
        return []

# --- INTERFACE UTILISATEUR (STREAMLIT) ---

st.title("🤖 InvestImmo Bot : Intelligence Artificielle Immobilière")
st.markdown("---")

# Sidebar pour la configuration
with st.sidebar:
    st.header("🔑 Configuration API")
    apify_token = st.text_input("Apify API Token", type="password", help="Pour le scraping réel")
    sncf_token = st.text_input("SNCF API Token", type="password", help="Pour le calcul de trajet")
    
    st.header("🔍 Critères de Recherche")
    ville_cible = st.text_input("Ville de recherche", "Versailles")
    budget_max = st.number_input("Budget Maximum (€)", value=500000, step=10000)
    
    submit = st.button("🚀 Lancer l'Analyse Live", use_container_width=True)

if submit:
    if not sncf_token or not ville_cible:
        st.error("Veuillez remplir au moins la ville et le token SNCF.")
    else:
        # 1. RÉCUPÉRATION DES DONNÉES GÉOGRAPHIQUES (API GOUV)
        with st.spinner("Analyse de la ville en cours..."):
            geo_url = f"https://geo.api.gouv.fr/communes?nom={ville_cible}&fields=code,population,centre"
            geo_res = requests.get(geo_url).json()
            
        if geo_res:
            ville_data = geo_res[0]
            code_insee = ville_data['code']
            population = ville_data.get('population', 0)
            coords_ville = ville_data['centre']['coordinates']
            
            # 2. ANALYSE DU MARCHÉ ET SERVICES
            prix_m2_moyen = get_dvf_prices_dynamic(code_insee)
            piliers = get_dynamic_piliers(population)
            
            st.header(f"📍 Rapport Sectoriel : {ville_data['nom']}")
            
            # Métriques principales
            m1, m2, m3 = st.columns(3)
            m1.metric("Population Réelle", f"{population:,} hab.")
            m2.metric("Prix m² Marché (DVF)", f"{prix_m2_moyen} €")
            m3.metric("Tension Immobilière", "Haute" if population > 50000 else "Modérée")
            
            # Affichage des 7 Piliers
            st.subheader("🌟 Diagnostic Qualité de Vie")
            cols = st.columns(7)
            for i, (nom, score) in enumerate(piliers.items()):
                cols[i].progress(score/10, text=nom)
                cols[i].write(f"**{score}/10**")
                
            # 3. SCRAPING ET AFFICHAGE DES ANNONCES
            st.divider()
            st.subheader("🔥 Opportunités Détectées en Direct")
            
            with st.spinner("Scraping des annonces web..."):
                annonces = get_real_listings_web(apify_token, ville_cible, budget_max)
            
            if not annonces:
                st.warning("Aucune annonce trouvée via le scraper. Vérifiez votre token Apify.")
            else:
                for ann in annonces:
                    # Calculs dynamiques par annonce
                    p_m2_ann = round(ann['prix'] / ann['surface']) if ann['surface'] > 0 else 0
                    # Trajet vers Paris (Châtelet) par défaut
                    temps_paris = get_sncf_times(sncf_token, coords_ville, [2.3488, 48.8534])
                    
                    with st.container(border=True):
                        c_img, c_info = st.columns([1, 2])
                        
                        with c_img:
                            if ann['images']:
                                st.image(ann['images'][0], width='stretch')
                            else:
                                st.image("https://via.placeholder.com/400x300?text=Pas+de+photo", width='stretch')
                        
                        with c_info:
                            st.write(f"### {ann['titre']}")
                            st.write(f"💰 **{ann['prix']:,} €** | 📐 **{ann['surface']} m²**")
                            
                            sc1, sc2, sc3 = st.columns(3)
                            sc1.metric("Prix m²", f"{p_m2_ann} €")
                            sc2.metric("🚆 Gare Paris", f"{temps_paris} min")
                            
                            with sc3:
                                if prix_m2_moyen > 0 and p_m2_ann < prix_m2_moyen:
                                    diff = round(((prix_m2_moyen - p_m2_ann) / prix_m2_moyen) * 100)
                                    st.success(f"DÉCOTE : -{diff}%")
                                else:
                                    st.info("Prix Marché")
                            
                            st.link_button("🌐 Consulter l'annonce originale", ann['url'], use_container_width=True)
        else:
            st.error("Ville non identifiée. Vérifiez l'orthographe.")

else:
    st.info("👋 Bienvenue. Configurez vos accès dans le menu de gauche et lancez l'analyse.")
