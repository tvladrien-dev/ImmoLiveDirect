import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="InvestImmo Bot", layout="wide")

# --- FONCTIONS API ---

def get_sncf_times(token, start_coords, end_coords):
    """Calcule le temps de trajet via API SNCF (Gratuit)"""
    # Format coords pour SNCF: lon;lat
    url = f"https://api.sncf.com/v1/coverage/sncf/journeys?from={start_coords[0]};{start_coords[1]}&to={end_coords[0]};{end_coords[1]}"
    try:
        res = requests.get(url, auth=(token, ""))
        data = res.json()
        if "journeys" in data:
            duration = data["journeys"][0]["duration"]
            return round(duration / 60)
        return "N/A"
    except:
        return "Erreur"

def get_dvf_prices(code_insee):
    """Récupère le prix moyen m2 historique (API cquest gratuite)"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        res = requests.get(url).json()
        if "features" in res:
            df = pd.DataFrame([f['properties'] for f in res['features']])
            # Calcul du prix m2 moyen sur les ventes de maisons/apparts
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            avg_price = (df['valeur_fonciere'] / df['surface_reelle_bati']).mean()
            return round(avg_price)
        return 0
    except:
        return 0

# --- INTERFACE STREAMLIT ---
st.title("🏠 Bot Investisseur Immo (Full Gratuit)")

with st.sidebar:
    st.header("Configuration")
    sncf_token = st.text_input("Token API SNCF", type="password")
    ville_nom = st.text_input("Ville ciblée", "Versailles")
    budget_max = st.number_input("Budget Max (€)", value=400000)

if ville_nom and sncf_token:
    # 1. Infos Ville & INSEE
    geo_url = f"https://geo.api.gouv.fr/communes?nom={ville_nom}&fields=code,population,centre,codesPostaux"
    res_geo = requests.get(geo_url).json()
    
    if res_geo:
        ville = res_geo[0]
        code_insee = ville['code']
        coords_ville = ville['centre']['coordinates'] # [lon, lat]
        
        st.header(f"📍 {ville['nom']} ({code_insee})")
        
        # 2. Analyse Marché
        prix_m2_moyen = get_dvf_prices(code_insee)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Population", f"{ville['population']:,} hab.")
        col2.metric("Prix m² Moyen (DVF)", f"{prix_m2_moyen} €")
        col3.metric("Risque", "Faible" if ville['population'] > 20000 else "Modéré")

        # 3. Simulation Annonce (Remplace par ton scraper)
        st.divider()
        st.subheader("🔎 Opportunités détectées")
        
        # Exemple d'annonce scrapée
        annonces = [
            {"titre": "Appartement T3 Centre", "prix": 320000, "surface": 55, "coords": [2.1305, 48.8039]},
            {"titre": "Studio Gare", "prix": 150000, "surface": 20, "coords": [2.1350, 48.8000]}
        ]

        for ann in annonces:
            prix_m2_ann = round(ann['prix'] / ann['surface'])
            # Calcul trajet vers Paris (Exemple: Versailles -> Paris Montparnasse)
            coords_paris = [2.3219, 48.8412]
            temps_train = get_sncf_times(sncf_token, ann['coords'], coords_paris)
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"**{ann['titre']}**")
                c1.caption(f"Prix m² : {prix_m2_ann}€ | Marché : {prix_m2_moyen}€")
                
                c2.write(f"🚆 Paris : {temps_train} min")
                
                # Indicateur d'affaire
                if prix_m2_ann < prix_m2_moyen:
                    diff = round(((prix_m2_moyen - prix_m2_ann) / prix_m2_moyen) * 100)
                    c3.success(f"Pépite : -{diff}%")
                else:
                    c3.info("Prix Marché")

                if st.button("📧 Envoyer Rapport", key=ann['titre']):
                    st.toast("Rapport envoyé (Simulé)")

    else:
        st.error("Ville non trouvée.")
else:
    st.info("Veuillez saisir votre Token SNCF et une ville dans le menu à gauche.")
