"""Application pédagogique d'étude préliminaire des chaussées.

IMPORTANT : les classes et épaisseurs du catalogue sont des hypothèses de démonstration,
non des prescriptions normatives. Remplacer le catalogue par les tableaux d'un guide
technique validé avant tout usage professionnel ou tout projet réel.
"""
from __future__ import annotations

from datetime import datetime
import io
import math
import html
import hashlib

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import requests

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None
    Credentials = None

st.set_page_config(page_title="SHM | Étude de chaussée", page_icon="🛣️", layout="wide")

st.markdown("""
<style>
:root { --navy:#17365D; --blue:#2F75B5; --sky:#DCEAF7; --pale:#F4F8FC; --gold:#D6A84F; }
.stApp { background:#F7FAFD; color:#243447; }
.block-container {padding-top:1.35rem; padding-bottom:3rem; max-width:1400px;}
section[data-testid="stSidebar"] {background:#EAF2FA; border-right:1px solid #D4E1EF;}
section[data-testid="stSidebar"] * {color:#17365D;}
section[data-testid="stSidebar"] label {font-weight:600;}
.hero {padding:1.35rem 1.6rem; border-radius:15px; background:linear-gradient(110deg,#17365D,#2F75B5); color:white; margin-bottom:1rem; box-shadow:0 5px 18px rgba(23,54,93,.12);}
.hero h1 {color:white; margin-bottom:.25rem; font-size:1.8rem;}
.notice {padding:.9rem 1rem; border-left:5px solid #D6A84F; background:#FFF8E8; border-radius:7px; color:#493B21;}
[data-testid="stMetric"] {background:white; border:1px solid #DFE8F1; padding:12px 14px; border-radius:12px; box-shadow:0 2px 7px rgba(23,54,93,.04);}
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] {color:#17365D !important;}
.stButton>button, .stDownloadButton>button {border-radius:8px; font-weight:600; color:#17365D !important;}
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {color:white !important;}
label, .stMarkdown, .stCaption, p, span {color:#243447;}
input, textarea, .stSelectbox div, .stNumberInput input {color:#17365D !important;}
.stTextInput input, .stNumberInput input {background:#FFFFFF !important; border:1px solid #B7C5D3 !important;}
.stTextInput input::placeholder {color:#8CA0B3 !important;}
.stTabs [data-baseweb="tab-list"] {gap:6px;}
.stTabs [data-baseweb="tab"] {color:#17365D !important; font-weight:600; background:#EAF2FA; border-radius:8px 8px 0 0; padding:8px 16px;}
.stTabs [aria-selected="true"] {background:#2F75B5 !important; color:#FFFFFF !important;}
 .small-muted {color:#64748B; font-size:.9rem;}
.welcome-hero {padding:2rem 2.2rem; border-radius:18px; background:linear-gradient(120deg,#102A43 0%,#174A72 100%); border-bottom:5px solid #D6A84F; margin:1.2rem 0 2rem; box-shadow:0 10px 26px rgba(16,42,67,.13);}
.welcome-hero .welcome-kicker {color:#F4D58D !important; font-size:.78rem; font-weight:800; letter-spacing:3px; margin-bottom:.8rem;}
.welcome-hero h1, .welcome-hero h1 * {color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; font-size:2.25rem; line-height:1.2; margin:0 0 .8rem 0; text-shadow:0 1px 2px rgba(0,0,0,.18) !important; opacity:1 !important;}
.welcome-hero p {color:#F4F8FC !important; font-size:1.03rem; line-height:1.7; max-width:850px; margin:0;}
.welcome-card {background:#FFFFFF; border:1px solid #D8E3EE; border-top:4px solid #2F75B5; border-radius:16px; padding:1.35rem 1.45rem 1.1rem; box-shadow:0 8px 24px rgba(23,54,93,.08);}
.welcome-card h3 {color:#17365D !important; margin-top:.2rem;}
.welcome-card p, .welcome-card label {color:#334155 !important;}
.welcome-card [data-testid="stForm"] {border:0; padding:0;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Catalogue de démonstration : à remplacer par un référentiel technique validé.
# Les épaisseurs ne sont volontairement PAS qualifiées de « normatives ».
# -----------------------------------------------------------------------------
TRAFFIC_CLASSES = [
    (5e5, "T5"), (2e6, "T4"), (7e6, "T3"), (2e7, "T2"), (5e7, "T1"), (float("inf"), "T0")
]
SOIL_CLASSES = [(5, "S1"), (8, "S2"), (15, "S3"), (30, "S4"), (float("inf"), "S5")]

# Épaisseurs d'exemple en cm. Ce jeu de données est illustratif et doit être validé.
CATALOGUE = {
    "S1": {"T5": (5, 15, 25), "T4": (6, 20, 30), "T3": (6, 25, 35), "T2": (8, 30, 40), "T1": (10, 35, 45), "T0": (12, 40, 50)},
    "S2": {"T5": (5, 12, 20), "T4": (6, 15, 25), "T3": (6, 20, 30), "T2": (8, 25, 35), "T1": (10, 30, 40), "T0": (12, 35, 45)},
    "S3": {"T5": (5, 10, 15), "T4": (5, 12, 20), "T3": (6, 15, 25), "T2": (8, 20, 30), "T1": (10, 25, 35), "T0": (12, 30, 40)},
    "S4": {"T5": (5, 10, 0), "T4": (5, 12, 15), "T3": (6, 15, 20), "T2": (8, 18, 25), "T1": (10, 22, 30), "T0": (12, 25, 35)},
    "S5": {"T5": (4, 8, 0), "T4": (5, 10, 12), "T3": (6, 12, 18), "T2": (8, 15, 22), "T1": (10, 20, 28), "T0": (12, 22, 32)},
}

MATERIALS = {
    "Roulement": ["Béton bitumineux (BB)", "Enduit superficiel bicouche", "Autre / à préciser"],
    "Base": ["Grave-bitume (GB)", "Grave non traitée (GNT)", "Grave-ciment (GC)", "Matériau local traité", "Autre / à préciser"],
    "Fondation": ["Grave non traitée (GNT)", "Latérite (caractéristiques à vérifier)", "Tout-venant concassé", "Autre / à préciser"],
}


def classer_trafic(n: float) -> str:
    for seuil, classe in TRAFFIC_CLASSES:
        if n < seuil:
            return classe
    return "T0"


def classer_sol(cbr: float) -> str:
    for seuil, classe in SOIL_CLASSES:
        if cbr < seuil:
            return classe
    return "S5"


def trafic_cumule(pl_jour_deux_sens: float, croissance_pct: float, annees: int, part_voie_pct: float) -> float:
    """Nombre cumulé de PL sur la voie considérée, sous hypothèse de croissance annuelle constante.

    Hypothèses : trafic initial quotidien dans les deux sens; part de la voie appliquée
    au trafic; 365 jours/an. Ne remplace pas un calcul en essieux équivalents lorsqu'il
    est exigé par le guide de dimensionnement retenu.
    """
    i = croissance_pct / 100.0
    trafic_voie = pl_jour_deux_sens * part_voie_pct / 100.0
    if annees <= 0:
        return 0.0
    facteur = annees if math.isclose(i, 0.0, abs_tol=1e-12) else ((1 + i) ** annees - 1) / i
    return trafic_voie * 365.0 * facteur


def format_nombre(x: float, decimales: int = 0) -> str:
    return f"{x:,.{decimales}f}".replace(",", " ")


def generer_coupe(epaisseurs: dict[str, float], materiaux: dict[str, str]) -> go.Figure:
    """Dessine une coupe lisible sur fond clair, avec des couches bien distinctes."""
    palette = {
        "Roulement": {"color": "#343A40", "text": "#FFFFFF"},
        "Base": {"color": "#D6A84F", "text": "#263445"},
        "Fondation": {"color": "#8FB8D8", "text": "#17365D"},
    }
    fig = go.Figure()
    y = 0.0
    total = sum(max(0.0, float(epaisseurs.get(c, 0))) for c in ["Roulement", "Base", "Fondation"])
    for couche in ["Roulement", "Base", "Fondation"]:
        e = max(0.0, float(epaisseurs.get(couche, 0)))
        if e <= 0:
            continue
        color = palette[couche]["color"]
        fig.add_shape(type="rect", x0=1.2, x1=8.8, y0=y, y1=y + e,
                      line=dict(color="#FFFFFF", width=2), fillcolor=color, layer="above")
        label = f"{couche} — {e:g} cm\n{materiaux.get(couche, '')}"
        fig.add_annotation(x=5, y=y + e / 2, text=label.replace("&", "&amp;"),
                           showarrow=False, align="center", font=dict(color=palette[couche]["text"], size=12),
                           bgcolor="rgba(255,255,255,0.0)")
        y += e
    # Sol support visuellement distinct, dessiné même si la structure est vide.
    sol_h = max(8.0, total * 0.30)
    fig.add_shape(type="rect", x0=1.2, x1=8.8, y0=y, y1=y + sol_h,
                  line=dict(color="#B7C5D3", width=1.5), fillcolor="#E5EAF0", layer="above")
    fig.add_annotation(x=5, y=y + sol_h / 2, text="SOL SUPPORT / PLATE-FORME",
                       showarrow=False, font=dict(color="#34495E", size=12))
    fig.update_layout(
        height=480,
        title=dict(text="Coupe schématique de la chaussée", x=0.02, xanchor="left", font=dict(color="#17365D", size=18)),
        xaxis=dict(visible=False, range=[0, 10], fixedrange=True),
        yaxis=dict(visible=False, range=[y + sol_h + 2, -2], fixedrange=True),
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=18, r=18, t=55, b=18), showlegend=False,
        annotations=list(fig.layout.annotations) + [dict(x=5, y=y + sol_h + 1.2, text="Représentation schématique — épaisseurs non à l’échelle", showarrow=False, font=dict(size=10, color="#64748B"))]
    )
    return fig


def creer_pdf_metre(titre: str, projet: str, report: dict, df_metre: pd.DataFrame, marque: str = "SHM", auteur: str = "", logo_bytes: bytes | None = None) -> bytes:
    """Génère un rapport PDF propre et paginé, avec tableau de métré."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=1.7*cm, leftMargin=1.7*cm,
                            topMargin=1.6*cm, bottomMargin=1.6*cm, title=titre, author="SHM Road")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                              fontSize=19, leading=23, textColor=colors.HexColor("#16324f"), alignment=TA_LEFT, spaceAfter=5))
    styles.add(ParagraphStyle(name="SectionBlue", parent=styles["Heading2"], fontSize=12, leading=15,
                              textColor=colors.HexColor("#2364aa"), spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="SmallNote", parent=styles["BodyText"], fontSize=8, leading=10,
                              textColor=colors.HexColor("#555555")))
    brand_line = f"{html.escape(marque)} ROAD" if marque.strip() else "Rapport technique"
    story = []
    if logo_bytes:
        try:
            logo_img = Image(io.BytesIO(logo_bytes), width=2.2*cm, height=2.2*cm, kind="proportional")
            logo_img.hAlign = "LEFT"
            story.extend([logo_img, Spacer(1, 4)])
        except Exception:
            pass
    story += [Paragraph(brand_line, styles["Heading2"]), Paragraph(titre, styles["ReportTitle"]),
             Paragraph(f"Projet : {html.escape(projet)} &nbsp;&nbsp; | &nbsp;&nbsp; Généré le : {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["BodyText"]),
             Spacer(1, 10), Paragraph("1. Synthèse du projet", styles["SectionBlue"])]
    summary_rows = [["Indicateur", "Valeur"],
        ["Trafic initial", f"{format_nombre(float(report['Trafic initial (PL/jour, deux sens)']))} PL/jour (deux sens)"],
        ["Croissance annuelle", f"{report['Croissance annuelle (%)']} %"],
        ["Durée de calcul", f"{report['Durée (années)']} ans"],
        ["Trafic cumulé estimé", f"{format_nombre(float(report['Trafic cumulé estimé (PL)']))} PL"],
        ["Classe de trafic", str(report['Classe trafic indicative']) + " (indicative)"],
        ["CBR du sol", f"{report['CBR (%)']} %"],
        ["Classe de sol", str(report['Classe sol indicative']) + " (indicative)"],
        ["Dimensions du tronçon", f"{report['Longueur (m)']} m × {report['Largeur (m)']} m"],
        ["Épaisseur totale", f"{report['Épaisseur totale indicative (cm)']} cm"]]
    t = Table(summary_rows, colWidths=[6.1*cm, 10.5*cm], repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#16324f")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cbd5df")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f2f6fa")]),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [t, Spacer(1, 8), Paragraph("2. Métré géométrique préliminaire", styles["SectionBlue"])]
    if auteur.strip():
        story.append(Paragraph(f"Préparé par : {html.escape(auteur.strip())}", styles["BodyText"]))
    metre_rows = [["Couche", "Matériau", "Épaisseur (cm)", "Volume (m³)"]]
    for _, row in df_metre.iterrows():
        metre_rows.append([str(row["Couche"]), str(row["Matériau"]), f"{float(row['Épaisseur (cm)']):g}", f"{float(row['Volume géométrique (m³)']):,.2f}".replace(",", " ")])
    metre_rows.append(["TOTAL", "", "", f"{float(df_metre['Volume géométrique (m³)'].sum()):,.2f}".replace(",", " ")])
    mt = Table(metre_rows, colWidths=[3.2*cm, 6.0*cm, 3.0*cm, 4.4*cm], repeatRows=1, hAlign="LEFT")
    mt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2364aa")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#e7eef5")),("FONTSIZE",(0,0),(-1,-1),8),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cbd5df")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story += [mt, Spacer(1, 12), Paragraph("3. Hypothèses et limites", styles["SectionBlue"]),
              Paragraph("Les volumes sont des volumes géométriques théoriques calculés à partir de la longueur, de la largeur et des épaisseurs indiquées. Ils ne prennent pas en compte les pertes, le compactage, le foisonnement, les pentes, les accotements ni les corrections de chantier.", styles["BodyText"]),
              Spacer(1, 6), Paragraph("AVERTISSEMENT TECHNIQUE : les classes et épaisseurs proposées par ce prototype sont indicatives et non normatives. Le rapport ne remplace pas une étude géotechnique, le choix d'un guide de dimensionnement reconnu ni la validation par un ingénieur compétent avant tout projet réel.", styles["SmallNote"])]
    def footer(canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#cbd5df")); canvas.line(1.7*cm, 1.25*cm, A4[0]-1.7*cm, 1.25*cm)
        canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#65758b"))
        canvas.drawString(1.7*cm, 0.85*cm, f"{marque} Road · Rapport préliminaire")
        canvas.drawRightString(A4[0]-1.7*cm, 0.85*cm, f"Page {doc.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def creer_word_metre(titre: str, projet: str, report: dict, df_metre: pd.DataFrame, marque: str = "SHM", auteur: str = "", logo_bytes: bytes | None = None) -> bytes:
    """Génère un document Word structuré avec synthèse et tableau de métré."""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.65); section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75); section.right_margin = Inches(0.75)
    normal = doc.styles["Normal"]; normal.font.name = "Aptos"; normal.font.size = Pt(9)
    normal.font.color.rgb = RGBColor(45, 55, 65)
    if logo_bytes:
        try:
            p_logo = doc.add_paragraph(); p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_logo.add_run().add_picture(io.BytesIO(logo_bytes), width=Inches(1.0))
        except Exception:
            pass
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{marque.strip() or 'Rapport technique'} ROAD"); r.bold = True; r.font.size = Pt(12); r.font.color.rgb = RGBColor(35,100,170)
    h = doc.add_heading(titre, 0); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f"Projet : {projet}  |  Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    if auteur.strip():
        p2 = doc.add_paragraph(f"Préparé par : {auteur.strip()}"); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_heading("1. Synthèse du projet", level=1)
    keys = [("Trafic initial", f"{format_nombre(float(report['Trafic initial (PL/jour, deux sens)']))} PL/jour (deux sens)"),
        ("Croissance annuelle", f"{report['Croissance annuelle (%)']} %"), ("Durée de calcul", f"{report['Durée (années)']} ans"),
        ("Trafic cumulé estimé", f"{format_nombre(float(report['Trafic cumulé estimé (PL)']))} PL"),
        ("Classe de trafic", f"{report['Classe trafic indicative']} (indicative)"),
        ("CBR du sol", f"{report['CBR (%)']} %"),
        ("Classe de sol", f"{report['Classe sol indicative']} (indicative)"),
        ("Dimensions du tronçon", f"{report['Longueur (m)']} m × {report['Largeur (m)']} m"),
        ("Épaisseur totale", f"{report['Épaisseur totale indicative (cm)']} cm")]
    table = doc.add_table(rows=1, cols=2); table.style = "Light Shading Accent 1"; table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.rows[0].cells[0].text = "Indicateur"; table.rows[0].cells[1].text = "Valeur"
    for k,v in keys:
        cells=table.add_row().cells; cells[0].text=k; cells[1].text=str(v)
    doc.add_heading("2. Métré géométrique préliminaire", level=1)
    table2 = doc.add_table(rows=1, cols=4); table2.style = "Light Shading Accent 1"; table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, val in zip(table2.rows[0].cells, ["Couche", "Matériau", "Épaisseur (cm)", "Volume (m³)"]): cell.text=val
    for _, row in df_metre.iterrows():
        cells=table2.add_row().cells
        vals=[row["Couche"],row["Matériau"],f"{float(row['Épaisseur (cm)']):g}",f"{float(row['Volume géométrique (m³)']):,.2f}".replace(",", " ")]
        for cell,val in zip(cells,vals): cell.text=str(val)
    cells=table2.add_row().cells; cells[0].text="TOTAL"; cells[1].text=""; cells[2].text=""; cells[3].text=f"{float(df_metre['Volume géométrique (m³)'].sum()):,.2f}".replace(",", " ")
    doc.add_heading("3. Hypothèses et limites", level=1)
    doc.add_paragraph("Les volumes sont des volumes géométriques théoriques calculés à partir de la longueur, de la largeur et des épaisseurs indiquées. Ils ne prennent pas en compte les pertes, le compactage, le foisonnement, les pentes, les accotements ni les corrections de chantier.")
    p=doc.add_paragraph(); r=p.add_run("AVERTISSEMENT TECHNIQUE : "); r.bold=True; r.font.color.rgb=RGBColor(180,70,20)
    p.add_run("les classes et épaisseurs proposées par ce prototype sont indicatives et non normatives. Ce rapport ne remplace pas une étude géotechnique, un guide de dimensionnement reconnu ni la validation par un ingénieur compétent avant tout projet réel.")
    out=io.BytesIO(); doc.save(out); return out.getvalue()


def get_sheet():
    """Connexion cloud facultative; nécessite les secrets Streamlit appropriés."""
    if gspread is None or Credentials is None:
        return None, "Modules Google non installés."
    try:
        service_account = st.secrets.get("gcp_service_account", None)
        nom_feuille = st.secrets.get("google_sheet_name", "Donnees_Chaussee")
        if not service_account:
            return None, "Cloud non configuré (secrets absents). L’application fonctionne localement."
        creds = Credentials.from_service_account_info(
            service_account,
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
        )
        client = gspread.authorize(creds)
        return client.open(nom_feuille).sheet1, None
    except Exception as exc:
        return None, f"Connexion cloud indisponible : {exc}"


def get_users_sheet():
    """Retourne l'onglet 'Utilisateurs' de la même feuille Google Sheets, le crée si absent."""
    if gspread is None or Credentials is None:
        return None, "Modules Google non installés."
    try:
        service_account = st.secrets.get("gcp_service_account", None)
        nom_feuille = st.secrets.get("google_sheet_name", "Donnees_Chaussee")
        if not service_account:
            return None, "Cloud non configuré (secrets absents)."
        creds = Credentials.from_service_account_info(
            service_account,
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open(nom_feuille)
        try:
            ws = spreadsheet.worksheet("Utilisateurs")
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title="Utilisateurs", rows=100, cols=2)
            ws.append_row(["Nom", "MotDePasseHash"], value_input_option="USER_ENTERED")
        return ws, None
    except Exception as exc:
        return None, f"Connexion cloud indisponible : {exc}"


def hash_mdp(mdp: str) -> str:
    return hashlib.sha256(mdp.encode("utf-8")).hexdigest()


@st.cache_data(ttl=600, show_spinner=False)
def meteo_actuelle(lat: float, lon: float):
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon,
                    "current": "temperature_2m,precipitation,wind_speed_10m"},
            timeout=8,
        )
        response.raise_for_status()
        return response.json().get("current")
    except (requests.RequestException, ValueError):
        return None

# -----------------------------------------------------------------------------
# Accueil : écran épuré, saisie du pseudo et identité visuelle contrastée
# -----------------------------------------------------------------------------
if not st.session_state.get("current_user"):
    st.markdown(
        """
        <div class="welcome-hero">
          <div class="welcome-kicker">SHM · GÉNIE CIVIL</div>
          <h1 style="color:#FFFFFF !important;-webkit-text-fill-color:#FFFFFF !important;opacity:1 !important;text-shadow:0 1px 2px rgba(0,0,0,.18);">Bienvenue sur SHM Road</h1>
          <p>
            Votre espace de travail pour les études préliminaires de chaussées :
            analyse du trafic, caractérisation du sol, visualisation de la structure
            et préparation de rapports de métré.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Une seule carte d'accès : le panneau de présentation à gauche a été supprimé.
    _, col_form, _ = st.columns([0.65, 1.7, 0.65], gap="large")
    with col_form:
        st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
        st.markdown("### Accéder à votre espace")
        st.markdown("Saisissez votre pseudo pour personnaliser votre session.")
        with st.form("pseudo_form", clear_on_submit=False):
            pseudo = st.text_input(
                "Votre pseudo",
                placeholder="Ex. : Shamma, Ivan, Étudiant GC…",
                max_chars=40,
            )
            continuer = st.form_submit_button(
                "Continuer vers SHM Road", type="primary", use_container_width=True
            )
        st.markdown('</div>', unsafe_allow_html=True)
        if continuer:
            pseudo_nettoye = " ".join(pseudo.strip().split())
            if not pseudo_nettoye:
                st.warning("Veuillez saisir un pseudo pour continuer.")
            else:
                st.session_state.current_user = pseudo_nettoye
                st.rerun()
    st.stop()

DEFAULTS = {"brand_name": "SHM", "report_author": "", "project_name": "Projet routier", "pl_jour": 450, "tc": 3.5, "duree": 15,
            "part_voie": 50, "cbr": 8.0, "drainage": "Moyen", "latitude": 5.9631,
            "longitude": 10.1591, "largeur": 7.0, "longueur": 1000.0}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

with st.sidebar:
    st.markdown("# 🛣️ SHM Road")
    st.caption("Prototype d’étude de chaussée")
    st.success(f"Espace de : {st.session_state.current_user}")
    if st.button("Changer de pseudo"):
        del st.session_state["current_user"]
        st.rerun()
    st.markdown("---")
    with st.expander("🎨 Identité des rapports", expanded=False):
        st.text_input("Nom / marque", key="brand_name", value=st.session_state.get("brand_name", "SHM"))
        st.text_input("Préparé par", key="report_author", value=st.session_state.get("report_author", ""))
        st.caption("Logo facultatif pour les documents PDF et Word")
        uploaded_logo = st.file_uploader("Importer un logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="brand_logo")
    st.markdown("---")
    st.caption("Toutes les sections sont regroupées ci-dessous : dépliez celle dont vous avez besoin.")
    st.markdown("---")
    st.caption("Version pédagogique — résultats à valider avant usage réel.")

st.markdown(f'<div class="hero"><div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;opacity:.82;margin-bottom:8px;">SHM ROAD · ESPACE DE TRAVAIL</div><h1>Bonjour {html.escape(str(st.session_state.current_user))}, votre étude de chaussée</h1><div>Trafic · Portance du sol · Structure · Coupe · Métré · Historique</div></div>', unsafe_allow_html=True)
st.markdown('<div class="notice"><b>Important :</b> le catalogue d’épaisseurs inclus est illustratif, pas normatif. Ne pas utiliser ses résultats pour exécuter des travaux sans remplacement par un guide validé et vérification par un ingénieur compétent.</div>', unsafe_allow_html=True)

# Calcul partagé
n_pl = trafic_cumule(st.session_state.pl_jour, st.session_state.tc, st.session_state.duree, st.session_state.part_voie)
classe_t = classer_trafic(n_pl)
cbr_effectif = st.session_state.cbr
classe_s = classer_sol(cbr_effectif)
e_ref = dict(zip(["Roulement", "Base", "Fondation"], CATALOGUE[classe_s][classe_t]))

materiaux = {}
for couche, options in MATERIALS.items():
    key = f"mat_{couche}"
    if key not in st.session_state:
        st.session_state[key] = options[0]
    materiaux[couche] = st.session_state[key]

# -----------------------------------------------------------------------------
# Navigation par onglets, répartis sur toute la largeur de l'écran
# -----------------------------------------------------------------------------
onglet_bord, onglet_trafic, onglet_sol, onglet_coupe, onglet_histo, onglet_scenarios = st.tabs([
    "🏠 Tableau de bord", "📊 Trafic & localisation", "🧱 Sol & dimensionnement",
    "📐 Coupe & métré", "☁️ Historique & statistiques", "🔮 Scénarios de trafic",
])

# -----------------------------------------------------------------------------
# SECTION : tableau de bord
# -----------------------------------------------------------------------------
with onglet_bord:
    st.subheader("Vue d’ensemble du projet")
    st.text_input("Nom du projet", key="project_name")
    a, b, c, d = st.columns(4)
    a.metric("Trafic cumulé estimé", f"{format_nombre(n_pl)} PL")
    b.metric("Classe de trafic (indicative)", classe_t)
    c.metric("CBR utilisé", f"{st.session_state.cbr:g} %")
    d.metric("Classe de sol (indicative)", classe_s)
    st.plotly_chart(generer_coupe(e_ref, materiaux), use_container_width=True, key="coupe_bord")
    st.subheader("Épaisseurs du catalogue illustratif")
    df = pd.DataFrame([{"Couche": k, "Matériau sélectionné": materiaux[k], "Épaisseur (cm)": v} for k, v in e_ref.items()])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.metric("Épaisseur totale indicative", f"{sum(e_ref.values())} cm")
    st.info("Les classes S1–S5 et T0–T5 affichées sont des catégories de démonstration. Confirmez les seuils et le catalogue avec le référentiel retenu.")

# -----------------------------------------------------------------------------
# SECTION : trafic / localisation
# -----------------------------------------------------------------------------
with onglet_trafic:
    st.subheader("Paramètres du trafic")
    left, right = st.columns(2)
    with left:
        st.number_input("Trafic initial de poids lourds (PL/jour, deux sens)", min_value=0, max_value=500000, step=50, key="pl_jour")
        st.number_input("Croissance annuelle du trafic (%)", min_value=0.0, max_value=15.0, step=0.1, key="tc")
    with right:
        st.number_input("Durée de calcul (années)", min_value=1, max_value=50, step=1, key="duree")
        st.slider("Part du trafic affectée à la voie étudiée (%)", min_value=1, max_value=100, key="part_voie")
    n_pl = trafic_cumule(st.session_state.pl_jour, st.session_state.tc, st.session_state.duree, st.session_state.part_voie)
    st.metric("Trafic cumulé estimé sur la voie", f"{format_nombre(n_pl)} PL")
    st.caption("Calcul basé sur une croissance annuelle constante et 365 jours/an. Vérifier la définition du trafic et la répartition par voie selon la méthode retenue.")
    st.markdown("---")
    st.subheader("Localisation et météo indicative")
    c1, c2 = st.columns(2)
    with c1:
        st.number_input("Latitude", min_value=-90.0, max_value=90.0, format="%.5f", key="latitude")
    with c2:
        st.number_input("Longitude", min_value=-180.0, max_value=180.0, format="%.5f", key="longitude")
    st.map(pd.DataFrame({"lat": [st.session_state.latitude], "lon": [st.session_state.longitude]}), zoom=8)
    if st.button("Récupérer la météo actuelle"):
        weather = meteo_actuelle(st.session_state.latitude, st.session_state.longitude)
        if weather:
            w1, w2, w3 = st.columns(3)
            w1.metric("Température", f"{weather.get('temperature_2m', '—')} °C")
            w2.metric("Précipitations", f"{weather.get('precipitation', '—')} mm")
            w3.metric("Vent", f"{weather.get('wind_speed_10m', '—')} km/h")
            st.caption("Météo instantanée uniquement : elle ne remplace pas les données climatiques historiques nécessaires à une étude de chaussée.")
        else:
            st.warning("Données météo indisponibles. Vérifiez la connexion Internet et les coordonnées.")

# -----------------------------------------------------------------------------
# SECTION : sol / dimensionnement
# -----------------------------------------------------------------------------
with onglet_sol:
    st.subheader("Caractérisation indicative de la plate-forme")
    st.number_input("Indice CBR (%)", min_value=0.1, max_value=100.0, step=0.5, key="cbr",
                     help="Indice portant de la plate-forme (California Bearing Ratio).")
    st.success(f"✅ CBR utilisé : {st.session_state.cbr:g} %")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Conditions de drainage", ["Mauvais", "Moyen", "Bon", "Très bon"], key="drainage")
    with c2:
        st.metric("Classe de sol indicative", classe_s)
        st.write("**Trafic cumulé estimé :**", f"{format_nombre(n_pl)} PL")
        st.write("**Classe de trafic indicative :**", classe_t)
    st.markdown("---")
    st.subheader("Catalogue d’épaisseurs de démonstration")
    st.warning("Ces valeurs ne sont pas certifiées par une norme. Elles servent uniquement à tester l’interface et le flux de calcul.")
    epaisseurs = CATALOGUE[classe_s][classe_t]
    st.dataframe(pd.DataFrame([
        {"Couche": "Roulement", "Épaisseur indicative (cm)": epaisseurs[0]},
        {"Couche": "Base", "Épaisseur indicative (cm)": epaisseurs[1]},
        {"Couche": "Fondation", "Épaisseur indicative (cm)": epaisseurs[2]},
    ]), use_container_width=True, hide_index=True)
    st.caption("Avant une utilisation technique, documenter le guide, l’édition, le domaine d’application et les hypothèses de chaque valeur.")

# -----------------------------------------------------------------------------
# SECTION : coupe / métré
# -----------------------------------------------------------------------------
with onglet_coupe:
    st.subheader("Matériaux et représentation de la structure")
    st.caption("Le choix du matériau ne modifie pas automatiquement l’épaisseur : aucun coefficient d’équivalence universel n’est appliqué.")
    cols = st.columns(3)
    for col, couche in zip(cols, ["Roulement", "Base", "Fondation"]):
        with col:
            st.selectbox(f"Matériau — {couche}", MATERIALS[couche], key=f"mat_{couche}")
            if e_ref[couche] == 0:
                st.caption("Aucune épaisseur proposée par le catalogue illustratif pour cette couche.")
    materiaux = {c: st.session_state[f"mat_{c}"] for c in ["Roulement", "Base", "Fondation"]}
    st.plotly_chart(generer_coupe(e_ref, materiaux), use_container_width=True, key="coupe_dimensionnement")
    st.subheader("Récapitulatif")
    df_layers = pd.DataFrame([{"Couche": c, "Matériau": materiaux[c], "Épaisseur indicative (cm)": e_ref[c]} for c in e_ref])
    st.dataframe(df_layers, use_container_width=True, hide_index=True)
    st.metric("Épaisseur totale indicative", f"{sum(e_ref.values())} cm")
    st.markdown("---")
    st.subheader("Métré géométrique préliminaire")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Longueur du tronçon (m)", min_value=0.0, max_value=1000000.0, step=50.0, key="longueur")
    with col2:
        st.number_input("Largeur totale de la chaussée (m)", min_value=0.1, max_value=100.0, step=0.5, key="largeur")
    rows = []
    for couche, e_cm in e_ref.items():
        volume = st.session_state.longueur * st.session_state.largeur * (e_cm / 100.0)
        rows.append({"Couche": couche, "Matériau": materiaux[couche], "Épaisseur (cm)": e_cm, "Volume géométrique (m³)": volume})
    df_metre = pd.DataFrame(rows)
    st.dataframe(df_metre, use_container_width=True, hide_index=True, column_config={"Volume géométrique (m³)": st.column_config.NumberColumn(format="%.2f m³")})
    st.caption("Volumes géométriques théoriques uniquement : ne comprennent ni pertes, ni compactage, ni foisonnement, ni corrections de métré.")

    report = {
        "Projet": st.session_state.project_name,
        "Date de génération": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Statut": "Étude préliminaire — catalogue illustratif non normatif",
        "Trafic initial (PL/jour, deux sens)": st.session_state.pl_jour,
        "Croissance annuelle (%)": st.session_state.tc,
        "Durée (années)": st.session_state.duree,
        "Part voie étudiée (%)": st.session_state.part_voie,
        "Trafic cumulé estimé (PL)": round(n_pl),
        "Classe trafic indicative": classe_t,
        "CBR (%)": st.session_state.cbr,
        "Classe sol indicative": classe_s,
        "Drainage": st.session_state.drainage,
        "Latitude": st.session_state.latitude,
        "Longitude": st.session_state.longitude,
        "Longueur (m)": st.session_state.longueur,
        "Largeur (m)": st.session_state.largeur,
        "Épaisseur totale indicative (cm)": sum(e_ref.values()),
    }
    for c in e_ref:
        report[f"Matériau {c}"] = materiaux[c]
        report[f"Épaisseur {c} (cm)"] = e_ref[c]
    report_df = pd.DataFrame([report])
    st.markdown("### Exporter un rapport propre")
    st.caption("Choisis le format de document souhaité. Le rapport comprend une synthèse, un tableau de métré lisible et les hypothèses de calcul.")
    exp1, exp2 = st.columns(2)
    with exp1:
        try:
            pdf_bytes = creer_pdf_metre("Rapport de métré de chaussée", st.session_state.project_name, report, df_metre, st.session_state.brand_name, st.session_state.report_author, uploaded_logo.getvalue() if uploaded_logo else None)
            st.download_button("📄 Télécharger le rapport PDF", data=pdf_bytes, file_name="rapport_metre_chaussee.pdf", mime="application/pdf", use_container_width=True)
        except ImportError:
            st.warning("Pour activer l’export PDF, installe reportlab depuis requirements.txt.")
    with exp2:
        try:
            word_bytes = creer_word_metre("Rapport de métré de chaussée", st.session_state.project_name, report, df_metre, st.session_state.brand_name, st.session_state.report_author, uploaded_logo.getvalue() if uploaded_logo else None)
            st.download_button("📝 Télécharger le rapport Word", data=word_bytes, file_name="rapport_metre_chaussee.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        except ImportError:
            st.warning("Pour activer l’export Word, installe python-docx depuis requirements.txt.")

# -----------------------------------------------------------------------------
# SECTION : cloud / statistiques
# -----------------------------------------------------------------------------
with onglet_histo:
    st.subheader("Historique des études")
    sheet, cloud_error = get_sheet()
    if cloud_error:
        st.info(cloud_error)
    df_hist = pd.DataFrame()
    if sheet is None:
        st.markdown("Pour activer le cloud, installez les dépendances Google et configurez les secrets Streamlit (voir le guide fourni).")
    else:
        try:
            data = sheet.get_all_records()
            df_hist = pd.DataFrame(data)
        except Exception as exc:
            st.error(f"Impossible de lire l’historique : {exc}")
    if sheet is not None and df_hist.empty:
        st.info("Aucune étude enregistrée pour le moment. Vous pouvez enregistrer une étude depuis cette page lorsque les paramètres sont prêts.")
    elif not df_hist.empty:
        if "Utilisateur" in df_hist.columns:
            voir_tout = st.checkbox("Afficher les études de tous les utilisateurs", value=False)
            if not voir_tout:
                df_hist = df_hist[df_hist["Utilisateur"] == st.session_state.current_user]
        st.dataframe(df_hist, use_container_width=True)
        numeric_candidates = [c for c in ["Trafic_cumule", "CBR", "Epaisseur_totale_cm"] if c in df_hist.columns]
        if numeric_candidates:
            variable = st.selectbox("Variable à analyser", numeric_candidates)
            serie = pd.to_numeric(df_hist[variable], errors="coerce").dropna()
            if not serie.empty:
                a, b, c, d = st.columns(4)
                a.metric("Nombre de valeurs", len(serie))
                b.metric("Moyenne", f"{serie.mean():.2f}")
                c.metric("Minimum", f"{serie.min():.2f}")
                d.metric("Maximum", f"{serie.max():.2f}")
                st.plotly_chart(px.histogram(x=serie, nbins=min(15, max(5, len(serie))), labels={"x": variable}, title=f"Distribution — {variable}"), use_container_width=True, key=f"hist_{variable}")
                if len(serie) >= 2:
                    st.plotly_chart(px.line(y=serie.reset_index(drop=True), labels={"x": "Observation", "y": variable}, markers=True, title=f"Valeurs enregistrées — {variable}"), use_container_width=True, key=f"line_{variable}")
        if {"Latitude", "Longitude"}.issubset(df_hist.columns):
            coords = df_hist[["Latitude", "Longitude"]].apply(pd.to_numeric, errors="coerce").dropna()
            if not coords.empty:
                coords.columns = ["lat", "lon"]
                st.subheader("Localisation des études enregistrées")
                st.map(coords)
    st.markdown("---")
    st.subheader("Enregistrer les paramètres actuels")
    if st.button("☁️ Enregistrer l’étude actuelle", type="primary"):
        try:
            row = {
                "Horodatage": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Utilisateur": st.session_state.current_user,
                "Projet": st.session_state.project_name,
                "PL_jour": st.session_state.pl_jour,
                "Taux_croissance_pct": st.session_state.tc,
                "Duree_annees": st.session_state.duree,
                "Part_voie_pct": st.session_state.part_voie,
                "Trafic_cumule": round(n_pl), "Classe_trafic": classe_t,
                "CBR": st.session_state.cbr, "Classe_sol": classe_s,
                "Drainage": st.session_state.drainage,
                "Materiau_Roulement": st.session_state.mat_Roulement,
                "Epaisseur_Roulement_cm": e_ref["Roulement"],
                "Materiau_Base": st.session_state.mat_Base,
                "Epaisseur_Base_cm": e_ref["Base"],
                "Materiau_Fondation": st.session_state.mat_Fondation,
                "Epaisseur_Fondation_cm": e_ref["Fondation"],
                "Epaisseur_totale_cm": sum(e_ref.values()),
                "Latitude": st.session_state.latitude, "Longitude": st.session_state.longitude,
                "Statut": "Préliminaire — catalogue illustratif non normatif",
            }
            sheet.append_row(list(row.values()), value_input_option="USER_ENTERED")
            st.success("Étude enregistrée dans Google Sheets.")
        except Exception as exc:
            st.error(f"Échec de l’enregistrement : {exc}")

# -----------------------------------------------------------------------------
# SECTION : scénarios de trafic
# -----------------------------------------------------------------------------
with onglet_scenarios:
    st.subheader("Projection indicative du trafic cumulé")
    c1, c2 = st.columns(2)
    with c1:
        taux_bas = st.number_input("Croissance — scénario bas (%)", min_value=0.0, max_value=15.0, value=max(0.0, st.session_state.tc - 1.0), step=0.1)
    with c2:
        taux_haut = st.number_input("Croissance — scénario haut (%)", min_value=float(taux_bas), max_value=20.0, value=min(20.0, max(taux_bas, st.session_state.tc + 1.0)), step=0.1)
    horizon = st.slider("Horizon de projection (années)", min_value=1, max_value=50, value=20)
    annees = np.arange(0, horizon + 1)
    fig = go.Figure()
    for taux, nom in [(taux_bas, "Scénario bas"), (st.session_state.tc, "Scénario central"), (taux_haut, "Scénario haut")]:
        vals = [trafic_cumule(st.session_state.pl_jour, taux, int(n), st.session_state.part_voie) for n in annees]
        fig.add_trace(go.Scatter(x=annees, y=vals, mode="lines", name=f"{nom} ({taux:.1f} %)"))
    for seuil, classe in [(5e5, "T4"), (2e6, "T3"), (7e6, "T2"), (2e7, "T1"), (5e7, "T0")]:
        fig.add_hline(y=seuil, line_dash="dot", annotation_text=f"Seuil {classe}", annotation_position="top left")
    fig.update_layout(title="Scénarios de trafic cumulé", xaxis_title="Années depuis le début de la projection", yaxis_title="PL cumulés estimés", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, key="scenario_trafic")
    st.caption("Les scénarios sont des hypothèses, pas des prévisions garanties. Les seuils de classes doivent être confirmés selon le référentiel adopté.")

st.markdown("---")
st.markdown('<p class="small-muted">Prototype pédagogique · Vérification normative et validation professionnelle requises avant toute utilisation pour un projet réel.</p>', unsafe_allow_html=True)
