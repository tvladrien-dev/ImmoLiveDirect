import streamlit as st
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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
    page_title="InvestImmo Bot PRO - Jinka Edition", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- INITIALISATION DU NAVIGATEUR FURTIF ---

def get_driver():
    """
    Initialise Undetected Chromedriver pour contourner les protections type DataDome/Cloudflare.
    """
    options = uc.ChromeOptions()
    options.add_argument("--headless") # Note: Jinka détecte parfois le headless, à tester.
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Configuration du profil pour paraître humain
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    try:
        # Sur Streamlit Cloud, on doit spécifier l'emplacement du binaire Chrome
        driver = uc.Chrome(
            options=options,
            driver_executable_path="/usr/bin/chromedriver", # Standard Streamlit Cloud
            version_main=114 # Ou laisser vide pour auto-détection
        )
        return driver
    except Exception as e:
        st.error(f"Erreur d'initialisation du driver furtif : {e}")
        # Fallback local plus simple pour tes tests
        try:
            return uc.Chrome(options=options)
        except:
            return None

# --- MOTEUR D'ANALYSE DVF ---
@st.cache_data(ttl=86400)
def get_market_price_dvf(code_insee):
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        if "features" in data and len(data["features"]) > 0:
            df = pd.DataFrame([f['properties'] for f in data['features']])
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            if not df.empty:
                return round((df['valeur_fonciere'] / df['surface_reelle_bati']).mean())
    except:
        return 0
    return 0

# --- MOTEUR DE SCRAPING JINKA (ANTI-BOT) ---

def run_scraping_engine(ville_nom, budget_max):
    driver = get_driver()
    if not driver:
        return []

    results = []
    # Construction de l'URL Jinka (format de recherche classique)
    target_url = f"https://www.jinka.fr/recherche/vente?communes={ville_nom}&prix_max={budget_max}"
    
    try:
        driver.get(target_url)
        
        # --- SIMULATION HUMAINE ---
        # 1. Attente aléatoire longue pour le chargement des scripts Jinka
        time.sleep(random.uniform(6.1, 9.4))
        
        # 2. Scroll progressif pour déclencher le chargement Lazy-Loading des images/annonces
        for i in range(1, 4):
            driver.execute_script(f"window.scrollTo(0, {i * 400});")
            time.sleep(random.uniform(0.5, 1.2))
        
        # Extraction du HTML après exécution du JS
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Sélecteur Jinka (Vérifier les classes qui changent souvent)
        # Jinka utilise souvent des composants React avec des classes type "AdCard"
        cards = soup.select('div[class*="AdCard"]') or soup.find_all('article')
        
        for card in cards[:20]:
            try:
                # Prix
                price_txt = card.find(text=re.compile(r"€"))
                price = int(''.join(re.findall(r'\d+', price_txt))) if price_txt else 0
                
                # Surface
                surf_txt = card.find(text=re.compile(r"m²"))
                surface = int(''.join(re.findall(r'\d+', surf_txt))) if surf_txt else 0
                
                # Image
                img_tag = card.find('img')
                img_url = img_tag['src'] if img_tag else "https://via.placeholder.com/400x300"
                
                # Lien (Crucial sur Jinka : ils utilisent souvent des redirections)
                link_tag = card.find('a', href=True)
                ad_url = "https://www.jinka.fr" + link_tag['href'] if link_tag else target_url
                
                if price > 0 and surface > 0:
                    results.append({
                        "id": random.randint(100000, 999999),
                        "titre": f"Bien à {ville_nom}",
                        "prix": price,
                        "surface": surface,
                        "img": img_url,
                        "url": ad_url
                    })
            except:
                continue
    finally:
        driver.quit()
        
    return results

# --- LOGIQUE DE RENDEMENT ---
def analyze_opportunity(prix, surface, prix_m2_marche):
    if prix_m2_marche <= 0: return 0, 0
    prix_m2_annonce = prix / surface
    decote = ((prix_m2_marche - prix_m2_annonce) / prix_m2_marche) * 100
    loyer_estime = (prix_m2_marche * 0.0055) * surface
    renta_brute = ((loyer_estime * 12) / prix) * 100
    return round(decote, 1), round(renta_brute, 2)

# --- INTERFACE ---
if 'pepites' not in st.session_state:
    st.session_state.pepites = []

st.title("🏘️ Jinka-Scraper PRO (Furtif)")
st.caption("Mode : Undetected-Chromedriver | Bypass DataDome")

with st.sidebar:
    input_ville = st.text_input("Ville", "Paris")
    input_budget = st.number_input("Budget", value=500000)
    lancer = st.button("🚀 Lancer le scan furtif")

if lancer:
    geo_res = requests.get(f"https://geo.api.gouv.fr/communes?nom={input_ville}&fields=code,population").json()
    if geo_res:
        code_insee = geo_res[0]['code']
        prix_ref = get_market_price_dvf(code_insee)
        
        with st.spinner("Contournement des protections Jinka..."):
            annonces = run_scraping_engine(input_ville, input_budget)
            
        if annonces:
            for a in annonces:
                decote, renta = analyze_opportunity(a['prix'], a['surface'], prix_ref)
                a['renta'] = renta
                a['decote'] = decote
                
                if renta >= 7.0: # Seuil pépite
                    st.session_state.pepites.append(a)
                
                with st.container(border=True):
                    c1, c2 = st.columns([1, 2])
                    c1.image(a['img'])
                    c2.write(f"### {a['prix']:,} € - {a['surface']}m²")
                    c2.write(f"Rentabilité estimée : **{renta}%**")
                    c2.link_button("Voir sur Jinka", a['url'])
        else:
            st.error("Le bot a été détecté ou aucune annonce trouvée. Essayez d'augmenter le délai de pause.")
