import streamlit as st
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
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
    page_title="InvestImmo Bot PRO - Master Edition", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- INITIALISATION DU NAVIGATEUR FURTIF ---

def get_driver():
    """
    Initialise Undetected Chromedriver pour Streamlit Cloud.
    Utilise le binaire Chromium installé via packages.txt.
    """
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Masquage des variables d'automatisation (bypass DataDome)
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # User-Agent réaliste et varié pour éviter le fingerprinting
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"user-agent={random.choice(ua_list)}")

    try:
        # Chemin binaire spécifique à l'environnement Streamlit Cloud
        driver = uc.Chrome(
            options=options,
            browser_executable_path="/usr/bin/chromium",
            headless=True
        )
        return driver
    except Exception as e:
        st.error(f"Erreur d'initialisation du driver : {e}")
        return None

# --- MOTEUR D'ANALYSE DVF (DONNÉES ÉTAT) ---

@st.cache_data(ttl=86400)
def get_market_price_dvf(code_insee):
    """Calcule le prix m2 moyen réel du secteur via l'API cquest (DVF)"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        if "features" in data and len(data["features"]) > 0:
            df = pd.DataFrame([f['properties'] for f in data['features']])
            # Nettoyage des données numériques
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            
            if not df.empty:
                return round((df['valeur_fonciere'] / df['surface_reelle_bati']).mean())
    except Exception:
        return 0
    return 0

# --- MOTEUR DE SCRAPING (JINKA) ---

def run_scraping_engine(ville_nom, budget_max):
    """Simule une navigation humaine sur Jinka pour extraire les annonces"""
    driver = get_driver()
    if not driver:
        return []

    results = []
    ville_clean = ville_nom.lower().strip()
    target_url = f"https://www.jinka.fr/recherche/vente?communes={ville_clean}&prix_max={budget_max}"
    
    try:
        driver.get(target_url)
        
        # --- PHASE FURTIVE ---
        # 1. Attente aléatoire longue pour simuler la lecture
        time.sleep(random.uniform(8.0, 12.0))
        
        # 2. Scrolling irrégulier (charge le contenu dynamique)
        for _ in range(3):
            scroll = random.randint(400, 900)
            driver.execute_script(f"window.scrollBy(0, {scroll});")
            time.sleep(random.uniform(1.5, 3.0))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Identification des cartes d'annonces par regex sur les classes CSS
        cards = soup.find_all(['article', 'div'], class_=re.compile(r"AdCard|ad-card|PropertyCard"))
        
        if not cards: # Fallback
            cards = soup.select('div[class*="ad"]') or soup.select('div[class*="card"]')

        for card in cards[:25]:
            try:
                # Extraction Prix
                price_text = card.find(text=re.compile(r"€"))
                price = int(''.join(re.findall(r'\d+', price_text))) if price_text else 0
                
                # Extraction Surface
                surf_text = card.find(text=re.compile(r"m²"))
                surface = int(''.join(re.findall(r'\d+', surf_text))) if surf_text else 0
                
                # Extraction Image
                img_tag = card.find('img')
                img_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else "https://via.placeholder.com/400x300"
                
                # Lien
                link_tag = card.find('a', href=True)
                ad_url = "https://www.jinka.fr" + link_tag['href'] if link_tag and link_tag['href'].startswith('/') else link_tag['href'] if link_tag else target_url
                
                if price > 0 and surface > 0:
                    results.append({
                        "id": random.randint(1000, 9999),
                        "titre": f"{surface}m² à {ville_nom}",
                        "prix": price,
                        "surface": surface,
                        "img": img_url,
                        "url": ad_url
                    })
            except Exception:
                continue
    finally:
        driver.quit()
        
    return results

# --- ANALYSE FINANCIÈRE ---

def analyze_opportunity(prix, surface, prix_m2_marche):
    """Calcule la décote et la rentabilité théorique"""
    if prix_m2_marche <= 0: return 0, 0
    
    prix_m2_annonce = prix / surface
    decote = ((prix_m2_marche - prix_m2_annonce) / prix_m2_marche) * 100
    
    # Estimation loyer : basée sur 0.55% de la valeur de marché/mois
    loyer_mensuel = (prix_m2_marche * surface * 0.0055) 
    renta_brute = ((loyer_mensuel * 12) / prix) * 100
    
    return round(decote, 1), round(renta_brute, 2)

# --- INTERFACE STREAMLIT ---

if 'pepites' not in st.session_state:
    st.session_state.pepites = []

st.title("🏘️ InvestImmo Bot PRO")
st.caption("Version Intégrale : Scraping Jinka + Data DVF")

tab_scan, tab_db = st.tabs(["🔍 Nouveau Scan", "💎 Pépites Sauvegardées"])

with st.sidebar:
    st.header("⚙️ Configuration")
    input_ville = st.text_input("Ville cible", "Marseille")
    input_budget = st.number_input("Budget Max (€)", value=200000, step=10000)
    st.divider()
    lancer_scan = st.button("🚀 Lancer l'analyse", use_container_width=True)
    if st.button("🗑️ Vider le cache"):
        st.session_state.pepites = []
        st.rerun()

if lancer_scan:
    with tab_scan:
        # Géo-localisation Code INSEE
        geo_res = requests.get(f"https://geo.api.gouv.fr/communes?nom={input_ville}&fields=code,population&boost=population").json()
        
        if geo_res:
            ville_data = geo_res[0]
            insee = ville_data['code']
            prix_ref = get_market_price_dvf(insee)
            
            st.subheader(f"📊 État du marché : {ville_data['nom']}")
            c1, c2 = st.columns(2)
            c1.metric("Prix m² moyen (DVF)", f"{prix_ref} €/m²")
            c2.metric("Population", f"{ville_data['population']:,} hab.")
            
            with st.spinner("Extraction furtive des annonces..."):
                annonces = run_scraping_engine(ville_data['nom'], input_budget)
            
            if annonces:
                for a in annonces:
                    decote, renta = analyze_opportunity(a['prix'], a['surface'], prix_ref)
                    a['decote'], a['renta'] = decote, renta
                    
                    # Logique "Pépite"
                    if renta > 7.5 or decote > 15:
                        if not any(p['url'] == a['url'] for p in st.session_state.pepites):
                            st.session_state.pepites.append(a)
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([1, 2])
                        col1.image(a['img'])
                        col2.write(f"### {a['prix']:,} € - {a['surface']} m²")
                        if prix_ref > 0:
                            m1, m2 = col2.columns(2)
                            m1.metric("Rendement Brut", f"{renta}%")
                            m2.metric("Décote Marché", f"{decote}%")
                        col2.link_button("🌐 Voir sur Jinka", a['url'])
            else:
                st.warning("Aucune annonce trouvée. Vérifiez l'orthographe ou le budget.")
        else:
            st.error("Ville inconnue.")

with tab_db:
    if not st.session_state.pepites:
        st.info("Aucune pépite détectée pour le moment.")
    else:
        for p in st.session_state.pepites:
            with st.expander(f"💎 {p['renta']}% - {p['prix']:,}€ ({p['surface']}m²)"):
                st.write(f"Secteur : {input_ville}")
                st.write(f"Décote : {p['decote']}%")
                st.link_button("Ouvrir l'annonce", p['url'])
