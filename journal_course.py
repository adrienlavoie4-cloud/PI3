import csv
import os
import time
from datetime import datetime, timezone


class JournalCourse:
    def __init__(self, dossier="courses"):
        self.dossier = dossier
        self._fichier = None
        self._writer = None
        self._t_debut = None

    def demarrer(self):
        os.makedirs(self.dossier, exist_ok=True)
        nom = datetime.now().strftime("course_%Y-%m-%d_%H-%M-%S.csv")
        chemin = os.path.join(self.dossier, nom)

        self._fichier = open(chemin, mode="w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._fichier)
        self._writer.writerow([
            "timestamp_iso", "timestamp_unix", "duree_s",
            "vitesse_kmh", "distance_km", "pitch_deg",
            "acceleration_ms2", "puissance_w", "puissance_cible_w",
        ])
        self._t_debut = time.time()
        return chemin

    def ajouter_echantillon(self, vitesse, distance, pitch, accel, puissance, cible):
        if self._writer is None:
            return
        maintenant = time.time()
        self._writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            f"{maintenant:.3f}",
            f"{maintenant - self._t_debut:.2f}",
            f"{vitesse:.2f}",
            f"{distance:.4f}",
            f"{pitch:.2f}",
            f"{accel:.3f}",
            f"{puissance:.1f}",
            f"{cible:.1f}",
        ])

    def arreter(self):
        if self._fichier is not None:
            self._fichier.close()
        self._fichier = None
        self._writer = None