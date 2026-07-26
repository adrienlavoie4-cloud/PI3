import sys
import os

import pandas as pd
import matplotlib.pyplot as plt


def charger_course(chemin_csv):
    df = pd.read_csv(chemin_csv, parse_dates=["timestamp_iso"])
    return df


def tracer_course(df, titre="Course"):
    fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
    fig.suptitle(titre, fontsize=14)

    t = df["duree_s"] / 60.0  # minutes, plus lisible qu'en secondes

    # Vitesse
    axes[0].plot(t, df["vitesse_kmh"], color="tab:blue")
    axes[0].set_ylabel("Vitesse (km/h)")
    axes[0].grid(True, alpha=0.3)

    # Puissance : reelle vs cible
    axes[1].plot(t, df["puissance_w"], color="tab:red", label="Puissance estimee")
    axes[1].plot(t, df["puissance_cible_w"], color="tab:orange", linestyle="--", label="Puissance cible")
    axes[1].set_ylabel("Puissance (W)")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].grid(True, alpha=0.3)

    # Pitch (pente)
    axes[2].plot(t, df["pitch_deg"], color="tab:green")
    axes[2].axhline(0, color="gray", linewidth=0.8)
    axes[2].set_ylabel("Pitch (deg)")
    axes[2].grid(True, alpha=0.3)

    # Distance cumulee
    axes[3].plot(t, df["distance_km"], color="tab:purple")
    axes[3].set_ylabel("Distance (km)")
    axes[3].set_xlabel("Temps (minutes)")
    axes[3].grid(True, alpha=0.3)

    fig.tight_layout()
    return fig


def resume_texte(df):
    duree_h = df["duree_s"].iloc[-1] / 3600.0
    distance = df["distance_km"].iloc[-1]
    vitesse_moy = distance / duree_h if duree_h > 0 else 0.0
    puissance_moy = df.loc[df["puissance_w"] > 0, "puissance_w"].mean()

    print(f"Duree            : {duree_h * 60:.1f} min")
    print(f"Distance         : {distance:.2f} km")
    print(f"Vitesse moyenne  : {vitesse_moy:.1f} km/h")
    print(f"Puissance moyenne (hors 0 W) : {puissance_moy:.0f} W")


def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_course.py chemin/vers/course_XXXX.csv")
        sys.exit(1)

    chemin_csv = sys.argv[1]
    df = charger_course(chemin_csv)

    resume_texte(df)

    nom_base = os.path.splitext(os.path.basename(chemin_csv))[0]
    fig = tracer_course(df, titre=nom_base)

    chemin_png = os.path.join(os.path.dirname(chemin_csv), nom_base + ".png")
    fig.savefig(chemin_png, dpi=150)
    print(f"\nGraphique sauvegarde : {chemin_png}")

    plt.show()



if __name__ == "__main__":
    main()