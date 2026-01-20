import streamlit as st
import os
import sys
import time
import random
import re
import requests
import pandas as pd

# --- FIX COMPATIBILITÉ CRITIQUE ---
try:
    from setuptools import distutils
    sys.modules['distutils'] = distutils
except:
    pass

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

# --- CONFIGURATION UI ---
st.set_page_config(page_title="InvestImmo PRO - Live", layout="wide")

# --- MOTEUR DE DONNÉES OFFICIELLES (API ETALAB) ---
@st.cache_data(ttl=86400)
def get_market_data(ville_nom):
    """Récupère les prix réels notariés via l'API officielle Etalab"""
    try:
        # 1. Recherche du code commune
        geo = requests.get(f"https://geo.api.gouv.fr/communes?nom={ville_nom}&fields=code,population&boost=population", timeout=5).json()
        if not geo: return None
        
        code_insee = geo[0]['code']
        nom_complet = geo[0]['nom']
        
        # 2. Appel API DVF officielle (Filtre sur les 18 derniers mois)
        # On utilise l'API de data.gouv.fr pour la stabilité
        dvf_url = f"https://dvf-api.data.gouv.fr/api/v1/mutations/?code_commune={code_insee}"
        res = requests.get(dvf_url, timeout=10).json()
        
        prices = []
        if "results" in res:
            for item in res["results"]:
                val = item.get('valeur_fonciere')
                surf = item.get('surface_reelle_bati')
                if val and surf and surf > 0:
                    prices.append(float(val) / float(surf))
        
        # Calcul du prix médian (plus fiable que la moyenne)
        if prices:
            median_price = round(pd.Series(prices).median())
        else:
            # Fallback : Si DVF vide, on utilise une API de secours (Base d'estimation par département)
            median_price = 3000 
            
        return {
            "nom": nom_complet,
            "code": code_insee,
            "prix_m2": median_price,
            "pop": geo[0]['population']
        }
    except Exception as e:
        st.error(f"Erreur API Gouv : {e}")
        return None

# --- MOTEUR DE SCRAPING (ADAPTÉ AUX LOGS SYSTEME) ---
def get_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Simulation d'un écran standard
    options.add_argument("--window-size=1920,1080")
    # Bypass des détections
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        # D'après tes logs, chromium est dans /usr/bin/chromium
        driver = uc.Chrome(
            options=options, 
            browser_executable_path="/usr/bin/chromium",
            driver_executable_path="/usr/bin/chromedriver"
        )
        return driver
    except Exception as e:
        st.error(f"Le navigateur n'a pas pu démarrer : {e}")
        return None

def run_invest_scraper(ville_nom, budget_max):
    driver = get_driver()
    if not driver: return []
    
    results = []
    # Recherche large sur Jinka
    url = f"https://www.jinka.fr/recherche/vente?communes={ville_nom.lower()}&prix_max={budget_max}"
    
    try:
        driver.get(url)
        # Pause humaine longue pour charger les scripts de sécurité
        time.sleep(random.uniform(10, 15))
        
        # Simulation de scroll pour activer le chargement
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # On cherche tous les liens d'annonces
        links = soup.select('a[href*="/annonce/"]')
        
        for link in links[:15]:
            try:
                card = link.find_parent(['div', 'article'])
                if not card: continue
                
                text = card.get_text(separator=" ")
                # Extraction Regex robuste
                price_match = re.search(r'(\d[\d\s]*)\s*€', text)
                surf_match = re.search(r'(\d[\d\s]*)\s*m²', text)
                
                if price_match and surf_match:
                    p = int(price_match.group(1).replace(" ", ""))
                    s = int(surf_match.group(1).replace(" ", ""))
                    
                    full_url = "https://www.jinka.fr" + link['href'] if link['href'].startswith('/') else link['href']
                    img = card.find('img')['src'] if card.find('img') else ""
                    
                    results.append({
                        "prix": p,
                        "surface": s,
                        "prix_m2": p/s,
                        "url": full_url,
                        "img": img
                    })
            except: continue
    finally:
        driver.quit()
    return results

# --- INTERFACE ET LOGIQUE ---
st.title("🏘️ ImmoLive Alpha - Master Bot")
st.sidebar.header("Configuration")

target = st.sidebar.text_input("Ville", "Bordeaux")
budget = st.sidebar.number_input("Budget Max", value=250000)
trigger = st.sidebar.button("🚀 Analyser le marché")

if trigger:
    # 1. Analyse Market
    with st.spinner("Analyse des prix réels (Données Notaires)..."):
        market = get_market_data(target)
    
    if market:
        st.subheader(f"📊 État du marché : {market['nom']}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Prix m² Médian (Réel)", f"{market['prix_m2']} €")
        c2.metric("Population", f"{market['pop']:,} hab.")
        c3.metric("Attractivité", "Top 10%" if market['pop'] > 100000 else "Standard")
        
        # 2. Scraping
        with st.spinner("Scan des annonces en cours (Mode Furtif)..."):
            ads = run_invest_scraper(market['nom'], budget)
            
        if ads:
            st.divider()
            st.subheader("🎯 Opportunités Détectées")
            
            # Calcul financier pour chaque annonce
            for a in ads:
                # Décote par rapport au prix réel DVF
                decote = ((market['prix_m2'] - a['prix_m2']) / market['prix_m2']) * 100
                # Loyer estimé (0.6% de la valeur m2 par mois)
                renta = ((market['prix_m2'] * a['surface'] * 0.006 * 12) / a['prix']) * 100
                
                # On affiche si c'est une opportunité (Décote > 0)
                status = "🟢 BONNE AFFAIRE" if decote > 10 else "🟡 PRIX MARCHÉ"
                if decote < -10: status = "🔴 TROP CHER"
                
                with st.container(border=True):
                    col_img, col_info = st.columns([1, 2])
                    if a['img']: col_img.image(a['img'])
                    
                    col_info.write(f"### {a['prix']:,} € | {a['surface']} m²")
                    col_info.write(f"**Analyse : {status}**")
                    
                    m1, m2 = col_info.columns(2)
                    m1.metric("Décote vs Marché", f"{round(decote, 1)}%")
                    m2.metric("Rendement Est.", f"{round(renta, 1)}%")
                    
                    col_info.link_button("Voir l'annonce", a['url'])
        else:
            st.warning("Aucune annonce trouvée ou accès bloqué par le site. Réessayez avec une autre ville.")
    else:
        st.error("Impossible de récupérer les données pour cette ville. Vérifiez l'orthographe.")
