import streamlit as st
import os
import sys

# --- FIX CRITIQUE POUR PYTHON 3.12+ / STREAMLIT CLOUD ---
# Correction de l'erreur 'ModuleNotFoundError: No module named distutils'
try:
    from distutils.version import LooseVersion
except ImportError:
    try:
        import setuptools
        from setuptools import distutils
        sys.modules['distutils'] = distutils
    except ImportError:
        st.error("Le module 'setuptools' est manquant. Ajoutez-le à votre requirements.txt.")

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import time
import random
import requests
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
    Cible le binaire Chromium installé via packages.txt.
    """
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Masquage des variables d'automatisation pour bypasser DataDome/Cloudflare
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # User-Agent réaliste pour éviter d'être identifié comme un bot
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    try:
        # Chemin absolu vers le binaire installé par Streamlit (Debian)
        driver = uc.Chrome(
            options=options,
            browser_executable_path="/usr/bin/chromium",
            headless=True
        )
        return driver
    except Exception as e:
        st.error(f"Erreur d'initialisation du driver : {e}")
        return None

# --- MOTEUR D'ANALYSE DVF (DONNÉES OFFICIELLES) ---

@st.cache_data(ttl=86400)
def get_market_price_dvf(code_insee):
    """Calcul du prix m2 moyen réel via l'API Open Data DVF (cquest)"""
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

# --- MOTEUR DE SCRAPING JINKA (ANTI-DÉTECTION) ---

def run_scraping_engine(ville_nom, budget_max):
    driver = get_driver()
    if not driver:
        return []

    results = []
    ville_slug = ville_nom.lower().strip()
    target_url = f"https://www.jinka.fr/recherche/vente?communes={ville_slug}&prix_max={budget_max}"
    
    try:
        driver.get(target_url)
        
        # --- SIMULATION COMPORTEMENTALE HUMAINE ---
        time.sleep(random.uniform(9.0, 14.0)) # Attente aléatoire longue
        
        # Scroll progressif pour déclencher le Lazy Loading
        for _ in range(3):
            scroll = random.randint(500, 1000)
            driver.execute_script(f"window.scrollBy(0, {scroll});")
            time.sleep(random.uniform(1.5, 3.0))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Ciblage des cartes d'annonces
        cards = soup.find_all(['article', 'div'], class_=re.compile(r"AdCard|ad-card|PropertyCard"))
        
        if not cards:
            cards = soup.select('a[href*="/annonce/"]') or soup.find_all('article')

        for card in cards[:25]:
            try:
                # Prix
                price_txt = card.find(text=re.compile(r"€"))
                price = int(''.join(re.findall(r'\d+', price_txt))) if price_txt else 0
                
                # Surface
                surf_txt = card.find(text=re.compile(r"m²"))
                surface = int(''.join(re.findall(r'\d+', surf_txt))) if surf_txt else 0
                
                # Image et URL
                img_tag = card.find('img')
                img_url = img_tag['src'] if img_tag else "https://via.placeholder.com/400x300"
                
                link_tag = card.find('a', href=True) if card.name != 'a' else card
                ad_url = "https://www.jinka.fr" + link_tag['href'] if link_tag['href'].startswith('/') else link_tag['href']
                
                if price > 0 and surface > 0:
                    results.append({
                        "id": random.randint(100000, 999999),
                        "titre": f"{surface}m² à {ville_nom}",
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

# --- LOGIQUE D'ANALYSE FINANCIÈRE ---

def analyze_opportunity(prix, surface, prix_m2_marche):
    if prix_m2_marche <= 0: return 0, 0
    prix_m2_annonce = prix / surface
    decote = ((prix_m2_marche - prix_m2_annonce) / prix_m2_marche) * 100
    
    # Rendement : Loyer estimé à 0.55% de la valeur vénale mensuelle (standard prudent)
    loyer_mensuel = (prix_m2_marche * surface * 0.0055)
    renta_brute = ((loyer_mensuel * 12) / prix) * 100
    
    return round(decote, 1), round(renta_brute, 2)

# --- INTERFACE UTILISATEUR ---

if 'pepites' not in st.session_state:
    st.session_state.pepites = []

st.title("🏘️ Jinka Master-Scraper PRO")
st.markdown("*Mode furtif activé (Bypass DataDome/Python 3.13 Ready)*")
st.divider()

with st.sidebar:
    st.header("⚙️ Configuration")
    input_ville = st.text_input("Ville", "Bordeaux")
    input_budget = st.number_input("Budget Max (€)", value=250000)
    
    st.divider()
    lancer = st.button("🚀 Lancer le Scan Direct", use_container_width=True)
    
    if st.button("🗑️ Reset"):
        st.session_state.pepites = []
        st.rerun()

if lancer:
    # 1. Analyse Géo & Marché
    geo = requests.get(f"https://geo.api.gouv.fr/communes?nom={input_ville}&fields=code,population&boost=population").json()
    
    if geo:
        ville_data = geo[0]
        prix_ref = get_market_price_dvf(ville_data['code'])
        
        st.subheader(f"📍 Analyse Secteur : {ville_data['nom']}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Prix m² Moyen (DVF)", f"{prix_ref} €/m²")
        c2.metric("Population", f"{ville_data['population']:,} hab.")
        c3.metric("Budget Max", f"{input_budget:,} €")
        
        # 2. Scraping
        with st.spinner("Contournement des protections en cours (± 15s)..."):
            annonces = run_scraping_engine(ville_data['nom'], input_budget)
        
        if annonces:
            for a in annonces:
                decote, renta = analyze_opportunity(a['prix'], a['surface'], prix_ref)
                a['renta'], a['decote'] = renta, decote
                
                # Sauvegarde si c'est une pépite (>7% renta ou >10% décote)
                if renta >= 7.0 or decote >= 10:
                    if not any(p['url'] == a['url'] for p in st.session_state.pepites):
                        st.session_state.pepites.append(a)
                
                with st.container(border=True):
                    col_img, col_txt = st.columns([1, 2])
                    col_img.image(a['img'], use_container_width=True)
                    col_txt.write(f"### {a['prix']:,} € | {a['surface']} m²")
                    col_txt.write(f"📊 Renta : **{renta}%** | Décote : **{decote}%**")
                    col_txt.link_button("Voir l'annonce", a['url'], use_container_width=True)
        else:
            st.error("Aucune donnée. Le bot a été détecté ou l'IP est temporairement limitée.")
    else:
        st.error("Ville non trouvée.")

# --- SECTION PÉPITES ---
if st.session_state.pepites:
    st.divider()
    st.header("💎 Opportunités mémorisées")
    for p in st.session_state.pepites:
        st.info(f"Renta : {p['renta']}% | {p['prix']:,}€ | {p['url']}")
