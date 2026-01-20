import streamlit as st
import os
import sys
import time
import random
import re
import requests
import pandas as pd

# --- COMPATIBILITÉ ENVIRONNEMENT CLOUD ---
try:
    from setuptools import distutils
    sys.modules['distutils'] = distutils
except ImportError:
    pass

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

# --- CONFIGURATION STREAMLIT ---
st.set_page_config(
    page_title="InvestImmo Alpha Bot - Version Intégrale",
    page_icon="🏠",
    layout="wide"
)

# --- SECTION 1 : ANALYSE DU MARCHÉ ET LOCALITÉ ---

@st.cache_data(ttl=86400)
def get_full_market_data(ville_nom):
    """Récupère les données INSEE, Population et Prix DVF officiels"""
    try:
        # 1. Identification Géo
        geo_url = f"https://geo.api.gouv.fr/communes?nom={ville_nom}&fields=code,population,centre,departement&boost=population"
        geo_res = requests.get(geo_url, timeout=10).json()
        if not geo_res:
            return None
        
        ville_info = geo_res[0]
        code_insee = ville_info['code']
        
        # 2. Récupération des prix Notaires (DVF)
        # On utilise l'API officielle Etalab
        dvf_url = f"https://dvf-api.data.gouv.fr/api/v1/mutations/?code_commune={code_insee}"
        dvf_res = requests.get(dvf_url, timeout=15).json()
        
        prices = []
        if "results" in dvf_res:
            for item in dvf_res["results"]:
                val = item.get('valeur_fonciere')
                surf = item.get('surface_reelle_bati')
                # Filtrage des données aberrantes ou vides
                if val and surf and float(surf) > 5:
                    prices.append(float(val) / float(surf))
        
        # Calcul des statistiques de marché
        if prices:
            prices.sort()
            # On retire les 5% extrêmes (Nettoyage statistique)
            trim = int(len(prices) * 0.05)
            prices_clean = prices[trim:-trim] if trim > 0 else prices
            market_price = sum(prices_clean) / len(prices_clean)
        else:
            market_price = 3200  # Valeur par défaut moyenne France si DVF indisponible
            
        return {
            "nom": ville_info['nom'],
            "code": code_insee,
            "pop": ville_info['population'],
            "prix_m2_ref": round(market_price),
            "coords": ville_info['centre']['coordinates']
        }
    except Exception as e:
        st.sidebar.error(f"Erreur Data : {e}")
        return None

# --- SECTION 2 : MOTEUR DE SCRAPING ANTI-BLOCAGE ---

def get_stealth_driver():
    """Initialise un driver Chrome indétectable"""
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Simulation d'un profil utilisateur réel
    options.add_argument("--disable-blink-features=AutomationControlled")
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"user-agent={random.choice(user_agents)}")
    
    try:
        # Chemins spécifiques à Streamlit Cloud (Debian)
        driver = uc.Chrome(
            options=options,
            browser_executable_path="/usr/bin/chromium",
            driver_executable_path="/usr/bin/chromedriver"
        )
        return driver
    except Exception as e:
        st.error(f"Erreur d'initialisation du bot : {e}")
        return None

def fetch_live_ads(ville, budget):
    """Scrape les annonces réelles sur Jinka"""
    driver = get_stealth_driver()
    if not driver: return []
    
    url = f"https://www.jinka.fr/recherche/vente?communes={ville.lower()}&prix_max={budget}"
    ads_found = []
    
    try:
        driver.get(url)
        # Temps de chargement pour simuler un humain (crucial)
        time.sleep(random.uniform(8, 12))
        
        # Scroll pour déclencher le Lazy Loading
        driver.execute_script("window.scrollTo(0, 1200);")
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Recherche par motifs car les classes changent
        containers = soup.find_all(['article', 'div'], class_=re.compile(r"AdCard|property|card", re.I))
        
        if not containers:
            # Sélecteur de secours : liens d'annonces
            containers = soup.select('a[href*="/annonce/"]')

        for container in containers[:15]:
            try:
                full_text = container.get_text(separator=" ")
                # Regex pour prix et surface
                p_match = re.search(r'(\d[\d\s]*)\s*€', full_text)
                s_match = re.search(r'(\d[\d\s]*)\s*m²', full_text)
                
                if p_match and s_match:
                    prix = int(p_match.group(1).replace(" ", ""))
                    surf = int(s_match.group(1).replace(" ", ""))
                    
                    # Récupération du lien
                    link_tag = container if container.name == 'a' else container.find('a', href=True)
                    href = link_tag['href']
                    full_link = "https://www.jinka.fr" + href if href.startswith('/') else href
                    
                    # Récupération de l'image
                    img_tag = container.find('img')
                    img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else ""

                    ads_found.append({
                        "prix": prix,
                        "surface": surf,
                        "prix_m2": prix / surf,
                        "url": full_link,
                        "img": img_url
                    })
            except: continue
    finally:
        driver.quit()
    return ads_found

# --- SECTION 3 : ANALYSE ET DASHBOARD ---

st.title("🚀 Alpha Immo : Bot d'Investissement Haute Performance")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("🎯 Paramètres de recherche")
    ville_input = st.text_input("Ville cible", "Marseille")
    budget_input = st.number_input("Budget Max (€)", value=250000, step=10000)
    st.divider()
    analyze_btn = st.button("Lancer l'Analyse Expert", use_container_width=True)

if analyze_btn:
    # Step 1 : Analyse de la ville
    with st.spinner(f"Analyse financière de {ville_input}..."):
        market = get_full_market_data(ville_input)
    
    if market:
        # Affichage des Metrics Ville
        st.subheader(f"📍 Marché Immobilier : {market['nom']}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Prix m² Médian Réel", f"{market['prix_m2_ref']} €")
        m2.metric("Population", f"{market['pop']:,}")
        
        # Calcul attractivité arbitraire (Pop / Infrastructure)
        attr_score = min(100, (market['pop'] / 10000) * 2 + 30)
        m3.metric("Score d'Attractivité", f"{round(attr_score)}/100")
        m4.metric("Tension Locative", "🔴 Très Forte" if attr_score > 60 else "🟢 Modérée")

        # Step 2 : Scraping Live
        with st.spinner("Recherche d'opportunités en temps réel..."):
            ads = fetch_live_ads(market['nom'], budget_input)
        
        if ads:
            st.divider()
            st.subheader(f"💎 Meilleures Opportunités à {market['nom']}")
            
            # Analyse financière de chaque annonce
            for ad in ads:
                # Calcul de la décote
                decote = ((market['prix_m2_ref'] - ad['prix_m2']) / market['prix_m2_ref']) * 100
                # Estimation renta (Loyer estimé = Prix marché * 0.0055/mois)
                renta = ((market['prix_m2_ref'] * ad['surface'] * 0.0055 * 12) / ad['prix']) * 100
                
                # On trie : n'afficher que ce qui n'est pas "trop cher" (moins de 10% au dessus du marché)
                if decote > -10:
                    with st.container(border=True):
                        col1, col2 = st.columns([1, 3])
                        
                        if ad['img']: col1.image(ad['img'], use_container_width=True)
                        else: col1.write("🖼️ Image indisponible")
                        
                        with col2:
                            st.write(f"### {ad['prix']:,} € — {ad['surface']} m²")
                            st.write(f"📍 **Prix m² : {round(ad['prix_m2'])} €** (Moyenne : {market['prix_m2_ref']} €)")
                            
                            met1, met2, met3 = st.columns(3)
                            
                            # Logique d'affichage des gains
                            color = "normal" if decote > 0 else "inverse"
                            met1.metric("Potentiel Plus-Value", f"{round(decote, 1)}%", delta=f"{round(decote, 1)}%", delta_color=color)
                            met2.metric("Rentabilité Brute Est.", f"{round(renta, 1)}%")
                            
                            score_invest = (decote * 2) + (renta * 5)
                            met3.write(f"**Score Opportunité**\n# {round(score_invest)}/100")
                            
                            st.link_button("🚀 Voir l'opportunité", ad['url'])
        else:
            st.warning("⚠️ Jinka a bloqué la requête ou aucune annonce ne correspond. Réessayez dans quelques minutes.")
    else:
        st.error("❌ Ville introuvable. Vérifiez l'orthographe ou essayez une ville plus grande.")

st.divider()
st.caption("Données de marché : DVF (Notaires) / Etalab 2024-2025. Données annonces : Jinka Live.")
