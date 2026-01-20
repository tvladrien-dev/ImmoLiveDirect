import streamlit as st
import requests
import pandas as pd
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import re
import time

# --- CONFIGURATION ET FIX COMPATIBILITÉ ---
import sys
try:
    from setuptools import distutils
    sys.modules['distutils'] = distutils
except:
    pass

st.set_page_config(page_title="Real Estate Alpha Bot", layout="wide")

# --- 1. MOTEUR D'ANALYSE DE LA VILLE (ATTRACTIVITÉ) ---
@st.cache_data
def get_city_metrics(ville_nom):
    """Récupère les données d'attractivité via API Geo Gouv"""
    url = f"https://geo.api.gouv.fr/communes?nom={ville_nom}&fields=code,population,codesPostaux&boost=population"
    res = requests.get(url).json()
    if res:
        data = res[0]
        # Simulation d'un score d'attractivité basé sur la population et la tension
        score = min(100, (data['population'] / 10000) * 1.5) 
        return data['code'], data['population'], round(score, 1)
    return None, None, None

# --- 2. ESTIMATION PRIX DU MARCHÉ (DVF) ---
@st.cache_data
def get_market_price(code_insee):
    """Récupère le prix moyen réel m2 (Données Notaires)"""
    # Utilisation de l'API cquest qui indexe les DVF
    url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
    try:
        data = requests.get(url, timeout=10).json()
        prices = [f['properties']['valeur_fonciere'] / f['properties']['surface_reelle_bati'] 
                  for f in data['features'] if f['properties']['surface_reelle_bati'] > 0]
        return round(sum(prices) / len(prices)) if prices else 0
    except:
        return 2500 # Prix par défaut si erreur API

# --- 3. SCRAPER FURTIF (JINKA) ---
def scrape_jinka(ville, budget_max):
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    driver = uc.Chrome(options=options, browser_executable_path="/usr/bin/chromium")
    
    results = []
    url = f"https://www.jinka.fr/recherche/vente?communes={ville.lower()}&prix_max={budget_max}"
    
    try:
        driver.get(url)
        time.sleep(10) # Temps pour bypasser les protections
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Logique de capture simplifiée pour l'exemple
        for card in soup.select('article')[:10]:
            try:
                p_text = card.find(text=re.compile(r"€")).replace(" ", "")
                prix = int(re.search(r'\d+', p_text).group())
                s_text = card.find(text=re.compile(r"m²")).replace(" ", "")
                surface = int(re.search(r'\d+', s_text).group())
                link = card.find('a')['href']
                
                results.append({"prix": prix, "surface": surface, "url": link})
            except: continue
    finally:
        driver.quit()
    return results

# --- 4. INTERFACE ET LOGIQUE D'INVESTISSEMENT ---
st.title("🚀 Real Estate Alpha Bot")
st.sidebar.header("Paramètres d'Investissement")

target_city = st.sidebar.text_input("Ville cible", "Marseille")
budget = st.sidebar.number_input("Budget Max (€)", value=200000)

if st.sidebar.button("Analyser les Opportunités"):
    code_insee, pop, attract_score = get_city_metrics(target_city)
    
    if code_insee:
        price_m2_ref = get_market_price(code_insee)
        
        # Affichage metrics ville
        st.subheader(f"📊 Analyse de {target_city.capitalize()}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Prix Marché (m²)", f"{price_m2_ref} €")
        col2.metric("Score Attractivité", f"{attract_score}/100")
        col3.metric("Population", f"{pop:,}")

        # Lancement du Bot
        with st.spinner("Recherche d'opportunités sous le prix du marché..."):
            deals = scrape_jinka(target_city, budget)
        
        if deals:
            st.success(f"{len(deals)} annonces trouvées. Analyse financière en cours...")
            
            for d in deals:
                p_m2_annonce = d['prix'] / d['surface']
                # Calcul de l'opportunité (Décote)
                decote = ((price_m2_ref - p_m2_annonce) / price_m2_ref) * 100
                
                # Estimation Potentiel Locatif (Renta Brute théorique)
                # Basé sur un loyer moyen estimé à 0.5% de la valeur vénale/mois
                loyer_est = (price_m2_ref * d['surface'] * 0.006) 
                renta = ((loyer_est * 12) / d['prix']) * 100

                # Affichage conditionnel : Uniquement les vraies opportunités
                if decote > 5 or renta > 7:
                    with st.expander(f"💎 OPPORTUNITÉ : {d['prix']:,} € - {d['surface']} m²"):
                        c1, c2 = st.columns(2)
                        status = "🔥 EXCELLENT" if decote > 15 else "✅ BON"
                        c1.write(f"**Prix m² :** {round(p_m2_annonce)} € (Réf: {price_m2_ref} €)")
                        c1.write(f"**Décote :** {round(decote, 1)}% ({status})")
                        c2.write(f"**Renta. Estimée :** {round(renta, 1)}% brute")
                        st.link_button("Ouvrir l'annonce", f"https://www.jinka.fr{d['url']}")
        else:
            st.warning("Aucune annonce ne correspond aux critères ou le bot a été bloqué.")
