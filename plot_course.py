import sys
import os
import math
from collections import deque
from statistics import median

import pandas as pd
import matplotlib.pyplot as plt

import puissance_estimee


def charger_course(chemin_csv):
    return pd.read_csv(chemin_csv, parse_dates=["timestamp_iso"])


def lisser_course(df):
    """
    Recalcule le pitch et la puissance en appliquant les
    protections actuellement utilisées dans power.py.
    """
    vitesse_resultat = []
    acceleration_resultat = []

    derniere_vitesse_valide = 0.0
    derniere_acceleration_valide = 0.0

    # Paramètres du traitement
    FENETRE_MEDIANE_PITCH = 5
    FENETRE_MOYENNE_PITCH = 15
    FENETRE_PUISSANCE = 25

    PITCH_MIN_DEG = -15.0
    PITCH_MAX_DEG = 15.0
    VITESSE_MAX_KMH = 60.0
    ACCELERATION_MAX_MS2 = 3.0
    VITESSE_VARIATION_PITCH_MAX = 3.0

    # Mémoires des filtres
    historique_pitch_median = deque(maxlen=FENETRE_MEDIANE_PITCH)
    moyenne_pitch = puissance_estimee.MoyenneMobile(fenetre=FENETRE_MOYENNE_PITCH)
    moyenne_puissance = puissance_estimee.MoyenneMobile(fenetre=FENETRE_PUISSANCE)

    dernier_pitch_valide = None
    dernier_pitch_limite = None
    dernier_temps_pitch = None

    derniere_acceleration_valide = 0.0
    derniere_puissance_affichee = 0.0

    pitch_resultat = []
    puissance_resultat = []

    for ligne in df.itertuples(index=False):
        temps_s = float(ligne.duree_s)
        vitesse_kmh = float(ligne.vitesse_kmh)
        pitch_brut = float(ligne.pitch_deg)
        acceleration_ms2 = float(ligne.acceleration_ms2)

        # 1. Validation et filtrage du pitch
        if PITCH_MIN_DEG <= pitch_brut <= PITCH_MAX_DEG:
            historique_pitch_median.append(pitch_brut)
            pitch_median = median(historique_pitch_median)

            if dernier_pitch_limite is None or dernier_temps_pitch is None:
                pitch_limite = pitch_median
            else:
                delta_t = temps_s - dernier_temps_pitch
                if delta_t <= 0.0:
                    delta_t = 0.2

                variation_max = VITESSE_VARIATION_PITCH_MAX * delta_t
                variation_demandee = pitch_median - dernier_pitch_limite
                variation_limitee = max(
                    -variation_max,
                    min(variation_demandee, variation_max),
                )
                pitch_limite = dernier_pitch_limite + variation_limitee

            dernier_pitch_limite = pitch_limite
            dernier_pitch_valide = moyenne_pitch.ajouter(pitch_limite)
            dernier_temps_pitch = temps_s

        # Si le pitch est invalide, on conserve la dernière valeur filtrée.
        if dernier_pitch_valide is None:
            dernier_pitch_valide = 0.0

        pitch_resultat.append(dernier_pitch_valide)

        # 2. Validation de l'accélération
        acceleration_valide = (
            -ACCELERATION_MAX_MS2 <= acceleration_ms2 <= ACCELERATION_MAX_MS2
        )

        if acceleration_valide:
            derniere_acceleration_valide = acceleration_ms2
        else:
            print(
                f"Accélération rejetée à {temps_s:.2f} s : "
                f"{acceleration_ms2:.2f} m/s²"
            )

        acceleration_utilisee = derniere_acceleration_valide
        acceleration_resultat.append(acceleration_utilisee)

        # 3. Validation de la vitesse
        vitesse_valide = 0.0 <= vitesse_kmh <= VITESSE_MAX_KMH

        if vitesse_valide:
            derniere_vitesse_valide = vitesse_kmh
        else:
            print(
                f"Vitesse rejetée à {temps_s:.2f} s : "
                f"{vitesse_kmh:.2f} km/h"
            )

        vitesse_utilisee = derniere_vitesse_valide
        vitesse_resultat.append(vitesse_utilisee)

        if not vitesse_valide:
            # La lecture invalide n'est pas utilisée pour recalculer
            # la puissance. La dernière puissance reste affichée.
            puissance_resultat.append(derniere_puissance_affichee)
            continue

        # 4. Calcul de la puissance signée à la roue
        vitesse_ms = puissance_estimee.kmh_vers_ms(vitesse_utilisee)
        pitch_rad = puissance_estimee.degres_vers_radians(dernier_pitch_valide)

        mesures = puissance_estimee.creer_mesures(
            vitesse_sol_ms=vitesse_ms,
            pitch_rad=pitch_rad,
            acceleration_ms2=acceleration_utilisee,
        )
        composantes = puissance_estimee.estimer_puissance(mesures)
        puissance_roue_signee = composantes.total_roue_w

        # 5. Lissage signé, puis limitation à zéro
        puissance_roue_lissee = moyenne_puissance.ajouter(puissance_roue_signee)

        if puissance_roue_lissee <= 2.0:
            puissance_roue_positive = 0.0
        else:
            puissance_roue_positive = puissance_roue_lissee

        puissance_pedalier = puissance_estimee.puissance_pedalier(
            puissance_roue_positive
        )

        derniere_puissance_affichee = puissance_pedalier
        puissance_resultat.append(puissance_pedalier)

    return (
        vitesse_resultat,
        pitch_resultat,
        acceleration_resultat,
        puissance_resultat,
    )


def tracer_course(
    df,
    vitesse,
    pitch,
    acceleration,
    puissance,
    titre="Course",
    afficher_comparaison=False,
):
    fig, axes = plt.subplots(5, 1, figsize=(12, 13), sharex=True)
    fig.suptitle(titre, fontsize=14)

    t = df["duree_s"] / 60.0

    # Vitesse
    if afficher_comparaison:
        axes[0].plot(
            t,
            df["vitesse_kmh"],
            color="black",
            linestyle="--",
            linewidth=1.2,
            alpha=0.8,
            label="Vitesse injectée",
        )

    axes[0].plot(
        t,
        vitesse,
        color="tab:blue",
        linewidth=1.2,
        label="Vitesse utilisée" if afficher_comparaison else "Vitesse",
    )
    axes[0].set_ylabel("Vitesse\n(km/h)")
    axes[0].grid(True, alpha=0.3)

    if afficher_comparaison:
        axes[0].legend(loc="upper right", fontsize=8)

    # Puissance
    axes[1].plot(
        t,
        puissance,
        color="tab:red",
        label="Puissance recalculée",
    )
    axes[1].plot(
        t,
        df["puissance_cible_w"],
        color="tab:orange",
        linestyle="--",
        label="Puissance cible",
    )
    axes[1].set_ylabel("Puissance\n(W)")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].grid(True, alpha=0.3)

    # Pitch
    if afficher_comparaison:
        axes[2].plot(
            t,
            df["pitch_deg"],
            color="black",
            linestyle="--",
            linewidth=1.2,
            alpha=0.8,
            label="Pitch injecté",
        )

    axes[2].plot(
        t,
        pitch,
        color="tab:green",
        linewidth=1.2,
        label="Pitch filtré" if afficher_comparaison else "Pitch",
    )
    axes[2].axhline(0, color="gray", linewidth=0.8)
    axes[2].set_ylabel("Pitch\n(deg)")
    axes[2].grid(True, alpha=0.3)

    if afficher_comparaison:
        axes[2].legend(loc="upper right", fontsize=8)

    # Accélération
    if afficher_comparaison:
        axes[3].plot(
            t,
            df["acceleration_ms2"],
            color="black",
            linestyle="--",
            linewidth=1.2,
            alpha=0.8,
            label="Accélération injectée",
        )

    axes[3].plot(
        t,
        acceleration,
        color="tab:brown",
        linewidth=1.2,
        label="Accélération utilisée" if afficher_comparaison else "Accélération",
    )
    axes[3].axhline(0, color="gray", linewidth=0.8)
    axes[3].set_ylabel("Accélération\n(m/s²)")
    axes[3].grid(True, alpha=0.3)

    if afficher_comparaison:
        axes[3].legend(loc="upper right", fontsize=8)

    # Distance
    axes[4].plot(t, df["distance_km"], color="tab:purple")
    axes[4].set_ylabel("Distance\n(km)")
    axes[4].set_xlabel("Temps (minutes)")
    axes[4].grid(True, alpha=0.3)

    fig.tight_layout()
    return fig


def resume_texte(df, puissance):
    duree_h = df["duree_s"].iloc[-1] / 3600.0
    distance = df["distance_km"].iloc[-1]
    vitesse_moy = distance / duree_h if duree_h > 0 else 0.0
    puissance_moy = pd.Series(puissance).loc[lambda s: s > 0].mean()

    print(f"Duree            : {duree_h * 60:.1f} min")
    print(f"Distance         : {distance:.2f} km")
    print(f"Vitesse moyenne  : {vitesse_moy:.1f} km/h")
    print(f"Puissance moyenne (hors 0 W) : {puissance_moy:.0f} W")


def main():
    if len(sys.argv) < 2:
        print("Usage : python plot_course.py course.csv [--recalculer]")
        sys.exit(1)

    chemin_csv = sys.argv[1]
    recalculer = "--recalculer" in sys.argv or "-recalculer" in sys.argv
    df = charger_course(chemin_csv)

    if recalculer:
        print("Mode : recalcul de la puissance")
        vitesse, pitch, acceleration, puissance = lisser_course(df)
    else:
        print("Mode : données originales du CSV")
        vitesse = df["vitesse_kmh"].tolist()
        pitch = df["pitch_deg"].tolist()
        acceleration = df["acceleration_ms2"].tolist()
        puissance = df["puissance_w"].tolist()

    resume_texte(df, puissance)

    nom_base = os.path.splitext(os.path.basename(chemin_csv))[0]
    fig = tracer_course(
        df=df,
        vitesse=vitesse,
        pitch=pitch,
        acceleration=acceleration,
        puissance=puissance,
        titre=nom_base,
        afficher_comparaison=recalculer,
    )

    suffixe = "_recalcule" if recalculer else "_original"
    chemin_png = os.path.join(
        os.path.dirname(chemin_csv),
        nom_base + suffixe + ".png",
    )

    fig.savefig(chemin_png, dpi=150)
    print(f"\nGraphique sauvegardé : {chemin_png}")

    plt.show()


if __name__ == "__main__":
    main()
