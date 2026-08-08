import math
import time
import threading
import serial

from adafruit_bno08x.uart import BNO08X_UART
from adafruit_bno08x import BNO_REPORT_GAME_ROTATION_VECTOR


def _quat_to_euler_deg(i, j, k, real):
    """
    Convertit un quaternion BNO085 (I, J, K, Real)
    en yaw, pitch et roll, en degrés.
    """
    sinr_cosp = 2.0 * (real * i + j * k)
    cosr_cosp = 1.0 - 2.0 * (i * i + j * j)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (real * j - k * i)

    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2.0, sinp)
    else:
        pitch = math.asin(sinp)

    siny_cosp = 2.0 * (real * k + i * j)
    cosy_cosp = 1.0 - 2.0 * (j * j + k * k)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return (
        math.degrees(yaw),
        math.degrees(pitch),
        math.degrees(roll),
    )


class CapteurIMU:
    def __init__(
        self,
        port="/dev/serial0",
        baud=3_000_000,
        intervalle_lecture=0.5,
    ):
        """
        port:
            Port série du BNO085.

        baud:
            Vitesse de communication UART régulière.

        intervalle_lecture:
            Délai entre deux mises à jour de l'orientation,
            en secondes.
        """
        self.port = port
        self.baud = baud
        self.intervalle_lecture = intervalle_lecture

        self._uart = None
        self._bno = None

        self._lock = threading.Lock()
        self._thread_lecture = None

        self._en_marche = False
        self._initialise = False

        # Dernière orientation valide mise en cache.
        self._yaw = 0.0
        self._pitch = 0.0
        self._roll = 0.0

        # Surveillance de la communication.
        self._temps_derniere_lecture = None
        self._derniere_erreur = None
        self._nb_erreurs_consecutives = 0
        self._derniere_erreur_observee = None

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def init(self):
        """
        Ouvre le port série, initialise le BNO085, active le vecteur
        de rotation et démarre le thread de lecture.
        """
        if self._initialise:
            return

        self._uart = serial.Serial(
            self.port,
            baudrate=self.baud,
            timeout=1,
        )

        self._bno = BNO08X_UART(self._uart)

        # Seul rapport nécessaire pour obtenir le pitch.
        self._bno.enable_feature(
            BNO_REPORT_GAME_ROTATION_VECTOR
        )

        # Laisse au BNO085 le temps d'activer le rapport.
        time.sleep(0.2)

        self._en_marche = True

        self._thread_lecture = threading.Thread(
            target=self._boucle_lecture,
            daemon=True,
        )
        self._thread_lecture.start()

        self._initialise = True

    def cleanup(self):
        """Arrête le thread de lecture et ferme le port série."""
        self._en_marche = False

        if self._thread_lecture is not None:
            self._thread_lecture.join(
                timeout=self.intervalle_lecture + 1.0
            )
            self._thread_lecture = None

        if self._uart is not None:
            self._uart.close()
            self._uart = None

        self._bno = None
        self._initialise = False

    # ------------------------------------------------------------------
    # Lecture des valeurs
    # ------------------------------------------------------------------

    def get_orientation(self):
        """
        Retourne (yaw, pitch, roll) en degrés.

        L'orientation provient du GAME_ROTATION_VECTOR. Celui-ci
        n'utilise pas le magnétomètre. Le yaw peut donc dériver avec
        le temps, mais le pitch demeure adapté à la mesure de pente.
        """
        with self._lock:
            return self._yaw, self._pitch, self._roll

    def donnees_valides(self, age_max_s=1.5):
        """
        Retourne True si une orientation valide a été reçue récemment.

        Avec une lecture toutes les 0,5 seconde, une limite de
        1,5 seconde tolère quelques lectures manquées avant de
        déclarer les données invalides.
        """
        with self._lock:
            if self._temps_derniere_lecture is None:
                return False

            age_s = (
                time.monotonic()
                - self._temps_derniere_lecture
            )

            return age_s <= age_max_s

    def get_age_derniere_lecture(self):
        """
        Retourne l'âge de la dernière orientation valide en secondes.

        Retourne None si aucune lecture valide n'a encore été reçue.
        """
        with self._lock:
            if self._temps_derniere_lecture is None:
                return None

            return (
                time.monotonic()
                - self._temps_derniere_lecture
            )

    def get_derniere_erreur(self):
        """Retourne le dernier message d'erreur, ou None."""
        with self._lock:
            return self._derniere_erreur

    def get_nb_erreurs_consecutives(self):
        """Retourne le nombre d'erreurs de lecture consécutives."""
        with self._lock:
            return self._nb_erreurs_consecutives

    # ------------------------------------------------------------------
    # Thread de lecture
    # ------------------------------------------------------------------

    def _boucle_lecture(self):
        while self._en_marche:
            try:
                game_quat = self._bno.game_quaternion

                if game_quat is None:
                    raise RuntimeError(
                        "Aucun quaternion reçu du BNO085"
                    )

                if len(game_quat) != 4:
                    raise RuntimeError(
                        "Quaternion BNO085 incomplet"
                    )

                if any(
                    valeur is None
                    or not math.isfinite(valeur)
                    for valeur in game_quat
                ):
                    raise RuntimeError(
                        "Quaternion BNO085 invalide"
                    )

                yaw, pitch, roll = _quat_to_euler_deg(
                    *game_quat
                )

                if not all(
                    math.isfinite(valeur)
                    for valeur in (yaw, pitch, roll)
                ):
                    raise RuntimeError(
                        "Orientation BNO085 invalide"
                    )

                with self._lock:
                    self._yaw = yaw
                    self._pitch = pitch
                    self._roll = roll

                    self._temps_derniere_lecture = (
                        time.monotonic()
                    )

                    self._derniere_erreur = None
                    self._nb_erreurs_consecutives = 0

            except Exception as erreur:
                message = (
                    f"{type(erreur).__name__}: {erreur}"
                )

                with self._lock:
                    self._derniere_erreur = message
                    self._derniere_erreur_observee = message
                    self._nb_erreurs_consecutives += 1
                    nombre_erreurs = (
                        self._nb_erreurs_consecutives
                    )

                print(
                    "Erreur de communication BNO085 "
                    f"({nombre_erreurs}) : {message}"
                )

            time.sleep(self.intervalle_lecture)
    def get_derniere_erreur_observee(self):
        with self._lock:
            return self._derniere_erreur_observee