import numpy as np
import pandas as pd
import scipy.stats as stats
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ==========================================
# CONFIGURATION GÉNÉRALE
# ==========================================
st.set_page_config(
    page_title="Dimensionnement de Chaussée & Trafic",
    page_icon="🛣️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main { background-color: #f8f9fa; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #ffffff;
        border-radius: 8px 8px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    div.stButton > button:first-child {
        background-color: #007bff;
        color: white;
        border-radius: 6px;
        font-weight: bold;
        padding: 0.5rem 1rem;
        border: none;
    }
    div.stButton > button:first-child:hover { background-color: #0056b3; }
    @media print {
        body { background-color: white; }
        .stSidebar, .stTabs, button, header { display: none !important; }
        .printable-report { display: block !important; padding: 20px; font-size: 14px; color: black; }
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("🛣️ Analyse du Trafic & Dimensionnement des Chaussées")
st.markdown(
    "Application de collecte cloud et d'analyse statistique pour le dimensionnement "
    "structurel des chaussées (trafic, sol, épaisseurs)."
)

# ==========================================
# CONNEXION AU CLOUD (GOOGLE SHEETS)
# ==========================================
NOM_FEUILLE = "Donnees_Chaussee"  # <-- adapte au nom exact de ton Google Sheet


@st.cache_resource
def connexion_cloud():
    """
    Établit la connexion avec Google Sheets en utilisant les identifiants
    stockés dans .streamlit/secrets.toml (section [gcp_service_account]).
    Retourne None si la connexion échoue (ex: en test local sans secrets).
    """
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scopes
        )
        client = gspread.authorize(creds)
        feuille = client.open(NOM_FEUILLE).sheet1
        return feuille
    except Exception as e:
        st.sidebar.warning(
            f"⚠️ Connexion au cloud indisponible ({e}). "
            "Mode local activé : les données ne seront pas sauvegardées en ligne."
        )
        return None


feuille_cloud = connexion_cloud()


def enregistrer_mesure_cloud(ligne: dict):
    """Ajoute une ligne de données dans le Google Sheet (collecte cloud)."""
    if feuille_cloud is not None:
        feuille_cloud.append_row(list(ligne.values()))
        return True
    return False


@st.cache_data(ttl=30)
def charger_historique():
    """Récupère toutes les données déjà collectées dans le cloud."""
    if feuille_cloud is not None:
        valeurs = feuille_cloud.get_all_records()
        return pd.DataFrame(valeurs)
    return pd.DataFrame()


# ==========================================
# ONGLETS PRINCIPAUX
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📊 1. Analyse du Trafic",
        "🏗️ 2. Classification du Sol & Catalogue",
        "📐 3. Dimensionnement & Rapport d'Impression",
        "☁️ 4. Historique Cloud & Analyse Statistique",
    ]
)

# ==========================================
# ONGLET 1 : ANALYSE DU TRAFIC
# ==========================================
with tab1:
    st.header("1. Paramètres de Trafic et Évolution")

    col1, col2 = st.columns(2)
    with col1:
        pl_jour = st.number_input(
            "Trafic Poids Lourds initial (PL/jour dans les deux sens)",
            min_value=10, max_value=100000, value=450, step=50,
        )
        tc = st.number_input(
            "Taux de croissance annuel du trafic (%)",
            min_value=0.0, max_value=10.0, value=3.5, step=0.1,
        )
    with col2:
        duree = st.number_input(
            "Durée de calcul (années)", min_value=5, max_value=30, value=15, step=1
        )
        voie_sens = st.slider(
            "Pourcentage de Poids Lourds dans la voie la plus chargée (%)",
            min_value=30, max_value=100, value=50,
        )

    i = tc / 100.0
    if i > 0:
        cumul_pl = (
            pl_jour * 365 * (((1 + i) ** duree - 1) / i) * (voie_sens / 100.0) * 365
        ) / 365
    else:
        cumul_pl = pl_jour * 365 * duree * (voie_sens / 100.0)

    if cumul_pl < 5e5:
        classe_trafic = "T5 (< 0.5 million)"
    elif cumul_pl < 2e6:
        classe_trafic = "T4 (0.5 à 2 millions)"
    elif cumul_pl < 7e6:
        classe_trafic = "T3 (2 à 7 millions)"
    elif cumul_pl < 2e7:
        classe_trafic = "T2 (7 à 20 millions)"
    elif cumul_pl < 5e7:
        classe_trafic = "T1 (20 à 50 millions)"
    else:
        classe_trafic = "T0 (> 50 millions)"

    st.markdown("---")
    m1, m2 = st.columns(2)
    with m1:
        st.metric(
            label="Trafic Poids Lourds Cumulés estimé",
            value=f"{int(cumul_pl):,}".replace(",", " "),
        )
    with m2:
        st.metric(label="Classe de Trafic Normative", value=classe_trafic)

# ==========================================
# ONGLET 2 : CLASSIFICATION DU SOL
# ==========================================
with tab2:
    st.header("2. Caractéristiques et Classe de la Plate-forme (Sol)")
    st.markdown(
        "La portance de la plate-forme support de chaussée est classée de **S1** "
        "(sol faible) à **S5** (sol très bon)."
    )

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        cbr = st.slider(
            "Indice CBR (California Bearing Ratio) ou CBR estimé",
            min_value=2, max_value=30, value=8,
        )
        moyen_drainage = st.selectbox(
            "Conditions de drainage", ["Mauvais", "Moyen", "Bon", "Très bon"], index=2,
        )
    with col_s2:
        if cbr < 5:
            classe_sol = "S1 (CBR < 5 - Sol faible)"
        elif cbr < 8:
            classe_sol = "S2 (5 ≤ CBR < 8 - Sol moyen)"
        elif cbr < 15:
            classe_sol = "S3 (8 ≤ CBR < 15 - Sol bon)"
        elif cbr < 30:
            classe_sol = "S4 (15 ≤ CBR < 30 - Sol très bon)"
        else:
            classe_sol = "S5 (CBR ≥ 30 - Sol excellent)"

        st.markdown("### Résultat de la classification :")
        st.success(f"**Classe retenue :** {classe_sol}")

# ==========================================
# ONGLET 3 : DIMENSIONNEMENT & RAPPORT
# ==========================================
with tab3:
    st.header("3. Résultats du Dimensionnement & Espace d'Impression")
    st.markdown(
        "Visualisez ci-dessous les épaisseurs recommandées issues du catalogue "
        "de dimensionnement, prêtes à être imprimées, enregistrées en PDF, "
        "ou **envoyées vers le cloud** pour alimenter l'historique."
    )

    catalogue_epaisseurs = {
        "S1": {
            "T5 (< 0.5 million)": {"Roulement": 5, "Base": 15, "Fondation": 25},
            "T4 (0.5 à 2 millions)": {"Roulement": 6, "Base": 20, "Fondation": 30},
            "T3 (2 à 7 millions)": {"Roulement": 6, "Base": 25, "Fondation": 35},
            "T2 (7 à 20 millions)": {"Roulement": 8, "Base": 30, "Fondation": 40},
            "T1 (20 à 50 millions)": {"Roulement": 10, "Base": 35, "Fondation": 45},
            "T0 (> 50 millions)": {"Roulement": 12, "Base": 40, "Fondation": 50},
        },
        "S2": {
            "T5 (< 0.5 million)": {"Roulement": 5, "Base": 12, "Fondation": 20},
            "T4 (0.5 à 2 millions)": {"Roulement": 6, "Base": 15, "Fondation": 25},
            "T3 (2 à 7 millions)": {"Roulement": 6, "Base": 20, "Fondation": 30},
            "T2 (7 à 20 millions)": {"Roulement": 8, "Base": 25, "Fondation": 35},
            "T1 (20 à 50 millions)": {"Roulement": 10, "Base": 30, "Fondation": 40},
            "T0 (> 50 millions)": {"Roulement": 12, "Base": 35, "Fondation": 45},
        },
        "S3": {
            "T5 (< 0.5 million)": {"Roulement": 5, "Base": 10, "Fondation": 15},
            "T4 (0.5 à 2 millions)": {"Roulement": 5, "Base": 12, "Fondation": 20},
            "T3 (2 à 7 millions)": {"Roulement": 6, "Base": 15, "Fondation": 25},
            "T2 (7 à 20 millions)": {"Roulement": 8, "Base": 20, "Fondation": 30},
            "T1 (20 à 50 millions)": {"Roulement": 10, "Base": 25, "Fondation": 35},
            "T0 (> 50 millions)": {"Roulement": 12, "Base": 30, "Fondation": 40},
        },
        "S4": {
            "T5 (< 0.5 million)": {"Roulement": 5, "Base": 10, "Fondation": 0},
            "T4 (0.5 à 2 millions)": {"Roulement": 5, "Base": 12, "Fondation": 15},
            "T3 (2 à 7 millions)": {"Roulement": 6, "Base": 15, "Fondation": 20},
            "T2 (7 à 20 millions)": {"Roulement": 8, "Base": 18, "Fondation": 25},
            "T1 (20 à 50 millions)": {"Roulement": 10, "Base": 22, "Fondation": 30},
            "T0 (> 50 millions)": {"Roulement": 12, "Base": 25, "Fondation": 35},
        },
        "S5": {
            "T5 (< 0.5 million)": {"Roulement": 4, "Base": 8, "Fondation": 0},
            "T4 (0.5 à 2 millions)": {"Roulement": 5, "Base": 10, "Fondation": 12},
            "T3 (2 à 7 millions)": {"Roulement": 6, "Base": 12, "Fondation": 18},
            "T2 (7 à 20 millions)": {"Roulement": 8, "Base": 15, "Fondation": 22},
            "T1 (20 à 50 millions)": {"Roulement": 10, "Base": 20, "Fondation": 28},
            "T0 (> 50 millions)": {"Roulement": 12, "Base": 22, "Fondation": 32},
        },
    }

    sol_cle = classe_sol.split(" ")[0]
    resultats_epaisseurs = catalogue_epaisseurs[sol_cle][classe_trafic]

    st.info(
        f"📍 **Combinaison retenue :** Sol **{sol_cle}** associé au Trafic **{classe_trafic}**"
    )

    col_res1, col_res2, col_res3, col_res4 = st.columns(4)
    with col_res1:
        st.metric(label="Couche de Roulement", value=f"{resultats_epaisseurs['Roulement']} cm")
    with col_res2:
        st.metric(label="Couche de Base", value=f"{resultats_epaisseurs['Base']} cm")
    with col_res3:
        st.metric(label="Couche de Fondation", value=f"{resultats_epaisseurs['Fondation']} cm")
    with col_res4:
        epaisseur_totale = (
            resultats_epaisseurs["Roulement"]
            + resultats_epaisseurs["Base"]
            + resultats_epaisseurs["Fondation"]
        )
        st.metric(label="Épaisseur Totale", value=f"{epaisseur_totale} cm")

    st.markdown("---")
    st.subheader("📄 Aperçu du Rapport Synthétique")

    st.markdown(
        f"""
    <div style="border: 2px solid #007bff; padding: 20px; border-radius: 10px; background-color: white;">
        <h3 style="text-align: center; color: #007bff;">RAPPORT DE SYNTHÈSE - DIMENSIONNEMENT DE CHAUSSÉE</h3>
        <hr>
        <p><b>1. Données de Trafic :</b></p>
        <ul>
            <li>Trafic Poids Lourds Initial : <b>{pl_jour} PL/jour</b></li>
            <li>Taux de croissance : <b>{tc} % / an</b></li>
            <li>Durée de calcul : <b>{duree} ans</b></li>
            <li>Trafic cumulé calculé : <b>{int(cumul_pl):,} PL</b></li>
            <li>Classe de trafic normative : <b>{classe_trafic}</b></li>
        </ul>
        <p><b>2. Caractéristiques du Sol :</b></p>
        <ul>
            <li>Indice CBR : <b>{cbr}</b></li>
            <li>Classe de sol de plate-forme : <b>{classe_sol}</b></li>
        </ul>
        <p><b>3. Structure de Chaussée Recommandée :</b></p>
        <ul>
            <li>Épaisseur Couche de Roulement : <b>{resultats_epaisseurs['Roulement']} cm</b></li>
            <li>Épaisseur Couche de Base : <b>{resultats_epaisseurs['Base']} cm</b></li>
            <li>Épaisseur Couche de Fondation : <b>{resultats_epaisseurs['Fondation']} cm</b></li>
            <li><b>Épaisseur Totale de la Structure : {epaisseur_totale} cm</b></li>
        </ul>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            """
            <div style="text-align: center;">
                <button onclick="window.print()" style="background-color: #28a745; color: white; padding: 12px 24px; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer;">
                    🖨️ Imprimer / Enregistrer en PDF
                </button>
            </div>
        """,
            unsafe_allow_html=True,
        )
    with col_b:
        # BOUTON D'ENVOI VERS LE CLOUD : c'est ici que la "collecte en ligne" se produit
        if st.button("☁️ Envoyer cette mesure vers le cloud", use_container_width=True):
            ligne = {
                "Horodatage": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "PL_jour": pl_jour,
                "Taux_croissance_%": tc,
                "Duree_annees": duree,
                "Pct_voie_chargee": voie_sens,
                "Trafic_cumule": int(cumul_pl),
                "Classe_trafic": classe_trafic,
                "CBR": cbr,
                "Drainage": moyen_drainage,
                "Classe_sol": classe_sol,
                "Epaisseur_Roulement_cm": resultats_epaisseurs["Roulement"],
                "Epaisseur_Base_cm": resultats_epaisseurs["Base"],
                "Epaisseur_Fondation_cm": resultats_epaisseurs["Fondation"],
                "Epaisseur_Totale_cm": epaisseur_totale,
            }
            if enregistrer_mesure_cloud(ligne):
                st.success("✅ Mesure enregistrée dans le cloud (Google Sheets) !")
                st.cache_data.clear()  # force le rechargement de l'historique
            else:
                st.error(
                    "❌ Connexion cloud non configurée. Vérifie ton fichier "
                    ".streamlit/secrets.toml."
                )

# ==========================================
# ONGLET 4 : HISTORIQUE CLOUD & ANALYSE STATISTIQUE
# ==========================================
with tab4:
    st.header("4. Historique des Données Collectées (Cloud) & Analyse Statistique")

    df = charger_historique()

    if df.empty:
        st.warning(
            "Aucune donnée collectée pour le moment. Va dans l'onglet 3 et clique sur "
            "« Envoyer cette mesure vers le cloud » pour commencer à construire ton historique."
        )
    else:
        st.subheader("📋 Données brutes collectées")
        st.dataframe(df, use_container_width=True)

        st.markdown("---")
        st.subheader("📈 Statistique descriptive")

        colonne_analysee = st.selectbox(
            "Choisir la variable à analyser statistiquement",
            ["Trafic_cumule", "CBR", "Epaisseur_Totale_cm"],
        )

        serie = pd.to_numeric(df[colonne_analysee], errors="coerce").dropna()

        if len(serie) >= 2:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Moyenne", f"{serie.mean():.2f}")
            c2.metric("Écart-type", f"{serie.std():.2f}")
            c3.metric("Minimum", f"{serie.min():.2f}")
            c4.metric("Maximum", f"{serie.max():.2f}")

            st.markdown("#### Histogramme de distribution")
            st.bar_chart(serie.value_counts(bins=10).sort_index())

            st.markdown("---")
            st.subheader("🧪 Test d'hypothèse (test t à un échantillon)")
            st.markdown(
                "Teste si la moyenne observée diffère significativement d'une "
                "valeur de référence (ex: valeur de conception attendue)."
            )
            valeur_ref = st.number_input(
                f"Valeur de référence pour « {colonne_analysee} »",
                value=float(serie.mean()),
            )
            if st.button("Lancer le test t"):
                t_stat, p_value = stats.ttest_1samp(serie, valeur_ref)
                st.write(f"**Statistique t :** {t_stat:.4f}")
                st.write(f"**p-value :** {p_value:.4f}")
                if p_value < 0.05:
                    st.error(
                        "➡️ La moyenne observée diffère significativement de la "
                        "valeur de référence (p < 0.05)."
                    )
                else:
                    st.success(
                        "➡️ Pas de différence significative avec la valeur de "
                        "référence (p ≥ 0.05)."
                    )
        else:
            st.info("Il faut au moins 2 mesures collectées pour calculer des statistiques.")
