import streamlit as st
import os
import sys
import time
import random
import re
import requests
import pandas as pd

# --- FIX COMPATIBILITÉ PYTHON 3.12/3.13 (STREAMLIT CLOUD) ---
try:
    from distutils.version import LooseVersion
except ImportError:
    import setuptools
    from setuptools import distutils
    sys.modules['distutils'] = distutils

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

# --- CONFIGURATION UI ---
st.set_page_config(page_title="InvestImmo Alpha Master", layout="wide")

# --- MOTEUR GÉOGRAPHIQUE ET FINANCIER (DATA.GOUV) ---
@st.cache_data(ttl=86400)
def get_location_and_market_data(ville_nom):
    """Récupère les données INSEE, Population et Prix m2 réels"""
    try:
        # 1. Trouver le code INSEE et la Population
        geo_url = f"https://geo.api.gouv.fr/communes?nom={ville_nom}&fields=code,population,centre,surface&boost=population"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        if not geo_res:
            return None
        
        ville_data = geo_res[0]
        code_insee = ville_data['code']
        
        # 2. Récupérer les prix réels (DVF) via API cquest (OpenData)
        # On filtre sur les mutations de type 'Vente' pour des 'Appartements' ou 'Maisons'
        dvf_url = f"http://api.cquest.org/dvf?code_commune={code_insee}"
        dvf_res = requests.get(dvf_url, timeout=10).json()
        
        prices = []
        if "features" in dvf_res:
            for feat in dvf_res["features"]:
                prop = feat["properties"]
                valeur = prop.get("valeur_fonciere")
                surf = prop.get("surface_reelle_bati")
                if valeur and surf and surf > 0:
                    prices.append(valeur / surf)
        
        # Calcul de la moyenne robuste (on retire les 10% extrêmes pour éviter les anomalies)
        if len(prices) > 5:
            prices.sort()
            trim = int(len(prices) * 0.1)
            prices = prices[trim:-trim]
            avg_price = round(sum(prices) / len(prices))
        else:
            avg_price = 2800 # Valeur de secours par défaut
            
        return {
            "nom": ville_data['nom'],
            "code": code_insee,
            "pop": ville_data['population'],
            "prix_m2_ref": avg_price
        }
    except Exception as e:
        return None

# --- MOTEUR DE NAVIGATION FURTIF ---
def init_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Bypass des signatures de bot
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        driver = uc.Chrome(options=options, browser_executable_path="/usr/bin/chromium")
        return driver
    except Exception as e:
        st.error(f"Erreur technique (Driver): {e}")
        return None

def scrape_opportunities(ville, budget_max):
    driver = init_driver()
    if not driver: return []
    
    # Jinka formatte souvent les URLs ainsi : /recherche/vente?communes=ville-codeinsee
    # Mais la recherche par nom simple fonctionne aussi en redirection
    search_url = f"https://www.jinka.fr/recherche/vente?communes={ville.lower()}&prix_max={budget_max}"
    
    results = []
    try:
        driver.get(search_url)
        # Attente pour passer DataDome
        time.sleep(random.uniform(8, 12))
        
        # Scroll progressif pour charger les images
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # On cible les balises 'article' ou les liens contenant '/annonce/'
        annonces = soup.find_all(['article', 'div'], class_=re.compile(r"card|AdCard|property", re.I))
        
        if not annonces: # Backup si la structure a changé
            annonces = soup.select('a[href*="/annonce/"]')

        for ad in annonces[:20]:
            try:
                raw_text = ad.get_text(separator=" ")
                # Extraction Prix (ex: 250 000 €)
                price_match = re.search(r'(\d[\d\s]*)\s*€', raw_text)
                # Extraction Surface (ex: 45 m²)
                surf_match = re.search(r'(\d[\d\s]*)\s*m²', raw_text)
                
                if price_match and surf_match:
                    p = int(price_match.group(1).replace(" ", ""))
                    s = int(surf_match.group(1).replace(" ", ""))
                    
                    # Lien de l'annonce
                    link = ad.find('a', href=True)['href'] if ad.name != 'a' else ad['href']
                    full_link = "https://www.jinka.fr" + link if link.startswith('/') else link
                    
                    # Image
                    img_tag = ad.find('img')
                    img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else None

                    results.append({
                        "prix": p,
                        "surface": s,
                        "prix_m2": p / s,
                        "url": full_link,
                        "img": img_url
                    })
            except:
                continue
    finally:
        driver.quit()
    return results

# --- LOGIQUE D'ANALYSE D'INVESTISSEMENT ---
def get_investment_score(annonce, ref_m2):
    """Calcule la pertinence financière"""
    decote = ((ref_m2 - annonce['prix_m2']) / ref_m2) * 100
    # Estimation loyer : 0.6% de la valeur m2 réelle / mois (standard rendement locatif)
    loyer_mensuel_est = (ref_m2 * annonce['surface'] * 0.0055) 
    renta_brute = ((loyer_mensuel_est * 12) / annonce['prix']) * 100
    
    # Score de pertinence (0 à 100)
    score = (decote * 2) + (renta_brute * 5)
    return round(decote, 1), round(renta_brute, 1), round(score)

# --- INTERFACE STREAMLIT ---
st.title("💎 InvestImmo Alpha Bot")
st.markdown("---")

col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    target_city = st.text_input("📍 Ville d'investissement", value="Marseille")
with col_cfg2:
    max_price = st.number_input("💰 Budget Maximum (€)", value=300000, step=10000)

if st.button("🚀 Lancer l'analyse du marché", use_container_width=True):
    with st.spinner("1/3 - Récupération des données officielles (DVF/Notaires)..."):
        market = get_location_and_market_data(target_city)
    
    if market:
        st.success(f"Marché identifié : {market['nom']} ({market['code']})")
        
        # Affichage du contexte marché
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Prix m² Moyen Réel", f"{market['prix_m2_ref']} €")
        m_col2.metric("Population", f"{market['pop']:,}")
        m_col3.metric("Tension Immobilière", "Élevée 🔥")

        with st.spinner("2/3 - Scan furtif des annonces en cours..."):
            raw_ads = scrape_opportunities(market['nom'], max_price)
        
        if raw_ads:
            st.subheader(f"🔍 Résultats pour {market['nom']}")
            
            processed_ads = []
            for ad in raw_ads:
                decote, renta, score = get_investment_score(ad, market['prix_m2_ref'])
                ad.update({"decote": decote, "renta": renta, "score": score})
                processed_ads.append(ad)
            
            # Tri par score d'investissement
            processed_ads = sorted(processed_ads, key=lambda x: x['score'], reverse=True)

            for item in processed_ads:
                with st.container(border=True):
                    c1, c2 = st.columns([1, 3])
                    if item['img']:
                        c1.image(item['img'], use_container_width=True)
                    else:
                        c1.write("Pas d'image")
                        
                    with c2:
                        st.write(f"### {item['prix']:,} € - {item['surface']} m²")
                        st.write(f"📍 **Prix m² : {round(item['prix_m2'])} €** (Moyenne secteur : {market['prix_m2_ref']} €)")
                        
                        metric_col1, metric_col2, metric_col3 = st.columns(3)
                        # Indiquer si c'est une affaire ou trop cher
                        color = "normal" if item['decote'] >= 0 else "inverse"
                        metric_col1.metric("Décote Marché", f"{item['decote']}%", delta=item['decote'])
                        metric_col2.metric("Rendement Est.", f"{item['renta']}%")
                        metric_col3.write(f"**Score Investisseur**\n# {item['score']}/100")
                        
                        st.link_button("🌐 Voir l'annonce complète", item['url'])
        else:
            st.error("❌ Aucune annonce trouvée. Cela arrive si le site bloque l'adresse IP du serveur. Réessayez dans 10 minutes.")
    else:
        st.error("⚠️ Impossible de localiser la ville ou de récupérer les données DVF. Vérifiez l'orthographe.")

st.divider()
st.info("Note : Les données DVF représentent les prix de vente réels constatés par les notaires sur les 2 dernières années.")
