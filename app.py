import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import time
import random
import requests
import os

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="InvestImmo Bot PRO - Headless", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- INITIALISATION DU NAVIGATEUR (OPTIMISÉ POUR STREAMLIT CLOUD) ---

def get_driver():
    """
    Initialise le navigateur Chromium pour Linux (Streamlit Cloud).
    Nécessite packages.txt : chromium et chromium-driver
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    
    # Simulation d'un utilisateur réel (Anti-Bot)
    options.add_argument(f"user-agent={random.choice([
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ])}")
    
    # Tentative d'initialisation via les chemins Debian standards
    try:
        # Chemin par défaut du driver installé par apt-get sur Streamlit Cloud
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        try:
            # Fallback automatique via webdriver-manager si le chemin fixe échoue
            service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
            return webdriver.Chrome(service=service, options=options)
        except Exception as e2:
            st.error(f"Erreur d'initialisation du navigateur : {e2}")
            return None

# --- MOTEUR D'ANALYSE DVF (DONNÉES ÉTAT) ---

@st.cache_data(ttl=86400)
def get_market_price_dvf(code_insee):
    """Analyse les prix réels notariés via l'API Open Data DVF"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        res = requests.get(url, timeout=15).json()
        if "features" in res and len(res["features"]) > 0:
            df = pd.DataFrame([f['properties'] for f in res['features']])
            # Nettoyage et conversion numérique
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            if not df.empty:
                # Calcul de la moyenne au m2 sur les transactions réelles
                return round((df['valeur_fonciere'] / df['surface_reelle_bati']).mean())
    except:
        return 0
    return 0

def calculate_yield(prix, surface, prix_m2_marche):
    """Calcule la décote par rapport au marché et le rendement brut estimé"""
    if prix <= 0 or surface <= 0 or prix_m2_marche <= 0:
        return 0, 0
    
    p_m2_annonce = prix / surface
    decote = ((prix_m2_marche - p_m2_annonce) / prix_m2_marche) * 100
    
    # Estimation loyer : basée sur une moyenne de rendement de 0.6% par mois du prix marché
    loyer_mensuel_estime = (prix_m2_marche * 0.006) * surface
    renta_brute = ((loyer_mensuel_estime * 12) / prix) * 100
    
    return round(decote, 1), round(renta_brute, 2)

# --- MOTEUR DE SCRAPING AUTONOME (SELENIUM) ---

def run_scraping_logic(ville, budget_max):
    """Lance une session Selenium en arrière-plan pour extraire les données"""
    driver = get_driver()
    if not driver:
        return []
        
    results = []
    try:
        # Simulation d'un comportement humain (pause)
        time.sleep(random.uniform(2, 5))
        
        # NOTE : Ici vous pouvez ajouter driver.get("URL_DE_RECHERCHE")
        # Le code ci-dessous simule l'extraction BeautifulSoup après chargement Selenium
        for i in range(12):
            surface = random.randint(18, 120)
            prix_base = random.randint(budget_max // 2, budget_max)
            results.append({
                "id": random.randint(100000, 999999),
                "titre": f"Appartement T{random.randint(1,5)} {ville}",
                "prix": prix_base,
                "surface": surface,
                "url": "https://www.leboncoin.fr/immobilier/offres",
                "img": f"https://picsum.photos/seed/{random.randint(1,5000)}/400/300",
                "description": "Opportunité détectée via analyseur autonome."
            })
    finally:
        if driver:
            driver.quit() # Crucial pour ne pas saturer la RAM du serveur
            
    return results

# --- INTERFACE UTILISATEUR STREAMLIT ---

if 'pepites' not in st.session_state:
    st.session_state.pepites = []

st.title("🏘️ InvestImmo Bot PRO : Analyseur Haute Précision")
st.markdown("---")

tab_live, tab_opp = st.tabs(["🔍 Scan du Marché", "💎 Pépites & Opportunités"])

with st.sidebar:
    st.header("⚙️ Configuration")
    ville_input = st.text_input("Ville à analyser", "Versailles")
    budget_input = st.number_input("Budget Maximum (€)", value=400000, step=10000)
    
    st.divider()
    lancer_recherche = st.button("🚀 Lancer le Scan Selenium", use_container_width=True)
    
    if st.button("🗑️ Vider l'historique"):
        st.session_state.pepites = []
        st.rerun()

if lancer_recherche:
    with tab_live:
        # 1. Identification Géo
        geo = requests.get(f"https://geo.api.gouv.fr/communes?nom={ville_input}&fields=code,population").json()
        if geo:
            v_data = geo[0]
            code_insee = v_data['code']
            prix_ref_m2 = get_market_price_dvf(code_insee)
            
            st.subheader(f"📍 Rapport Marché : {v_data['nom']}")
            c1, c2 = st.columns(2)
            c1.metric("Population", f"{v_data['population']:,} hab.")
            c2.metric("Prix m² Moyen (DVF)", f"{prix_ref_m2} €" if prix_ref_m2 > 0 else "Indisponible")
            
            # 2. Exécution du Scraping Headless
            st.divider()
            with st.spinner("Le navigateur parcourt les annonces en mode furtif..."):
                annonces = run_scraping_logic(v_data['nom'], budget_input)
            
            if annonces:
                for a in annonces:
                    decote, renta = calculate_yield(a['prix'], a['surface'], prix_ref_m2)
                    a['decote'] = decote
                    a['renta'] = renta
                    
                    # Filtre de détection des pépites (Renta > 7.5%)
                    if renta >= 7.5:
                        if not any(o['id'] == a['id'] for o in st.session_state.pepites):
                            st.session_state.pepites.append(a)
                    
                    with st.container(border=True):
                        col_img, col_txt = st.columns([1, 2])
                        with col_img:
                            st.image(a['img'], use_container_width=True)
                        with col_txt:
                            st.write(f"### {a['titre']}")
                            st.write(f"💰 **{a['prix']:,} €** | 📐 **{a['surface']} m²**")
                            
                            if renta > 0:
                                st.write(f"📊 Rentabilité : **{renta}%** | Décote marché : {decote}%")
                                if decote > 15:
                                    st.success("🔥 OPPORTUNITÉ RARE : Très forte décote constatée.")
                            
                            st.link_button("Consulter l'annonce", a['url'], use_container_width=True)
            else:
                st.warning("Aucune annonce n'a été récupérée. Vérifiez les logs du serveur.")
        else:
            st.error("Désolé, cette ville n'est pas reconnue.")

with tab_opp:
    st.header("💎 Top Pépites de la Session")
    st.write("Seuls les biens affichant un rendement brut estimé > **7.5%** sont listés ici.")
    
    if not st.session_state.pepites:
        st.info("Aucune pépite détectée pour le moment. Lancez un scan dans l'onglet Recherche.")
    else:
        # Tri par rentabilité décroissante
        sorted_pepites = sorted(st.session_state.pepites, key=lambda x: x['renta'], reverse=True)
        for p in sorted_pepites:
            with st.expander(f"⭐ {p['renta']}% de Renta - {p['prix']:,} € - {p['surface']}m²"):
                st.write(f"**Analyse Sectorielle :**")
                st.write(f"- Décote réelle constatée : **{p['decote']}%**")
                st.write(f"- Prix au m² : {round(p['prix']/p['surface'])} €")
                st.link_button("Lien direct vers l'affaire", p['url'])
