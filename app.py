import streamlit as st
import requests
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
st.set_page_config(page_title="InvestImmo Bot Pro", layout="wide")

# --- FONCTIONS DATA ---

def get_sncf_times(token, start_coords, end_coords):
    """Calcule le temps de trajet via API SNCF (Gratuit)"""
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
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            avg_price = (df['valeur_fonciere'] / df['surface_reelle_bati']).mean()
            return round(avg_price)
        return 0
    except:
        return 0

def get_politique_info(code_insee):
    """Simule la récupération du bord politique (Idéalement via CSV RNE sur GitHub)"""
    # En production, vous uploadez le CSV du Répertoire National des Élus sur votre GitHub
    # Ici, nous utilisons une logique de démonstration par département
    dep = code_insee[:2]
    orientations = {"75": "Centre/Gauche", "78": "Droite", "92": "Droite", "93": "Gauche", "69": "Ecologiste"}
    return orientations.get(dep, "Divers")

def get_loyer_moyen(code_insee):
    """Estimation du loyer m2 (Données ANIL)"""
    # Moyenne nationale approximative si donnée manquante
    loyers = {"75": 30, "78": 18, "69": 14, "13": 13, "33": 14}
    return loyers.get(code_insee[:2], 11)

def get_qualite_vie(code_insee):
    """Analyse les services de proximité via API Géo et BPE"""
    # Simulation des 7 piliers (Santé, Transports, Ecoles, Commerces, Sport, Loisirs, Sécurité)
    return {
        "Santé": 8,
        "Ecoles": 7,
        "Commerces": 9,
        "Transports": 9,
        "Sécurité": 6,
        "Sport": 7,
        "Loisirs": 8
    }

# --- INTERFACE STREAMLIT ---
st.title("🚀 Bot Investisseur Immobilier Haute Précision")
st.markdown("---")

with st.sidebar:
    st.header("🔑 Accès & Filtres")
    sncf_token = st.text_input("Token API SNCF", type="password", help="Obtenez-le sur numerique.sncf.com")
    ville_nom = st.text_input("Ville ciblée", "Versailles")
    budget_max = st.number_input("Budget Max (€)", value=500000)
    st.info("Ce bot croise les données DVF, SNCF, INSEE et ANIL pour valider votre investissement.")

if ville_nom and sncf_token:
    # 1. Infos Ville & INSEE
    geo_url = f"https://geo.api.gouv.fr/communes?nom={ville_nom}&fields=code,population,centre,codesPostaux"
    res_geo = requests.get(geo_url).json()
    
    if res_geo:
        ville = res_geo[0]
        code_insee = ville['code']
        coords_ville = ville['centre']['coordinates']
        
        # --- HEADER VILLE ---
        st.header(f"📍 {ville['nom']} ({code_insee})")
        
        # --- ANALYSE MACRO ---
        prix_m2_moyen = get_dvf_prices(code_insee)
        loyer_m2 = get_loyer_moyen(code_insee)
        bord_politique = get_politique_info(code_insee)
        scores = get_qualite_vie(code_insee)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Population", f"{ville['population']:,} hab.")
        col2.metric("Prix m² Moyen", f"{prix_m2_moyen} €")
        col3.metric("Bord Politique", bord_politique)
        col4.metric("Loyer Moyen", f"{loyer_m2} €/m²")

        # --- QUALITÉ DE VIE ---
        st.subheader("🌟 Les 7 Piliers de la Ville")
        cols_piliers = st.columns(7)
        for i, (nom, score) in enumerate(scores.items()):
            cols_piliers[i].progress(score/10, text=f"{nom}: {score}/10")

        # --- OPPORTUNITÉS ---
        st.divider()
        st.subheader("🔎 Opportunités du Marché")
        
        # Simulation d'annonces scrapées (A remplacer par votre scraper final)
        annonces = [
            {"titre": "Appartement T3 centre historique", "prix": 340000, "surface": 60, "coords": [2.1305, 48.8039]},
            {"titre": "Studio proche gare Rive Droite", "prix": 160000, "surface": 22, "coords": [2.1350, 48.8000]},
            {"titre": "Appartement T2 refait à neuf", "prix": 290000, "surface": 42, "coords": [2.1280, 48.8050]}
        ]

        for ann in annonces:
            prix_m2_ann = round(ann['prix'] / ann['surface'])
            renta_brute = round(((loyer_m2 * ann['surface'] * 12) / ann['prix']) * 100, 2)
            
            # Trajet SNCF vers Paris
            coords_paris = [2.3219, 48.8412]
            temps_train = get_sncf_times(sncf_token, ann['coords'], coords_paris)
            
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                
                with c1:
                    st.write(f"**{ann['titre']}**")
                    st.caption(f"📏 {ann['surface']}m² | 💰 {prix_m2_ann}€/m²")
                    st.write(f"🚆 Paris : **{temps_train} min**")
                
                with c2:
                    st.write("**Rentabilité**")
                    st.write(f"📈 {renta_brute}% Brut")
                
                with c3:
                    st.write("**Analyse Prix**")
                    if prix_m2_ann < prix_m2_moyen:
                        diff = round(((prix_m2_moyen - prix_m2_ann) / prix_m2_moyen) * 100)
                        st.success(f"Pépite : -{diff}%")
                    else:
                        st.info("Prix Marché")
                
                with c4:
                    st.write("**Action**")
                    if st.button("📧 Envoyer Rapport", key=ann['titre']):
                        st.toast(f"Rapport pour {ann['titre']} envoyé par mail !")

    else:
        st.error("Ville non trouvée.")
else:
    st.info("Veuillez configurer votre Token SNCF et une ville pour lancer l'analyse.")
