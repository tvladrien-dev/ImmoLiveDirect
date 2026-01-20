import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="InvestImmo Alpha Bot v3",
    page_icon="🏘️",
    layout="wide"
)

# --- MOTEUR DE DONNÉES GOUVERNEMENTALES ---

@st.cache_data(ttl=86400)
def get_city_data(nom_ville):
    """Récupère les infos géo, population et codes INSEE"""
    try:
        url = f"https://geo.api.gouv.fr/communes?nom={nom_ville}&fields=code,population,codesPostaux,centre,surface,departement&boost=population"
        res = requests.get(url, timeout=10).json()
        return res[0] if res else None
    except:
        return None

@st.cache_data(ttl=604800)
def get_dvf_market_stats(code_insee):
    """Récupère les prix de vente réels (Notaires) via API DVF"""
    try:
        # On interroge les mutations des 2 dernières années
        url = f"https://dvf-api.data.gouv.fr/api/v1/mutations/?code_commune={code_insee}"
        res = requests.get(url, timeout=15).json()
        
        if not res.get('results'):
            return None
            
        data = []
        for item in res['results']:
            prix = item.get('valeur_fonciere')
            surf = item.get('surface_reelle_bati')
            if prix and surf and surf > 0:
                data.append({
                    "date": item['date_mutation'],
                    "prix_m2": float(prix) / float(surf),
                    "type": item['type_local'],
                    "pieces": item['nombre_pieces_principales']
                })
        
        df = pd.DataFrame(data)
        # Nettoyage des outliers (écarts extrêmes)
        low = df['prix_m2'].quantile(0.10)
        high = df['prix_m2'].quantile(0.90)
        df_clean = df[(df['prix_m2'] >= low) & (df['prix_m2'] <= high)]
        
        return {
            "prix_median": df_clean['prix_m2'].median(),
            "historique": df_clean,
            "count": len(df_clean)
        }
    except:
        return None

# --- ANALYSE DES INFRASTRUCTURES (OpenStreetMap) ---

@st.cache_data(ttl=86400)
def get_proximity_score(lat, lon):
    """Analyse la présence d'infrastructures clés via Overpass API (OSM)"""
    query = f"""
    [out:json];
    (
      node["amenity"~"school|university|hospital"](around:1500,{lat},{lon});
      node["public_transport"~"stop_position|station"](around:1000,{lat},{lon});
      node["shop"~"supermarket|mall"](around:1000,{lat},{lon});
    );
    out count;
    """
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        response = requests.post(overpass_url, data={'data': query}, timeout=10).json()
        return response.get('elements', [{}])[0].get('tags', {}).get('nodes', 0)
    except:
        return 0

# --- LOGIQUE D'ORIENTATION INVESTISSEUR ---

def analyze_opportunity(prix_m2_annonce, stats_marche, surface):
    prix_ref = stats_marche['prix_median']
    
    # 1. Calcul de la Décote (Potentiel de gain à l'achat)
    decote = ((prix_ref - prix_m2_annonce) / prix_ref) * 100
    
    # 2. Estimation Potentiel Locatif (Basé sur le rendement moyen FR ~0.55%/mois)
    # Loyer estimé = Prix Marché * Surface * 0.0055
    loyer_mensuel = (prix_ref * surface * 0.0055)
    renta_brute = ((loyer_mensuel * 12) / (prix_m2_annonce * surface)) * 100
    
    return round(decote, 1), round(renta_brute, 2)

# --- INTERFACE UTILISATEUR (STREAMLIT) ---

st.title("🚀 InvestImmo Alpha Master")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Paramètres")
    ville_input = st.text_input("Ville cible", "Lille")
    budget_input = st.number_input("Votre budget (€)", value=200000, step=5000)
    surface_visée = st.slider("Surface recherchée (m²)", 15, 120, 45)
    
    st.divider()
    st.info("Ce bot compare les annonces potentielles avec les prix RÉELS des notaires (DVF).")

# LANCEMENT DE L'ANALYSE
if ville_input:
    with st.spinner("Analyse du marché en cours..."):
        city = get_city_data(ville_input)
        
        if city:
            stats = get_dvf_market_stats(city['code'])
            
            if stats:
                # --- HEADER METRICS ---
                st.subheader(f"📍 Rapport de Marché : {city['nom']} ({city['departement']['nom']})")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Prix m² Médian", f"{round(stats['prix_median'])} €")
                c2.metric("Transactions (2 ans)", stats['count'])
                c3.metric("Population", f"{city['population']:,}")
                
                # Calcul attractivité
                infra_count = get_proximity_score(city['centre']['coordinates'][1], city['centre']['coordinates'][0])
                score_attract = min(100, (infra_count * 2) + (city['population'] / 5000))
                c4.metric("Score Attractivité", f"{round(score_attract)}/100")

                # --- GRAPHIQUE HISTORIQUE ---
                st.write("### 📈 Évolution des prix réels de vente")
                fig = px.line(stats['historique'].sort_values('date'), x='date', y='prix_m2', 
                             title="Prix au m² constaté lors des dernières ventes notariées")
                st.plotly_chart(fig, use_container_width=True)

                # --- DÉTECTEUR D'OPPORTUNITÉS ---
                st.divider()
                st.header("🎯 Cibles d'Investissement")
                
                # Simulation de 3 scénarios pour orienter l'utilisateur
                scenarios = [
                    {"label": "Opportunité 'Bon Père de Famille'", "decote": 5, "desc": "Prix proche du marché, risque faible."},
                    {"label": "Excellente Affaire", "decote": 15, "desc": "Bien sous-évalué, forte plus-value possible."},
                    {"label": "Pépite / Travaux", "decote": 25, "desc": "Décote massive, idéal achat-revente ou déficit foncier."}
                ]
                
                for sc in scenarios:
                    prix_cible_m2 = stats['prix_median'] * (1 - sc['decote']/100)
                    total_achat = prix_cible_m2 * surface_visée
                    decote, renta = analyze_opportunity(prix_cible_m2, stats, surface_visée)
                    
                    if total_achat <= budget_input:
                        with st.container(border=True):
                            col_txt, col_met = st.columns([2, 1])
                            col_txt.write(f"### {sc['label']}")
                            col_txt.write(f"{sc['desc']}")
                            col_txt.write(f"**Prix d'achat cible : {round(total_achat):,} €** ({round(prix_cible_m2)} €/m²)")
                            
                            col_met.metric("Rentabilité visée", f"{renta}%")
                            col_met.metric("Décote vs Marché", f"-{sc['decote']}%")
                
                # --- ANALYSE DE PRIX (ESTIMATION) ---
                st.divider()
                st.subheader("⚖️ Estimer une annonce que vous avez trouvée")
                p_annonce = st.number_input("Prix affiché de l'annonce (€)", value=150000)
                s_annonce = st.number_input("Surface de l'annonce (m²)", value=40)
                
                if p_annonce and s_annonce:
                    p_m2_an = p_annonce / s_annonce
                    diff = ((p_m2_an - stats['prix_median']) / stats['prix_median']) * 100
                    
                    if diff > 10:
                        st.error(f"🔴 Trop cher ! Ce bien est {round(diff)}% au-dessus du prix du marché local.")
                    elif diff < -10:
                        st.success(f"🟢 Excellente opportunité ! Ce bien est {round(abs(diff))}% en-dessous du marché.")
                    else:
                        st.warning(f"🟡 Prix correct. Le bien est dans la moyenne du secteur ({round(diff)}%).")

            else:
                st.error("Données DVF (notaires) indisponibles pour cette zone.")
        else:
            st.error("Ville non trouvée. Vérifiez l'orthographe.")

st.markdown("---")
st.caption("Données sources : Etalab (DVF), API Géo Gouv, OpenStreetMap.")
