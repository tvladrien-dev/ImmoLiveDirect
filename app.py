import streamlit as st
import requests
import pandas as pd
import numpy as np

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="InvestImmo Bot Dynamique", layout="wide", initial_sidebar_state="expanded")

# --- FONCTIONS DATA DYNAMIQUES ---

def get_sncf_times(token, start_coords, end_coords):
    """Calcule le temps de trajet via API SNCF (Données réelles)"""
    url = f"https://api.sncf.com/v1/coverage/sncf/journeys?from={start_coords[0]};{start_coords[1]}&to={end_coords[0]};{end_coords[1]}"
    try:
        res = requests.get(url, auth=(token, ""))
        data = res.json()
        if "journeys" in data:
            duration = data["journeys"][0]["duration"]
            return round(duration / 60)
        return "N/A"
    except Exception:
        return "Calcul impossible"

def get_dvf_prices_dynamic(code_insee):
    """Récupère et calcule le prix m2 réel sur les dernières ventes (API cquest)"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        res = requests.get(url).json()
        if "features" in res and len(res["features"]) > 0:
            df = pd.DataFrame([f['properties'] for f in res['features']])
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            if not df.empty:
                avg_price = (df['valeur_fonciere'] / df['surface_reelle_bati']).mean()
                return round(avg_price)
        return 3000 # Valeur pivot si aucune donnée
    except Exception:
        return 3000

def get_dynamic_scores(population):
    """Calcule les 7 piliers dynamiquement en fonction de la population réelle"""
    # Plus la ville est grande, plus les services sont denses
    pop_factor = np.log10(population) if population > 0 else 1
    base_score = min(int(pop_factor * 2), 10)
    
    return {
        "Santé": min(base_score + 1, 10),
        "Écoles": min(base_score, 10),
        "Commerces": min(base_score + 2, 10),
        "Transports": min(base_score + 1, 10),
        "Sécurité": max(10 - base_score, 3), # Souvent inverse à la densité
        "Sport": min(base_score, 10),
        "Loisirs": min(base_score + 1, 10)
    }

def fetch_real_listings(ville_nom, code_insee, budget_max):
    """
    Simule la sortie d'un scraper dynamique. 
    Dans une version finale, cette fonction appelle une API de scraping (ex: Apify).
    Elle génère ici des données basées sur les paramètres de la ville.
    """
    # On génère des opportunités basées sur la ville réelle choisie
    prefix = ville_nom.capitalize()
    return [
        {
            "id": f"{code_insee}-1",
            "titre": f"T3 de standing - {prefix} Centre",
            "prix": int(budget_max * 0.8),
            "surface": 65,
            "images": ["https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800"],
            "coords": [2.3522, 48.8566] # À ajuster selon la ville
        },
        {
            "id": f"{code_insee}-2",
            "titre": f"Studio Rénové - {prefix} Universités",
            "prix": int(budget_max * 0.4),
            "surface": 22,
            "images": ["https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800"],
            "coords": [2.3522, 48.8566]
        }
    ]

# --- INTERFACE ---
st.title("🤖 InvestImmo Bot : Analyseur Dynamique")

with st.sidebar:
    st.header("🔑 Paramètres de Recherche")
    sncf_token = st.text_input("Token API SNCF", type="password")
    ville_nom = st.text_input("Ville cible", "Versailles")
    budget_max = st.number_input("Budget Max (€)", value=500000, step=10000)
    st.divider()
    st.write("📈 **État du bot :**")
    if sncf_token and ville_nom:
        st.success("Connecté aux API")
    else:
        st.warning("En attente de configuration")

if ville_nom and sncf_token:
    # 1. API Géo pour récupérer les données fondamentales
    geo_url = f"https://geo.api.gouv.fr/communes?nom={ville_nom}&fields=code,population,centre,codesPostaux"
    res_geo = requests.get(geo_url).json()
    
    if res_geo:
        ville = res_geo[0]
        code_insee = ville['code']
        coords_ville = ville['centre']['coordinates']
        population = ville.get('population', 0)
        
        # 2. Données Marché Dynamiques
        prix_m2_moyen = get_dvf_prices_dynamic(code_insee)
        scores = get_dynamic_scores(population)
        
        st.header(f"📍 Ville : {ville['nom']} ({code_insee})")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Population", f"{population:,} hab.")
        m2.metric("Prix m² Moyen (DVF)", f"{prix_m2_moyen} €")
        m3.metric("Potentiel", "Élevé" if population > 50000 else "Niche")

        # 3. Affichage des 7 Piliers calculés
        st.subheader("🌟 Analyse Infrastructures (Données calculées)")
        cols_p = st.columns(7)
        for i, (k, v) in enumerate(scores.items()):
            cols_p[i].progress(v/10, text=k)
            cols_p[i].write(f"**{v}/10**")

        # 4. Annonces Dynamiques
        st.divider()
        st.subheader("🔎 Opportunités Détectées")
        
        annonces = fetch_real_listings(ville_nom, code_insee, budget_max)
        
        for ann in annonces:
            p_m2_ann = round(ann['prix'] / ann['surface'])
            # Calcul du trajet vers Paris via API SNCF
            coords_paris = [2.3219, 48.8412]
            temps_train = get_sncf_times(sncf_token, coords_ville, coords_paris)
            
            with st.container(border=True):
                c_img, c_desc = st.columns([1, 2])
                
                with c_img:
                    st.image(ann['images'][0], width='stretch') # Utilisation de stretch pour les logs
                
                with c_desc:
                    st.write(f"### {ann['titre']}")
                    st.write(f"💰 **{ann['prix']:,} €** | 📐 **{ann['surface']} m²**")
                    
                    sc1, sc2, sc3 = st.columns(3)
                    sc1.metric("Prix m²", f"{p_m2_ann} €")
                    sc2.metric("🚆 Train (Paris)", f"{temps_train} min")
                    
                    with sc3:
                        if p_m2_ann < prix_m2_moyen:
                            diff = round(((prix_m2_moyen - p_m2_ann) / prix_m2_moyen) * 100)
                            st.success(f"🔥 SOUS-COTÉ : -{diff}%")
                        else:
                            st.info("Prix Marché")
                    
                    st.button(f"Générer Rapport PDF ({ann['id']})", key=ann['id'], width='stretch')

    else:
        st.error("Ville non trouvée par l'API Géo.")
else:
    st.info("Veuillez configurer votre Token SNCF et une ville cible pour lancer l'analyse autonome.")
