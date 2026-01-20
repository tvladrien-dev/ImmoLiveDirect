import streamlit as st
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
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

# --- INITIALISATION DU NAVIGATEUR FURTIF (ARCHITECTURE MULTI-OS) ---

def get_driver():
    """
    Initialise Undetected Chromedriver pour contourner les protections type DataDome/Cloudflare.
    Cherche les binaires sur Streamlit Cloud ou installe localement si nécessaire.
    """
    options = uc.ChromeOptions()
    options.add_argument("--headless") # Requis pour Streamlit Cloud
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Masquage avancé : on retire les flags qui trahissent Selenium
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # User-Agent réaliste et varié
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"user-agent={random.choice(ua_list)}")

    try:
        # Tentative de détection du binaire Chrome sur Streamlit Cloud
        chrome_binary = "/usr/bin/google-chrome"
        if os.path.exists(chrome_binary):
            options.binary_location = chrome_binary

        # Initialisation du driver furtif
        driver = uc.Chrome(options=options)
        return driver
    except Exception as e:
        st.error(f"Erreur d'initialisation du driver furtif : {e}")
        return None

# --- MOTEUR D'ANALYSE DVF (OPEN DATA GOUV) ---

@st.cache_data(ttl=86400)
def get_market_price_dvf(code_insee):
    """Extraction et calcul du prix m2 moyen via l'API Open Data DVF (cquest)"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        if "features" in data and len(data["features"]) > 0:
            # Transformation en DataFrame pour nettoyage massif
            df = pd.DataFrame([f['properties'] for f in data['features']])
            
            # Conversion forcée en numérique pour calculs
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            
            # Suppression des lignes corrompues ou sans surface
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            
            if not df.empty:
                # Moyenne pondérée du prix au m2
                prix_m2_moyen = (df['valeur_fonciere'] / df['surface_reelle_bati']).mean()
                return round(prix_m2_moyen)
    except Exception as e:
        st.sidebar.warning(f"Note : DVF non disponible pour ce secteur ({e})")
        return 0
    return 0

# --- MOTEUR DE SCRAPING FURTIF (JINKA) ---

def run_scraping_engine(ville_nom, budget_max):
    """
    Simule une navigation humaine sur Jinka pour extraire les annonces.
    """
    driver = get_driver()
    if not driver:
        return []

    results = []
    # Formatage URL Jinka
    ville_clean = ville_nom.lower().strip()
    target_url = f"https://www.jinka.fr/recherche/vente?communes={ville_clean}&prix_max={budget_max}"
    
    try:
        driver.get(target_url)
        
        # --- PHASE DE SIMULATION HUMAINE ---
        # 1. Temps de lecture aléatoire (anti-empreinte)
        time.sleep(random.uniform(7.5, 12.2))
        
        # 2. Scrolling irrégulier pour charger les composants React/Lazy-load
        for _ in range(3):
            scroll_amount = random.randint(300, 700)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.8, 2.1))
        
        # Extraction du DOM complet généré par le JavaScript
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Identification des cartes d'annonces (Jinka utilise des classes dynamiques)
        # On cible par balise structurelle et contenu partiel
        cards = soup.find_all(['article', 'div'], class_=re.compile(r"AdCard|ad-card|PropertyCard"))
        
        if not cards:
            # Fallback : recherche par sélecteur plus large si Jinka a changé ses classes
            cards = soup.select('div[class*="ad"]') or soup.select('div[class*="card"]')

        for card in cards[:25]: # Analyse des 25 premiers résultats
            try:
                # Extraction du prix (nettoyage des symboles et espaces)
                price_text = card.find(text=re.compile(r"€"))
                price = int(''.join(re.findall(r'\d+', price_text))) if price_text else 0
                
                # Extraction surface (m²)
                surf_text = card.find(text=re.compile(r"m²"))
                surface = int(''.join(re.findall(r'\d+', surf_text))) if surf_text else 0
                
                # Extraction de l'image principale
                img_tag = card.find('img')
                img_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else "https://via.placeholder.com/400x300"
                
                # Lien vers l'annonce
                link_tag = card.find('a', href=True)
                ad_url = "https://www.jinka.fr" + link_tag['href'] if link_tag and link_tag['href'].startswith('/') else link_tag['href'] if link_tag else target_url
                
                if price > 0 and surface > 0:
                    results.append({
                        "id": random.randint(100000, 999999),
                        "titre": f"Appartement {surface}m² - {ville_nom}",
                        "prix": price,
                        "surface": surface,
                        "img": img_url,
                        "url": ad_url
                    })
            except Exception:
                continue
    finally:
        driver.quit() # Nettoyage mémoire obligatoire
        
    return results

# --- LOGIQUE DE RENDEMENT ET DÉCOTE ---

def analyze_opportunity(prix, surface, prix_m2_marche):
    """Calcule la rentabilité brute et la décote par rapport au marché DVF"""
    if prix_m2_marche <= 0: return 0, 0
    
    prix_m2_annonce = prix / surface
    decote = ((prix_m2_marche - prix_m2_annonce) / prix_m2_marche) * 100
    
    # Hypothèse prudente : Loyer annuel = 6.6% de la valeur de marché du bien
    loyer_mensuel_estime = (prix_m2_marche * surface * 0.0055) 
    renta_brute = ((loyer_mensuel_estime * 12) / prix) * 100
    
    return round(decote, 1), round(renta_brute, 2)

# --- INTERFACE UTILISATEUR (STREAMLIT) ---

if 'pepites' not in st.session_state:
    st.session_state.pepites = []

st.title("🏘️ InvestImmo Bot PRO : Jinka & DVF Edition")
st.caption("Scraping Furtif | Analyse Comparative Temps Réel")
st.markdown("---")

tab_scan, tab_db = st.tabs(["🔍 Lancer une Recherche", "💎 Pépites Enregistrées"])

with st.sidebar:
    st.header("⚙️ Paramètres")
    input_ville = st.text_input("Ville cible", "Bordeaux")
    input_budget = st.number_input("Budget Maximum (€)", value=300000, step=5000)
    
    st.divider()
    lancer_scan = st.button("🚀 Lancer le Scan Anti-Bot", use_container_width=True)
    
    if st.button("🗑️ Vider les pépites"):
        st.session_state.pepites = []
        st.rerun()

if lancer_scan:
    with tab_scan:
        # 1. Récupération Code INSEE (API GOUV)
        geo_url = f"https://geo.api.gouv.fr/communes?nom={input_ville}&fields=code,population&boost=population"
        geo_res = requests.get(geo_url).json()
        
        if geo_res:
            ville_data = geo_res[0]
            insee = ville_data['code']
            
            # 2. Analyse de Marché DVF
            prix_ref = get_market_price_dvf(insee)
            
            st.subheader(f"📍 Marché : {ville_data['nom']} ({insee})")
            c1, c2, c3 = st.columns(3)
            c1.metric("Prix m² Moyen (DVF)", f"{prix_ref} €" if prix_ref > 0 else "Indisponible")
            c2.metric("Population", f"{ville_data['population']:,} hab.")
            c3.metric("Zone de recherche", f"{input_budget:,} €")
            
            st.divider()
            
            # 3. Scraping Selenium Furtif
            with st.spinner("Navigation furtive sur Jinka en cours..."):
                annonces = run_scraping_engine(ville_data['nom'], input_budget)
            
            if annonces:
                st.success(f"{len(annonces)} annonces extraites avec succès.")
                
                for a in annonces:
                    decote, renta = analyze_opportunity(a['prix'], a['surface'], prix_ref)
                    a['decote'] = decote
                    a['renta'] = renta
                    
                    # Logique de détection de pépite (Renta > 7.5% ou décote > 15%)
                    if renta >= 7.5 or decote >= 15:
                        if not any(p['id'] == a['id'] for p in st.session_state.pepites):
                            st.session_state.pepites.append(a)
                    
                    # Affichage des résultats
                    with st.container(border=True):
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            st.image(a['img'], use_container_width=True)
                        with col2:
                            st.write(f"### {a['prix']:,} € - {a['surface']} m²")
                            st.write(f"🏷️ **Prix/m² : {round(a['prix']/a['surface'])} €**")
                            
                            if prix_ref > 0:
                                sc1, sc2 = st.columns(2)
                                sc1.metric("Rentabilité", f"{renta}%")
                                sc2.metric("Décote Marché", f"{decote}%")
                            
                            st.link_button("🔗 Consulter sur Jinka", a['url'], use_container_width=True)
            else:
                st.warning("Aucune donnée n'a pu être extraite. Jinka a peut-être bloqué l'accès ou la ville est mal orthographiée.")
        else:
            st.error("Ville non trouvée via l'API Géo-Gouv.")

with tab_db:
    st.header("💎 Vos pépites détectées")
    if not st.session_state.pepites:
        st.info("Aucune opportunité exceptionnelle n'a été trouvée pour le moment.")
    else:
        # Tri par rentabilité
        pepites_sorted = sorted(st.session_state.pepites, key=lambda x: x['renta'], reverse=True)
        for p in pepites_sorted:
            with st.expander(f"🔥 Renta : {p['renta']}% | {p['prix']:,}€ | {p['surface']}m²"):
                st.write(f"Décote calculée : **{p['decote']}%** par rapport au prix moyen DVF.")
                st.link_button("Ouvrir l'opportunité", p['url'])
