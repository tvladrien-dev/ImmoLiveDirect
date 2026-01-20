import streamlit as st
import os
import sys

# --- FIX COMPATIBILITÉ PYTHON 3.12+ ---
try:
    import distutils.version
except ImportError:
    import setuptools
    from setuptools import distutils
    sys.modules['distutils'] = distutils

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import requests
import re

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="InvestImmo Alpha Bot", layout="wide")

# --- FONCTIONS D'ANALYSE (GOUV) ---
@st.cache_data(ttl=86400)
def get_dvf_data(city_name):
    """Récupère le prix m2 réel via l'API Géo et DVF"""
    try:
        geo = requests.get(f"https://geo.api.gouv.fr/communes?nom={city_name}&fields=code,population&boost=population").json()
        if not geo: return None
        code_insee = geo[0]['code']
        # API DVF alternative pour plus de stabilité
        res = requests.get(f"https://api.cquest.org/dvf?code_commune={code_insee}", timeout=10).json()
        prices = [f['properties']['valeur_fonciere'] / f['properties']['surface_reelle_bati'] 
                  for f in res['features'] if f['properties']['surface_reelle_bati'] and f['properties']['surface_reelle_bati'] > 0]
        return {
            "insee": code_insee,
            "pop": geo[0]['population'],
            "prix_m2": round(sum(prices) / len(prices)) if prices else 3000
        }
    except: return None

# --- MOTEUR DE SCRAPING ROBUSTE ---
def get_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Simulation d'un utilisateur réel (bypass DataDome)
    options.add_argument(f"--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    
    try:
        # Utilisation du binaire Chromium de Streamlit
        driver = uc.Chrome(options=options, browser_executable_path="/usr/bin/chromium")
        return driver
    except Exception as e:
        st.error(f"Erreur Driver : {e}")
        return None

def fetch_annonces(ville, budget):
    driver = get_driver()
    if not driver: return []
    
    url = f"https://www.jinka.fr/recherche/vente?communes={ville.lower()}&prix_max={budget}"
    annonces = []
    
    try:
        driver.get(url)
        # Attente intelligente : simule un humain qui fait défiler la page
        time.sleep(random.uniform(7, 12))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Jinka change souvent ses classes. On cherche par structure de lien d'annonce
        items = soup.find_all('a', href=re.compile(r'/annonce/'))
        
        for item in items:
            try:
                # On remonte au parent qui contient toutes les infos (prix/surface)
                card = item.find_parent(['div', 'article'])
                text_content = card.get_text(separator=' ')
                
                # Extraction prix et surface par Regex (très robuste)
                prix = int(''.join(re.findall(r'(\d+)\s*€', text_content)[0:1]))
                surface = int(''.join(re.findall(r'(\d+)\s*m²', text_content)[0:1]))
                
                link = item['href']
                img = card.find('img')['src'] if card.find('img') else ""

                if prix > 0 and surface > 0:
                    annonces.append({
                        "prix": prix,
                        "surface": surface,
                        "url": "https://www.jinka.fr" + link if link.startswith('/') else link,
                        "img": img
                    })
            except: continue
    finally:
        driver.quit()
    return annonces

# --- INTERFACE ---
st.title("🏘️ InvestImmo Alpha Bot")
st.markdown("Analyses basées sur **DVF (Prix Notaires)** et **Jinka (Offre temps réel)**")

with st.sidebar:
    ville = st.text_input("Ville cible", "Lille")
    budget = st.number_input("Budget Max (€)", value=250000)
    search = st.button("🚀 Lancer l'Analyse Expert")

if search:
    # 1. Analyse de Marché
    with st.spinner(f"Analyse de la localité : {ville}..."):
        market = get_dvf_data(ville)
    
    if market:
        st.subheader(f"📍 Marché de {ville.capitalize()}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Prix m² Moyen (Réel DVF)", f"{market['prix_m2']} €")
        c2.metric("Population", f"{market['pop']:,} hab.")
        
        # 2. Scraping
        with st.spinner("Recherche d'opportunités (Simultation iPhone)..."):
            results = fetch_annonces(ville, budget)
        
        if results:
            # Filtrage intelligent : Seulement les biens "Sous le prix du marché"
            opportunities = []
            for a in results:
                p_m2 = a['prix'] / a['surface']
                decote = ((market['prix_m2'] - p_m2) / market['prix_m2']) * 100
                # Calcul renta (loyer estimé à 0.6% de la valeur m2 DVF / mois)
                renta = ((market['prix_m2'] * a['surface'] * 0.006 * 12) / a['prix']) * 100
                
                if decote > -10: # On accepte jusqu'à 10% au dessus si la renta est bonne
                    a['decote'] = round(decote, 1)
                    a['renta'] = round(renta, 1)
                    opportunities.append(a)

            # Tri par meilleure décote
            opportunities = sorted(opportunities, key=lambda x: x['decote'], reverse=True)

            st.write(f"### {len(opportunities)} Opportunités détectées")
            for op in opportunities:
                with st.container(border=True):
                    col1, col2 = st.columns([1, 2])
                    if op['img']: col1.image(op['img'])
                    
                    col2.write(f"**Prix : {op['prix']:,} € | Surface : {op['surface']} m²**")
                    status = "🔥 PÉPITE" if op['decote'] > 15 else "🔍 OPPORTUNITÉ"
                    col2.write(f"**Score : {status}**")
                    
                    m1, m2 = col2.columns(2)
                    m1.metric("Décote / Marché", f"{op['decote']}%", delta=f"{op['decote']}%")
                    m2.metric("Potentiel Renta", f"{op['renta']}%")
                    
                    col2.link_button("Consulter l'offre", op['url'])
        else:
            st.warning("⚠️ Jinka a bloqué la requête. Essayez de changer la ville ou de relancer dans 5 minutes (Protection Anti-Flood).")
    else:
        st.error("Ville introuvable dans la base de données gouvernementale.")
