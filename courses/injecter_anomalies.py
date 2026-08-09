from pathlib import Path

import pandas as pd


FICHIER_ENTREE = Path(
    "course_2026-08-08_16-55-25.csv"
)

FICHIER_SORTIE = Path(
    "course_2026-08-08_16-55-25_invalide.csv"
)


# --------------------------------------------------------------
# Lecture du fichier original
# --------------------------------------------------------------

df = pd.read_csv(FICHIER_ENTREE)


def injecter_valeur(
    temps_s: float,
    colonne: str,
    nouvelle_valeur: float,
    nombre_echantillons: int = 1,
):
    """
    Remplace une ou plusieurs mesures à proximité du temps demandé.

    temps_s:
        Instant auquel injecter l'anomalie.

    colonne:
        Colonne à modifier.

    nouvelle_valeur:
        Valeur irréaliste injectée.

    nombre_echantillons:
        Nombre de lignes consécutives à modifier.
    """
    if colonne not in df.columns:
        raise ValueError(
            f"Colonne absente du CSV : {colonne}"
        )

    # Trouve la position de la mesure la plus proche.
    position = (
        df["duree_s"]
        .sub(temps_s)
        .abs()
        .to_numpy()
        .argmin()
    )

    position_fin = min(
        position + nombre_echantillons,
        len(df),
    )

    ancienne_valeur = df.iloc[position][colonne]
    temps_reel = df.iloc[position]["duree_s"]

    df.iloc[
        position:position_fin,
        df.columns.get_loc(colonne),
    ] = nouvelle_valeur

    print(
        f"Injection à {temps_reel:.2f} s : "
        f"{colonne}, "
        f"{ancienne_valeur} -> {nouvelle_valeur}, "
        f"{position_fin - position} échantillon(s)"
    )


# --------------------------------------------------------------
# Injection des anomalies
# --------------------------------------------------------------

# Pitch hors de la plage autorisée de ±15°.
injecter_valeur(
    temps_s=300,
    colonne="pitch_deg",
    nouvelle_valeur=30.0,
)

injecter_valeur(
    temps_s=500,
    colonne="pitch_deg",
    nouvelle_valeur=-25.0,
)

# Sauts isolés restant dans la plage, utiles pour tester
# le filtre médian et le limiteur de variation.
injecter_valeur(
    temps_s=700,
    colonne="pitch_deg",
    nouvelle_valeur=14.0,
)

injecter_valeur(
    temps_s=900,
    colonne="pitch_deg",
    nouvelle_valeur=-12.0,
    nombre_echantillons=2,
)

# Vitesse physiquement irréaliste pour ton prototype.
injecter_valeur(
    temps_s=400,
    colonne="vitesse_kmh",
    nouvelle_valeur=80.0,
)

injecter_valeur(
    temps_s=800,
    colonne="vitesse_kmh",
    nouvelle_valeur=-10.0,
)

# Accélération hors de la plage ±3 m/s².
injecter_valeur(
    temps_s=600,
    colonne="acceleration_ms2",
    nouvelle_valeur=5.0,
)

injecter_valeur(
    temps_s=1000,
    colonne="acceleration_ms2",
    nouvelle_valeur=-6.0,
)


# --------------------------------------------------------------
# Enregistrement d'une nouvelle copie
# --------------------------------------------------------------

df.to_csv(
    FICHIER_SORTIE,
    index=False,
)

print(
    "\nFichier modifié créé : "
    f"{FICHIER_SORTIE}"
)