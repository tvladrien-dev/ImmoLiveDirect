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
    page_title="InvestImmo Bot PRO - Real Data", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- INITIALISATION DU NAVIGATEUR (OPTIMISÉ STREAMLIT CLOUD) ---

def get_driver():
    """Configure Selenium pour fonctionner sur les serveurs Streamlit"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    
    # Rotation de User-Agent pour paraître humain
    ua = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"user-agent={random.choice(ua)}")
    
    try:
        # Tentative via le binaire installé par packages.txt
        service = Service("/usr/bin/chromedriver")
        return webdriver.Chrome(service=service, options=options)
    except:
        try:
            # Fallback via webdriver-manager
            service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
            return webdriver.Chrome(service=service, options=options)
        except Exception as e:
            st.error(f"Erreur d'initialisation Selenium : {e}")
            return None

# --- ANALYSE DE MARCHÉ (DVF NOTAIRES) ---

@st.cache_data(ttl=86400)
def get_market_price_dvf(code_insee):
    """Récupère le prix m2 réel des ventes passées"""
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        res = requests.get(url, timeout=10).json()
        if "features" in res and len(res["features"]) > 0:
            df = pd.DataFrame([f['properties'] for f in res['features']])
            df['valeur_fonciere'] = pd.to_numeric(df['valeur_fonciere'], errors='coerce')
            df['surface_reelle_bati'] = pd.to_numeric(df['surface_reelle_bati'], errors='coerce')
            df = df.dropna(subset=['valeur_fonciere', 'surface_reelle_bati'])
            df = df[df['surface_reelle_bati'] > 0]
            if not df.empty:
                return round((df['valeur_fonciere'] / df['surface_reelle_bati']).mean())
    except:
        return 0
    return 0

# --- MOTEUR DE SCRAPING RÉEL ---

def scrape_logic_immo(ville, budget_max):
    """Effectue un vrai scraping sur Logic-Immo via Selenium"""
    driver = get_driver()
    if not driver:
        return []
    
    results = []
    # Nettoyage du nom de la ville pour l'URL
    ville_slug = ville.lower().replace(" ", "-")
    search_url = f"https://www.logic-immo.com/vente-immobilier-{ville_slug},100_1/options/prix-max={budget_max}"
    
    try:
        driver.get(search_url)
        # Délai aléatoire pour simuler une lecture humaine
        time.sleep(random.uniform(5, 8))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # On cherche les conteneurs d'annonces
        # Note : Les classes CSS de Logic-Immo changent, on utilise des sélecteurs plus larges
        items = soup.select('div[class*="CardProperty"]') or soup.select('div[class*="annonce"]')
        
        for item in items[:10]: # On limite à 10 pour éviter le timeout
            try:
                # Extraction Prix
                price_text = item.find(text=re.compile(r"€"))
                price = int(''.join(re.findall(r'\d+', price_text))) if price_text else 0
                
                # Extraction Surface
                surf_text = item.find(text=re.compile(r"m²"))
                surface = int(''.join(re.findall(r'\d+', surf_text))) if surf_text else 0
                
                # Image et Titre
                img_tag = item.find('img')
                img_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else "https://via.placeholder.com/400x300"
                title = item.find(['h2', 'h3']).text.strip() if item.find(['h2', 'h3']) else "Appartement"
                
                if price > 0 and surface > 0:
                    results.append({
                        "id": random.randint(1000, 9999),
                        "titre": title,
                        "prix": price,
                        "surface": surface,
                        "url": search_url, # Lien vers la recherche globale
                        "img": img_url,
                        "desc": f"Annonce réelle détectée à {ville}."
                    })
            except:
                continue
    finally:
        driver.quit()
    return results

# --- INTERFACE ---

if 'pepites' not in st.session_state:
    st.session_state.pepites = []

st.title("🏘️ InvestImmo : Scan & Analyse en Temps Réel")

tab_scan, tab_pepites = st.tabs(["🔍 Scan en Direct", "🔥 Page Opportunités"])

with st.sidebar:
    st.header("⚙️ Paramètres de Scan")
    ville_target = st.text_input("Ville", "Versailles")
    budget_target = st.number_input("Budget Max (€)", value=400000)
    btn_scan = st.button("🚀 Lancer le Bot Selenium", use_container_width=True)
    
    if st.button("🗑️ Vider la mémoire"):
        st.session_state.pepites = []
        st.rerun()

if btn_scan:
    with tab_scan:
        # 1. Analyse Géo
        geo = requests.get(f"https://geo.api.gouv.fr/communes?nom={ville_target}&fields=code,population").json()
        if geo:
            c_insee = geo[0]['code']
            p_m2_marche = get_market_price_dvf(c_insee)
            
            st.info(f"📍 Ville identifiée : **{geo[0]['nom']}** | Prix Marché : **{p_m2_marche}€/m²**")
            
            # 2. Scraping Selenium
            with st.spinner("Le navigateur headless analyse Logic-Immo..."):
                annonces = scrape_logic_immo(geo[0]['nom'], budget_target)
            
            if annonces:
                for a in annonces:
                    # Calcul Renta & Décote
                    p_m2_annonce = a['prix'] / a['surface']
                    decote = round(((p_m2_marche - p_m2_annonce) / p_m2_marche) * 100, 1) if p_m2_marche > 0 else 0
                    renta = round(((p_m2_marche * 0.0055 * 12) / a['prix']) * 100, 2)
                    
                    # Filtre Opportunité
                    if renta >= 7.0:
                        if not any(o['id'] == a['id'] for o in st.session_state.pepites):
                            a['renta'], a['decote'] = renta, decote
                            st.session_state.pepites.append(a)
                    
                    with st.container(border=True):
                        c1, c2 = st.columns([1, 2])
                        c1.image(a['img'], use_container_width=True)
                        c2.subheader(a['titre'])
                        c2.write(f"💰 **{a['prix']:,} €** | 📐 **{a['surface']} m²**")
                        c2.write(f"📊 Renta estimée : **{renta}%** | Décote : {decote}%")
                        st.link_button("Lien vers la recherche", a['url'])
            else:
                st.warning("Aucune annonce n'a pu être extraite. Le site bloque peut-être l'adresse IP du serveur.")
        else:
            st.error("Ville non reconnue.")

with tab_pepites:
    st.header("💎 Opportunités de la session")
    if not st.session_state.pepites:
        st.info("Aucun bien avec une rentabilité > 7% n'a été trouvé pour le moment.")
    else:
        for p in sorted(st.session_state.pepites, key=lambda x: x['renta'], reverse=True):
            with st.expander(f"⭐ {p['renta']}% - {p['titre']} ({p['prix']:,}€)"):
                st.write(f"Décote constatée : **{p['decote']}%**")
                st.link_button("Voir la source", p['url'])
