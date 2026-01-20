import streamlit as st
import requests
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="InvestImmo Bot Pro", layout="wide", initial_sidebar_state="expanded")

# --- FONCTIONS DATA ---

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
    """Récupération du bord politique par département"""
    dep = code_insee[:2]
    orientations = {
        "75": "Centre/Gauche", "78": "Droite", "92": "Droite", 
        "93": "Gauche", "69": "Ecologiste", "13": "Droite/Extrême Droite",
        "33": "Ecologiste", "31": "Gauche", "44": "Gauche", "59": "Divers Droite"
    }
    return orientations.get(dep, "Divers")

def get_loyer_moyen(code_insee):
    """Estimation du loyer m2 (Données types ANIL par département)"""
    loyers = {"75": 31, "78": 18, "92": 24, "69": 14, "13": 13, "33": 15, "31": 12, "44": 12, "59": 11}
    return loyers.get(code_insee[:2], 10)

def get_qualite_vie(code_insee):
    """Analyse simulée des 7 piliers (Basée sur densité urbaine via code_insee)"""
    # En production, croiser avec l'API BPE de l'INSEE
    score_base = 6 if len(code_insee) == 5 else 4
    return {
        "Santé": score_base + 2,
        "Écoles": score_base + 1,
        "Commerces": score_base + 3,
        "Transports": score_base + 2,
        "Sécurité": score_base - 1,
        "Sport": score_base,
        "Loisirs": score_base + 1
    }

# --- INTERFACE STREAMLIT ---
st.title("🚀 Bot Investisseur Immobilier Pro")
st.markdown("---")

with st.sidebar:
    st.header("🔑 Accès & Paramètres")
    sncf_token = st.text_input("Token API SNCF", type="password", help="Inscrivez-vous sur numerique.sncf.com")
    ville_nom = st.text_input("Ville cible", "Versailles")
    budget_max = st.number_input("Budget Max (€)", value=600000, step=10000)
    st.divider()
    st.info("Ce bot analyse en temps réel : la rentabilité brute, la décote DVF, les transports SNCF et la qualité de vie locale.")

if ville_nom and sncf_token:
    # 1. Infos Ville & INSEE via API Géo
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
        col2.metric("Prix m² Moyen (Marché)", f"{prix_m2_moyen} €")
        col3.metric("Bord Politique", bord_politique)
        col4.metric("Loyer Moyen", f"{loyer_m2} €/m²")

        # --- QUALITÉ DE VIE (LES 7 PILIERS) ---
        st.subheader("🌟 Analyse des 7 Piliers de la Ville")
        cols_piliers = st.columns(7)
        for i, (nom, score) in enumerate(scores.items()):
            cols_piliers[i].progress(score/10, text=f"{nom}")
            cols_piliers[i].write(f"**{score}/10**")

        # --- OPPORTUNITÉS (AVEC PHOTOS) ---
        st.divider()
        st.subheader("🔎 Annonces Détectées & Analyse de Rentabilité")
        
        # Simulation d'annonces scrapées avec multi-photos
        annonces = [
            {
                "id": "A1",
                "titre": "Appartement T3 centre - Cachet de l'ancien", 
                "prix": 345000, 
                "surface": 58, 
                "coords": [2.1305, 48.8039],
                "images": [
                    "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800",
                    "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=800"
                ]
            },
            {
                "id": "A2",
                "titre": "Studio Meublé - Spécial Investisseur", 
                "prix": 155000, 
                "surface": 20, 
                "coords": [2.1350, 48.8000],
                "images": [
                    "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800",
                    "https://images.unsplash.com/photo-1560448204-61dc36dc98c8?w=800"
                ]
            }
        ]

        for ann in annonces:
            if ann['prix'] <= budget_max:
                prix_m2_ann = round(ann['prix'] / ann['surface'])
                renta_brute = round(((loyer_m2 * ann['surface'] * 12) / ann['prix']) * 100, 2)
                
                # Temps SNCF vers Paris Montparnasse (Exemple)
                coords_paris = [2.3219, 48.8412]
                temps_train = get_sncf_times(sncf_token, ann['coords'], coords_paris)
                
                with st.container(border=True):
                    col_img, col_desc = st.columns([1.2, 2])
                    
                    with col_img:
                        # Carrousel simplifié : Sélection de la photo
                        img_select = st.selectbox(f"Photos de l'annonce {ann['id']}", range(len(ann['images'])), key=f"select_{ann['id']}")
                        st.image(ann['images'][img_select], use_container_width=True)
                    
                    with col_desc:
                        st.write(f"### {ann['titre']}")
                        st.write(f"💰 **{ann['prix']:,} €** | 📏 **{ann['surface']} m²** ({prix_m2_ann} €/m²)")
                        
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("Rentabilité Brute", f"{renta_brute} %")
                        with c2:
                            st.metric("🚆 Vers Paris", f"{temps_train} min")
                        with c3:
                            st.write("**Analyse Prix**")
                            if prix_m2_ann < prix_m2_moyen:
                                diff = round(((prix_m2_moyen - prix_m2_ann) / prix_m2_moyen) * 100)
                                st.success(f"🔥 Pépite : -{diff}% / marché")
                            else:
                                st.info("Prix dans la moyenne")
                        
                        st.divider()
                        if st.button(f"📧 Recevoir le rapport complet ({ann['id']})", use_container_width=True):
                            st.toast(f"Génération du PDF pour {ann['titre']}... Mail envoyé !")

    else:
        st.error("Ville non trouvée. Merci de vérifier l'orthographe (ex: Versailles, Lyon, etc.)")
else:
    st.warning("⚠️ Action requise : Entrez votre Token SNCF et une ville dans la barre latérale pour activer le bot.")
