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
import re

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="InvestImmo Bot PRO - Full Scraper", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- INITIALISATION DU NAVIGATEUR (ARCHITECTURE LINUX/CLOUD) ---

def get_driver():
    """
    Initialise Selenium en mode Headless. 
    Cherche les binaires installés par Apt (packages.txt) ou via le Manager.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    
    # User-Agent aléatoire pour contourner les protections basiques
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"user-agent={random.choice(ua_list)}")

    # Stratégie de recherche du binaire Chromedriver (Streamlit Cloud vs Local)
    paths = ["/usr/bin/chromedriver", "/usr/lib/chromium-browser/chromedriver"]
    service = None
    
    for path in paths:
        if os.path.exists(path):
            service = Service(path)
            break
            
    try:
        if service:
            driver = webdriver.Chrome(service=service, options=options)
        else:
            # Fallback local (Windows/Mac)
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        return driver
    except Exception as e:
        st.error(f"Erreur critique de lancement du navigateur : {e}")
        return None

# --- MOTEUR D'ANALYSE DVF (DONNÉES OFFICIELLES) ---

@st.cache_data(ttl=86400)
def get_market_price_dvf(code_insee):
    """Extraction et calcul du prix m2 moyen via l'API Open Data DVF"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        if "features" in data and len(data["features"]) > 0:
            # Conversion en DataFrame pour traitement vectorisé
            df = pd.DataFrame([f['properties'] for f in data['features']])
            
            # Nettoyage des données aberrantes et nulles
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            
            if not df.empty:
                # Calcul de la moyenne du prix au m2 sur les transactions réelles
                prix_m2_moyen = (df['valeur_fonciere'] / df['surface_reelle_bati']).mean()
                return round(prix_m2_moyen)
    except Exception as e:
        st.sidebar.warning(f"Note : DVF indisponible ({e})")
        return 0
    return 0

# --- MOTEUR DE SCRAPING RÉEL (LOGIC-IMMO) ---

def run_scraping_engine(ville_nom, budget_max):
    """
    Navigue sur le web, charge les annonces et extrait les données brutes.
    """
    driver = get_driver()
    if not driver:
        return []

    results = []
    # Formatage de l'URL pour Logic-Immo
    ville_slug = ville_nom.lower().replace(" ", "-")
    target_url = f"https://www.logic-immo.com/vente-immobilier-{ville_slug},100_1/options/prix-max={budget_max}"
    
    try:
        driver.get(target_url)
        # Simulation d'un temps de lecture (anti-bot)
        time.sleep(random.uniform(4.5, 7.2))
        
        # Parsing du contenu HTML généré
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Sélecteur de cartes d'annonces (ajusté selon la structure DOM actuelle)
        annonce_cards = soup.select('div[class*="CardProperty"]') or soup.select('div[class*="annonce"]')
        
        for card in annonce_cards[:15]: # Analyse des 15 premières opportunités
            try:
                # Extraction du Prix (recherche du symbole € et nettoyage)
                price_elem = card.find(text=re.compile(r"€"))
                price = int(''.join(re.findall(r'\d+', price_elem))) if price_elem else 0
                
                # Extraction Surface (recherche de m²)
                surf_elem = card.find(text=re.compile(r"m²"))
                surface = int(''.join(re.findall(r'\d+', surf_elem))) if surf_elem else 0
                
                # Extraction Image
                img_tag = card.find('img')
                img_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else "https://via.placeholder.com/400x300"
                
                # Titre de l'annonce
                title_elem = card.find(['h2', 'h3'])
                title = title_elem.text.strip() if title_elem else "Appartement"
                
                if price > 0 and surface > 0:
                    results.append({
                        "id": random.randint(10000, 99999),
                        "titre": title,
                        "prix": price,
                        "surface": surface,
                        "img": img_url,
                        "url": target_url
                    })
            except Exception:
                continue
    finally:
        driver.quit() # Fermeture obligatoire pour libérer la RAM
        
    return results

# --- LOGIQUE DE RENDEMENT ---

def analyze_opportunity(prix, surface, prix_m2_marche):
    """Calcule la rentabilité et la décote comparative"""
    if prix_m2_marche <= 0: return 0, 0
    
    prix_m2_annonce = prix / surface
    decote = ((prix_m2_marche - prix_m2_annonce) / prix_m2_marche) * 100
    
    # Estimation loyer : basées sur 0.55% du prix de marché mensuel (standard prudent)
    loyer_estime = (prix_m2_marche * 0.0055) * surface
    renta_brute = ((loyer_estime * 12) / prix) * 100
    
    return round(decote, 1), round(renta_brute, 2)

# --- INTERFACE UTILISATEUR (STREAMLIT) ---

if 'pepites' not in st.session_state:
    st.session_state.pepites = []

st.title("🏘️ InvestImmo Bot PRO : Analyseur Haute Précision")
st.caption("Données temps réel : Logic-Immo | Comparatif : DVF Notaires")
st.markdown("---")

tab_live, tab_pepites = st.tabs(["🔍 Analyse du Marché", "💎 Pépites Détectées"])

with st.sidebar:
    st.header("⚙️ Configuration")
    input_ville = st.text_input("Ville cible", "Versailles")
    input_budget = st.number_input("Budget Max (€)", value=400000, step=10000)
    
    st.divider()
    lancer_scan = st.button("🚀 Lancer le Scan Selenium", use_container_width=True)
    
    if st.button("🗑️ Vider l'historique"):
        st.session_state.pepites = []
        st.rerun()

if lancer_scan:
    with tab_live:
        # 1. Identification Géographique (API Gouv)
        geo_res = requests.get(f"https://geo.api.gouv.fr/communes?nom={input_ville}&fields=code,population").json()
        
        if geo_res:
            ville_data = geo_res[0]
            code_insee = ville_data['code']
            
            # 2. Récupération prix du marché
            prix_ref = get_market_price_dvf(code_insee)
            
            st.subheader(f"📍 Rapport Secteur : {ville_data['nom']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Population", f"{ville_data['population']:,} hab.")
            c2.metric("Prix m² Moyen (DVF)", f"{prix_ref} €" if prix_ref > 0 else "N/A")
            c3.metric("Budget Max", f"{input_budget:,} €")
            
            # 3. Scraping Selenium
            st.divider()
            with st.spinner("Le navigateur parcourt les annonces en temps réel..."):
                annonces = run_scraping_engine(ville_data['nom'], input_budget)
            
            if annonces:
                for a in annonces:
                    decote, renta = analyze_opportunity(a['prix'], a['surface'], prix_ref)
                    a['decote'] = decote
                    a['renta'] = renta
                    
                    # Stockage si pépite (Renta > 7.5%)
                    if renta >= 7.5:
                        if not any(item['id'] == a['id'] for item in st.session_state.pepites):
                            st.session_state.pepites.append(a)
                    
                    # Affichage Carte
                    with st.container(border=True):
                        col_i, col_d = st.columns([1, 2])
                        with col_i:
                            st.image(a['img'], use_container_width=True)
                        with col_d:
                            st.write(f"### {a['titre']}")
                            st.write(f"💰 **{a['prix']:,} €** | 📐 **{a['surface']} m²**")
                            
                            if renta > 0:
                                st.write(f"📊 Rentabilité : **{renta}%** | Décote marché : {decote}%")
                                if decote > 15:
                                    st.success("🔥 OPPORTUNITÉ RARE : Forte décote détectée !")
                            
                            st.link_button("Ouvrir l'annonce", a['url'], use_container_width=True)
            else:
                st.warning("Aucune annonce n'a été récupérée. Le site bloque peut-être l'accès.")
        else:
            st.error("Désolé, ville non reconnue par l'API Géo.")

with tab_pepites:
    st.header("💎 Top Opportunités de la Session")
    if not st.session_state.pepites:
        st.info("Aucune pépite détectée pour le moment. Lancez un scan.")
    else:
        # Tri par rentabilité décroissante
        data_p = sorted(st.session_state.pepites, key=lambda x: x['renta'], reverse=True)
        for p in data_p:
            with st.expander(f"⭐ {p['renta']}% de Renta - {p['prix']:,}€ - {p['titre']}"):
                st.write(f"Prix au m² : **{round(p['prix']/p['surface'])} €**")
                st.write(f"Décote comparative : **{p['decote']}%**")
                st.link_button("Lien direct vers le bien", p['url'])
