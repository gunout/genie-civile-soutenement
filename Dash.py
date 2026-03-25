"""
Application Streamlit - Calculateur de béton pour mur de parpaing armé
Auteur : Assistant
Description : Calcule les quantités de béton, nombre de parpaings, aciers et coffrage
              selon le métré du mur (longueur, hauteur, épaisseur) et les options d'armature.
              Conforme aux principes du DTU 23.1 et Eurocode 2.
"""

import streamlit as st
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt

# Configuration de la page
st.set_page_config(
    page_title="Béton Mur Parpaing Armé | Calculateur Métré",
    page_icon="🧱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- CONSTANTES TECHNIQUES ----------
# Dimensions standard parpaing (cm)
PARPAING_LONGUEUR = 50  # cm
PARPAING_HAUTEUR = 20   # cm

# Aciers : diamètres standards avec poids linéaire (kg/m)
ACIER_DIAMETRES = {
    "6 mm": 0.222,
    "8 mm": 0.395,
    "10 mm": 0.617,
    "12 mm": 0.888,
    "14 mm": 1.208,
    "16 mm": 1.578,
    "20 mm": 2.466
}

# ---------- FONCTIONS DE CALCUL ----------
def calculer_nombre_parpaings(longueur_m, hauteur_m, epaisseur_cm):
    """
    Calcule le nombre approximatif de parpaings (50x20)
    Prend en compte l'épaisseur pour ajustement (joints)
    """
    nb_horizontal = math.ceil(longueur_m * 100 / PARPAING_LONGUEUR)
    nb_vertical = math.ceil(hauteur_m * 100 / PARPAING_HAUTEUR)
    return nb_horizontal * nb_vertical

def calculer_volume_mortier_joints(longueur_m, hauteur_m, epaisseur_cm):
    """
    Calcule le volume de mortier pour les joints horizontaux et verticaux
    Joint horizontal: 1 cm d'épaisseur, largeur = épaisseur mur
    Joint vertical: 1 cm d'épaisseur, hauteur = hauteur parpaing
    """
    epaisseur_m = epaisseur_cm / 100
    nb_parpaings = calculer_nombre_parpaings(longueur_m, hauteur_m, epaisseur_cm)
    
    # Nombre de joints horizontaux = (nombre de rangées - 1) * longueur
    nb_rangees = math.ceil(hauteur_m * 100 / PARPAING_HAUTEUR)
    longueur_lin_joins_horiz = (nb_rangees - 1) * longueur_m
    volume_joints_horiz = longueur_lin_joins_horiz * epaisseur_m * 0.01  # 1 cm d'épaisseur
    
    # Nombre de joints verticaux = (nombre de blocs par rangée - 1) * nb rangées
    nb_blocs_rangee = math.ceil(longueur_m * 100 / PARPAING_LONGUEUR)
    longueur_lin_joins_vert = (nb_blocs_rangee - 1) * nb_rangees * PARPAING_HAUTEUR / 100
    volume_joints_vert = longueur_lin_joins_vert * epaisseur_m * 0.01  # 1 cm d'épaisseur
    
    return volume_joints_horiz + volume_joints_vert

def calculer_chainage_vertical(longueur_m, hauteur_m, espacement_vertical_m, section_largeur_cm, section_profondeur_cm):
    """
    Calcule le volume de béton pour les potelets / chaînages verticaux.
    Retourne volume (m3), nombre de potelets et liste des positions
    """
    if espacement_vertical_m <= 0 or longueur_m <= 0:
        return 0.0, 0, []
    
    # Calcul du nombre de potelets (aux extrémités + intermédiaires)
    nb_intervalles = max(1, math.ceil(longueur_m / espacement_vertical_m))
    nb_potelets = nb_intervalles + 1
    
    # Positions approximatives
    positions = [i * (longueur_m / nb_intervalles) for i in range(nb_potelets)]
    
    section_m2 = (section_largeur_cm / 100) * (section_profondeur_cm / 100)
    volume_unitaire = section_m2 * hauteur_m
    volume_total = nb_potelets * volume_unitaire
    
    return volume_total, nb_potelets, positions

def calculer_chainage_horizontal(longueur_m, nb_niveaux, section_largeur_cm, section_hauteur_cm, hauteur_mur=None, positions_personnalisees=None):
    """
    Chaînage horizontal (longrines) au niveau des fondations, seuils, linteaux, etc.
    nb_niveaux : nombre de ceintures horizontales
    positions_personnalisees : liste des hauteurs (m) si spécifiques
    """
    section_m2 = (section_largeur_cm / 100) * (section_hauteur_cm / 100)
    volume_total = longueur_m * section_m2 * nb_niveaux
    
    # Calcul des positions si hauteur_mur fournie
    positions = []
    if hauteur_mur and nb_niveaux > 0:
        if nb_niveaux == 1:
            positions = [hauteur_mur]  # chainage haut
        elif nb_niveaux == 2:
            positions = [0, hauteur_mur]  # bas et haut
        else:
            step = hauteur_mur / (nb_niveaux - 1)
            positions = [i * step for i in range(nb_niveaux)]
    
    return volume_total, positions

def calculer_volume_fondation(longueur_m, largeur_fond_m, hauteur_fond_m, redan_m=0.0):
    """Volume de béton pour la semelle filante sous le mur"""
    return longueur_m * largeur_fond_m * hauteur_fond_m

def calculer_aciers_verticaux(hauteur_m, nb_potelets, nbr_barres_par_potelet, diam_choisi, ancrage_m=0.4):
    """Aciers verticaux dans les chaînages verticaux"""
    densite = ACIER_DIAMETRES[diam_choisi]
    # Longueur par barre = hauteur + ancrage en pied + retour en tête
    longueur_par_barre = hauteur_m + ancrage_m + 0.2
    longueur_totale = nb_potelets * nbr_barres_par_potelet * longueur_par_barre
    poids = longueur_totale * densite
    return poids, longueur_totale

def calculer_aciers_horizontaux(longueur_m, nb_niveaux, nbr_barres_par_chainage, diam_choisi, recouvrement_m=0.5):
    """Aciers longitudinaux dans les chainages horizontaux"""
    densite = ACIER_DIAMETRES[diam_choisi]
    # Ajout des recouvrements tous les 12m environ
    nb_recouvrements = max(0, math.floor(longueur_m / 12))
    longueur_par_barre = longueur_m + (nb_recouvrements * recouvrement_m)
    longueur_totale = nb_niveaux * nbr_barres_par_chainage * longueur_par_barre
    poids = longueur_totale * densite
    return poids, longueur_totale

def calculer_cadres_et_etriers(perimetre_m, espacement_m, longueur_totale_chainage_lineaire, diam_cadre_choisi):
    """Estimation du poids des cadres / étriers pour les chainages"""
    if espacement_m <= 0 or longueur_totale_chainage_lineaire <= 0:
        return 0, 0
    nb_cadres = int(longueur_totale_chainage_lineaire / espacement_m) + 1
    longueur_totale_acier_cadres = nb_cadres * perimetre_m
    densite = ACIER_DIAMETRES[diam_cadre_choisi]
    poids = longueur_totale_acier_cadres * densite
    return poids, nb_cadres

def calculer_remplissage_blocs(longueur_m, hauteur_m, epaisseur_cm, taux_remplissage=0.33):
    """
    Volume de béton pour remplissage des alvéoles des parpaings
    (uniquement si armature verticale dans les blocs)
    """
    nb_parpaings = calculer_nombre_parpaings(longueur_m, hauteur_m, epaisseur_cm)
    # Volume d'une alvéole approx. (parpaing 20 cm : 2 alvéoles de ~5L)
    volume_alveole_litres = 5.5  # litres
    volume_alveole_m3 = volume_alveole_litres / 1000
    nb_alveoles = nb_parpaings * 2  # 2 alvéoles par parpaing standard
    volume_total = nb_alveoles * volume_alveole_m3 * taux_remplissage
    return volume_total

def calculer_coffrage_chainages(volume_chainages_m3, type_coffrage="banche"):
    """
    Estimation surface coffrage (m²)
    type_coffrage: "banche" (ratio 8-10) ou "traditionnel" (ratio 10-12)
    """
    if type_coffrage == "banche":
        ratio = 8.5
    else:
        ratio = 11
    return volume_chainages_m3 * ratio

def calculer_surface_enduit(longueur_m, hauteur_m, faces=2):
    """Surface d'enduit (m²) pour les faces du mur"""
    return longueur_m * hauteur_m * faces

def generer_rapport_chantier(longueur_mur, hauteur_mur, volume_beton, poids_acier, nb_parpaings, surface_enduit):
    """Génère un résumé formaté pour le chantier"""
    rapport = f"""
    === RAPPORT CHANTIER - MUR PARPAING ARMÉ ===
    
    MÉTRÉ :
    - Longueur : {longueur_mur:.2f} m
    - Hauteur : {hauteur_mur:.2f} m
    - Surface de mur : {longueur_mur * hauteur_mur:.2f} m²
    
    QUANTITÉS PRINCIPALES :
    - Parpaings (50x20) : {nb_parpaings} unités
    - Béton (fondation + chainages) : {volume_beton:.2f} m³
    - Aciers HA : {poids_acier:.1f} kg
    - Surface d'enduit : {surface_enduit:.1f} m²
    
    RECOMMANDATIONS :
    - Prévoir 5 à 10% de marge pour la casse et les coupes
    - Vérifier la disponibilité des matériaux avant commande
    - Respecter les délais de séchage du béton (28 jours)
    """
    return rapport


# ---------- INTERFACE STREAMLIT ----------
st.title("🧱 Tableau de bord : Béton pour mur de parpaing armé")
st.markdown("""
    Calculez les quantités de **béton**, **parpaings**, **aciers** et **coffrage** selon le métré de votre mur 
    et les dispositions d'armature (DTU 23.1). Modifiez les paramètres dans la barre latérale.
""")

# === SIDEBAR : Saisie des paramètres ===
with st.sidebar:
    st.header("📐 Dimensions du mur")
    longueur_mur = st.number_input("Longueur du mur (m)", min_value=0.5, max_value=100.0, value=8.0, step=0.5, format="%.2f")
    hauteur_mur = st.number_input("Hauteur du mur (m)", min_value=0.5, max_value=6.0, value=2.5, step=0.1, format="%.2f")
    epaisseur_mur = st.selectbox("Épaisseur du parpaing (cm)", options=[15, 20, 25], index=1, 
                                 help="20 cm standard pour mur porteur, 15 cm pour cloison, 25 cm pour mur renforcé")
    
    st.divider()
    st.header("🔩 Armatures & chaînages")
    st.markdown("**Chaînages verticaux (potelets)**")
    espacement_vertical = st.number_input("Espacement max entre potelets (m)", min_value=1.0, max_value=6.0, value=3.0, step=0.5, 
                                          help="DTU: ≤ 3m en zone sismique, ≤ 4m sinon")
    section_potelet_largeur = st.number_input("Largeur potelet (cm)", min_value=15, max_value=30, value=20, step=1)
    section_potelet_profondeur = st.number_input("Profondeur potelet (cm)", min_value=15, max_value=epaisseur_mur+10, value=epaisseur_mur, step=1)
    
    st.markdown("**Chaînages horizontaux (longrines)**")
    nb_chainages_horiz = st.number_input("Nombre de niveaux de chaînage horizontal", min_value=0, max_value=4, value=2, step=1,
                                         help="0: aucun, 1: chainage haut, 2: bas + haut, 3-4: niveaux intermédiaires")
    section_horiz_largeur = st.number_input("Largeur chainage horizontal (cm)", min_value=15, max_value=30, value=20, step=1)
    section_horiz_hauteur = st.number_input("Hauteur chainage horizontal (cm)", min_value=15, max_value=30, value=20, step=1)
    
    st.divider()
    st.header("🧪 Fondation (semelle filante)")
    inclure_fondation = st.checkbox("Inclure le béton de fondation", value=True)
    fond_largeur = st.number_input("Largeur semelle (cm)", min_value=40, max_value=100, value=60, step=5)
    fond_hauteur = st.number_input("Hauteur semelle (cm)", min_value=20, max_value=50, value=30, step=5)
    
    st.divider()
    st.header("⚙️ Aciers")
    col_ac1, col_ac2 = st.columns(2)
    with col_ac1:
        diam_vert = st.selectbox("Diamètre aciers verticaux", options=list(ACIER_DIAMETRES.keys()), index=3)
        nb_barres_par_potelet = st.number_input("Barres/potelet", min_value=2, max_value=8, value=4, step=1)
    with col_ac2:
        diam_horiz = st.selectbox("Diamètre aciers horizontaux", options=list(ACIER_DIAMETRES.keys()), index=3)
        nb_barres_par_chainage = st.number_input("Barres/chainage", min_value=2, max_value=6, value=4, step=1)
    
    diam_cadres = st.selectbox("Diamètre cadres / étriers", options=list(ACIER_DIAMETRES.keys()), index=1)
    espacement_cadres_cm = st.number_input("Espacement cadres (cm)", min_value=10, max_value=40, value=25, step=5)
    
    st.divider()
    st.markdown("💡 **Ajustements & options**")
    beton_majoration = st.slider("Majoration béton (%)", min_value=0, max_value=15, value=5, step=1, help="Perte / débord / surépaisseur")
    acier_majoration = st.slider("Majoration acier (%)", min_value=0, max_value=10, value=5, step=1)
    inclure_mortier = st.checkbox("Inclure le mortier de joints", value=True)
    inclure_remplissage = st.checkbox("Inclure remplissage alvéoles (optionnel)", value=False)
    type_coffrage = st.selectbox("Type de coffrage", options=["banche", "traditionnel"], index=0)

# === CALCULS PRINCIPAUX ===
# 1. Parpaings
nb_parpaings = calculer_nombre_parpaings(longueur_mur, hauteur_mur, epaisseur_mur)

# 2. Mortier joints
volume_mortier = 0
if inclure_mortier:
    volume_mortier = calculer_volume_mortier_joints(longueur_mur, hauteur_mur, epaisseur_mur)

# 3. Chaînages verticaux
vol_chain_vert, nb_potelets, positions_vert = calculer_chainage_vertical(
    longueur_mur, hauteur_mur, espacement_vertical, 
    section_potelet_largeur, section_potelet_profondeur
)

# 4. Chaînages horizontaux
vol_chain_horiz, positions_horiz = calculer_chainage_horizontal(
    longueur_mur, nb_chainages_horiz, section_horiz_largeur, 
    section_horiz_hauteur, hauteur_mur
)

# 5. Fondation
volume_fond = 0
if inclure_fondation:
    volume_fond = calculer_volume_fondation(longueur_mur, fond_largeur/100, fond_hauteur/100)

# 6. Volume total béton (hors remplissage alvéoles)
volume_beton_avant_majo = vol_chain_vert + vol_chain_horiz + volume_fond

# 7. Remplissage alvéoles (optionnel)
volume_remplissage = 0
if inclure_remplissage:
    volume_remplissage = calculer_remplissage_blocs(longueur_mur, hauteur_mur, epaisseur_mur, taux_remplissage=0.5)

volume_beton_total_avec_remplissage = volume_beton_avant_majo + volume_remplissage
volume_beton_final = volume_beton_total_avec_remplissage * (1 + beton_majoration / 100)

# 8. Aciers verticaux
poids_acier_vert, long_vert_tot = calculer_aciers_verticaux(
    hauteur_mur, nb_potelets, nb_barres_par_potelet, diam_vert
)

# 9. Aciers horizontaux
poids_acier_horiz, long_horiz_tot = calculer_aciers_horizontaux(
    longueur_mur, nb_chainages_horiz, nb_barres_par_chainage, diam_horiz
)

# 10. Cadres / étriers
longueur_totale_chainage_lineaire = (nb_potelets * hauteur_mur) + (longueur_mur * nb_chainages_horiz)
perimetre_cadre_m = 2 * ((max(section_potelet_largeur, section_horiz_largeur)/100) + 
                         (max(section_potelet_profondeur, section_horiz_hauteur)/100))
if perimetre_cadre_m < 0.6:
    perimetre_cadre_m = 0.8

poids_cadres, nb_cadres = calculer_cadres_et_etriers(
    perimetre_cadre_m, espacement_cadres_cm/100, longueur_totale_chainage_lineaire, diam_cadres
)

# 11. Total aciers
poids_acier_total_avant_majo = poids_acier_vert + poids_acier_horiz + poids_cadres
poids_acier_final = poids_acier_total_avant_majo * (1 + acier_majoration / 100)

# 12. Coffrage
coffrage_m2 = calculer_coffrage_chainages(vol_chain_vert + vol_chain_horiz, type_coffrage)

# 13. Surface enduit
surface_enduit = calculer_surface_enduit(longueur_mur, hauteur_mur, faces=2)

# 14. Rapport chantier
rapport = generer_rapport_chantier(longueur_mur, hauteur_mur, volume_beton_final, poids_acier_final, nb_parpaings, surface_enduit)

# === AFFICHAGE DASHBOARD ===
st.subheader("📊 Récapitulatif métré & quantités principales")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📏 Longueur mur", f"{longueur_mur:.2f} m")
    st.metric("📐 Hauteur mur", f"{hauteur_mur:.2f} m")
    st.metric("🧱 Parpaings (50x20)", f"{nb_parpaings:,}".replace(",", " "))
with col2:
    st.metric("📌 Potelets (chain. vert.)", f"{nb_potelets} unités")
    st.metric("🔗 Chainages horizontaux", f"{nb_chainages_horiz} niveaux")
    st.metric("📦 Béton total (avec majo)", f"{volume_beton_final:.2f} m³")
with col3:
    st.metric("⚖️ Aciers totaux", f"{poids_acier_final:.1f} kg")
    st.metric("🪵 Coffrage estimé", f"{coffrage_m2:.1f} m²")
    st.metric("🏗️ Cadres / étriers", f"{nb_cadres:,} u")
with col4:
    st.metric("🧴 Mortier joints", f"{volume_mortier:.3f} m³" if inclure_mortier else "Non inclus")
    st.metric("🪣 Remplissage alvéoles", f"{volume_remplissage:.3f} m³" if inclure_remplissage else "Optionnel")
    st.metric("🎨 Surface enduit", f"{surface_enduit:.1f} m²")

st.divider()

# === TABLEAUX DÉTAILLÉS ===
tab1, tab2, tab3, tab4 = st.tabs(["📋 Béton", "🔩 Aciers", "📐 Positions chaînages", "📄 Rapport chantier"])

with tab1:
    st.subheader("🧮 Détail des volumes de béton")
    detail_beton = pd.DataFrame([
        {"Composant": "Chaînages verticaux (potelets)", "Volume (m³)": f"{vol_chain_vert:.3f}", 
         "Observations": f"{nb_potelets} potelets de {section_potelet_largeur}x{section_potelet_profondeur} cm"},
        {"Composant": "Chaînages horizontaux", "Volume (m³)": f"{vol_chain_horiz:.3f}", 
         "Observations": f"{nb_chainages_horiz} niveaux {section_horiz_largeur}x{section_horiz_hauteur} cm"},
    ])
    if inclure_fondation:
        detail_beton.loc[len(detail_beton)] = ["Semelle filante (fondation)", f"{volume_fond:.3f}", 
                                                f"Largeur {fond_largeur} cm, hauteur {fond_hauteur} cm"]
    if inclure_remplissage:
        detail_beton.loc[len(detail_beton)] = ["Remplissage alvéoles", f"{volume_remplissage:.3f}", 
                                                f"Taux ~50% des alvéoles"]
    if inclure_mortier:
        detail_beton.loc[len(detail_beton)] = ["Mortier joints", f"{volume_mortier:.3f}", 
                                                "Joints horizontaux + verticaux (1 cm)"]
    detail_beton.loc[len(detail_beton)] = ["Majoration béton", f"+{beton_majoration}%", 
                                            f"+{volume_beton_total_avec_remplissage * beton_majoration / 100:.3f} m³"]
    detail_beton.loc[len(detail_beton)] = ["✅ VOLUME TOTAL BÉTON", f"{volume_beton_final:.2f} m³", 
                                            "Inclut fondation + chainages + majo"]
    
    st.dataframe(detail_beton, use_container_width=True, hide_index=True)
    
    # Graphique répartition
    st.subheader("📊 Répartition du volume de béton (hors majo)")
    labels = []
    sizes = []
    if vol_chain_vert > 0:
        labels.append("Potelets")
        sizes.append(vol_chain_vert)
    if vol_chain_horiz > 0:
        labels.append("Chainages horiz.")
        sizes.append(vol_chain_horiz)
    if inclure_fondation and volume_fond > 0:
        labels.append("Fondation")
        sizes.append(volume_fond)
    if inclure_remplissage and volume_remplissage > 0:
        labels.append("Remplissage alv.")
        sizes.append(volume_remplissage)
    
    if len(sizes) > 0:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, 
               colors=['#4e79a7', '#f28e2b', '#e15759', '#59a14f'])
        ax.axis('equal')
        st.pyplot(fig)
    else:
        st.info("Aucun volume à afficher")

with tab2:
    st.subheader("📌 Aciers de ferraillage")
    acier_detail = pd.DataFrame([
        {"Type d'acier": "Aciers verticaux (potelets)", "Diamètre": diam_vert, 
         "Quantité (kg)": f"{poids_acier_vert:.1f}", 
         "Détail": f"{nb_potelets} potelets x {nb_barres_par_potelet} HA{diam_vert[:2]}"},
        {"Type d'acier": "Aciers horizontaux (longrines)", "Diamètre": diam_horiz, 
         "Quantité (kg)": f"{poids_acier_horiz:.1f}", 
         "Détail": f"{nb_chainages_horiz} chainages x {nb_barres_par_chainage} HA{diam_horiz[:2]}"},
        {"Type d'acier": "Cadres / étriers", "Diamètre": diam_cadres, 
         "Quantité (kg)": f"{poids_cadres:.1f}", 
         "Détail": f"Espacement {espacement_cadres_cm} cm, env. {nb_cadres} cadres"},
    ])
    acier_detail.loc[len(acier_detail)] = ["Majoration acier", f"+{acier_majoration}%", 
                                            f"+{(poids_acier_total_avant_majo * acier_majoration / 100):.1f} kg", 
                                            "Pertes / coupes / recouvrements"]
    acier_detail.loc[len(acier_detail)] = ["✅ TOTAL ACIER HA", "", f"{poids_acier_final:.1f} kg", 
                                            f"soit ~{poids_acier_final/1000:.2f} tonnes"]
    
    st.dataframe(acier_detail, use_container_width=True, hide_index=True)
    
    # Longueurs développées
    st.subheader("📏 Longueurs développées d'acier")
    col_len1, col_len2, col_len3 = st.columns(3)
    with col_len1:
        st.metric("Aciers verticaux", f"{long_vert_tot:.1f} m", help="Longueur totale développée")
    with col_len2:
        st.metric("Aciers horizontaux", f"{long_horiz_tot:.1f} m", help="Longueur totale développée")
    with col_len3:
        st.metric("Cadres", f"{nb_cadres * perimetre_cadre_m:.1f} m", help="Longueur totale développée")

with tab3:
    st.subheader("📍 Positions des chaînages")
    
    col_pos1, col_pos2 = st.columns(2)
    with col_pos1:
        st.markdown("**Chaînages verticaux (potelets)**")
        if positions_vert:
            pos_df = pd.DataFrame({
                "Potelet n°": range(1, len(positions_vert) + 1),
                "Position (m depuis départ)": [f"{p:.2f}" for p in positions_vert]
            })
            st.dataframe(pos_df, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun chaînage vertical configuré")
    
    with col_pos2:
        st.markdown("**Chaînages horizontaux**")
        if positions_horiz:
            horiz_df = pd.DataFrame({
                "Niveau": range(1, len(positions_horiz) + 1),
                "Hauteur depuis base (m)": [f"{h:.2f}" for h in positions_horiz]
            })
            st.dataframe(horiz_df, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun chaînage horizontal configuré")
    
    # Schéma simple des positions
    if positions_vert and positions_horiz and hauteur_mur > 0:
        st.markdown("**Schéma de principe (vue en élévation)**")
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Dessiner le mur
        ax.add_patch(plt.Rectangle((0, 0), longueur_mur, hauteur_mur, fill=False, edgecolor='black', linewidth=2, label="Mur"))
        
        # Chaînages verticaux
        for pos in positions_vert:
            ax.axvline(x=pos, ymin=0, ymax=hauteur_mur, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
            ax.plot(pos, hauteur_mur/2, 'ro', markersize=6)
        
        # Chaînages horizontaux
        for pos_h in positions_horiz:
            ax.axhline(y=pos_h, xmin=0, xmax=longueur_mur, color='blue', linestyle='--', linewidth=1.5, alpha=0.7)
            ax.plot(longueur_mur/2, pos_h, 'bs', markersize=6)
        
        ax.set_xlim(-0.5, longueur_mur + 0.5)
        ax.set_ylim(-0.3, hauteur_mur + 0.3)
        ax.set_xlabel("Longueur (m)")
        ax.set_ylabel("Hauteur (m)")
        ax.set_title("Position des chaînages verticaux (rouge) et horizontaux (bleu)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        st.pyplot(fig)

with tab4:
    st.subheader("📄 Rapport de chantier")
    st.text(rapport)
    
    # Export CSV
    st.markdown("---")
    st.subheader("📎 Export des données")
    
    export_data = {
        "Description": [
            "Longueur mur (m)", "Hauteur mur (m)", "Surface mur (m²)",
            "Nombre parpaings", "Béton total (m³) avec majoration", 
            "Aciers totaux (kg)", "Coffrage estimé (m²)",
            "Nb potelets", "Nb chainages horizontaux", "Surface enduit (m²)"
        ],
        "Valeur": [
            longueur_mur, hauteur_mur, longueur_mur * hauteur_mur,
            nb_parpaings, round(volume_beton_final, 2), 
            round(poids_acier_final, 1), round(coffrage_m2, 1),
            nb_potelets, nb_chainages_horiz, round(surface_enduit, 1)
        ]
    }
    df_export = pd.DataFrame(export_data)
    csv = df_export.to_csv(index=False, sep=';', decimal=',')
    st.download_button(
        "⬇️ Télécharger le résumé (.csv)", 
        data=csv, 
        file_name="metre_beton_mur_parpaing.csv", 
        mime="text/csv"
    )

# === NOTES TECHNIQUES ===
with st.expander("🔧 Notes techniques & rappels normatifs"):
    st.markdown("""
    **Principes de calcul :**
    - Le béton calculé correspond aux **chaînages verticaux (potelets)** et **chaînages horizontaux (longrines)** nécessaires à la réalisation d'un mur en parpaings armé selon DTU 23.1 / Eurocode 2.
    - Les **parpaings** standards sont de 50x20 cm (épaisseur variable : 15, 20 ou 25 cm). Le nombre affiché est estimatif (hors ouvertures, à ajuster selon projet).
    - **Fondation** : semelle filante continue, le volume est ajouté au béton total. Largeur mini = 2 x épaisseur mur.
    - **Aciers** : HA (haute adhérence). Les longueurs incluent un coefficient de recouvrement forfaitaire (ancrages, arrêts). Les cadres respectent l'espacement maximal recommandé (≤ 25-30 cm).
    - **Majorations** : pour pertes, chutes, réglages de coffrage et dépassements.
    
    **Recommandations :**
    - Prévoir 5 à 10% de matériaux supplémentaires pour la casse et les coupes.
    - Respecter les délais de séchage du béton (28 jours pour résistance nominale).
    - Ces résultats sont des **estimations de chantier**. Une étude structurelle détaillée est nécessaire pour les ouvrages réglementaires.
    """)

st.success("✅ Calculs mis à jour en temps réel — modifiez les paramètres dans la barre latérale pour affiner vos quantités.")
st.caption("Application à vocation technique pour avant-métré. Pour un projet réel, consultez un bureau d'études structures.")