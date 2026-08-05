import math
import time
import threading
import serial
from adafruit_bno08x.uart import BNO08X_UART
from adafruit_bno08x import (
    BNO_REPORT_ACCELEROMETER,
    BNO_REPORT_GYROSCOPE,
    BNO_REPORT_MAGNETOMETER,
    BNO_REPORT_ROTATION_VECTOR,
    BNO_REPORT_LINEAR_ACCELERATION,
    BNO_REPORT_GRAVITY,
    BNO_REPORT_GAME_ROTATION_VECTOR,
    BNO_REPORT_GEOMAGNETIC_ROTATION_VECTOR,
    BNO_REPORT_STEP_COUNTER,
)


def _quat_to_euler_deg(i, j, k, real):
    """Convertit un quaternion BNO085 (I, J, K, Real) en yaw/pitch/roll (degres)."""
    sinr_cosp = 2 * (real * i + j * k)
    cosr_cosp = 1 - 2 * (i * i + j * j)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2 * (real * j - k * i)
    pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)

    siny_cosp = 2 * (real * k + i * j)
    cosy_cosp = 1 - 2 * (j * j + k * k)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(yaw), math.degrees(pitch), math.degrees(roll)


class CapteurIMU:
    def __init__(self, port="/dev/serial0", baud=3_000_000, intervalle_lecture=0.5):
        """
        port: port serie du BNO085 ("/dev/serial0", ou "/dev/ttyAMA0" si
              le Bluetooth occupe serial0)
        baud: vitesse de communication UART
        intervalle_lecture: delai entre deux lectures du capteur, en secondes
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

        self._derniere_erreur = None

        # Valeurs mises en cache (protegees par _lock)
        self._yaw = 0.0
        self._pitch = 0.0
        self._roll = 0.0
        self._game_yaw = 0.0
        self._game_pitch = 0.0
        self._game_roll = 0.0
        self._accel = (0.0, 0.0, 0.0)
        self._gyro = (0.0, 0.0, 0.0)
        self._mag = (0.0, 0.0, 0.0)
        self._linear = (0.0, 0.0, 0.0)
        self._gravity = (0.0, 0.0, 0.0)
        self._steps = 0
        self._temps_derniere_lecture = None

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    def init(self):
        """Ouvre le port serie, connecte le BNO085, active les capteurs
        et demarre le thread de lecture."""
        if self._initialise:
            return

        self._uart = serial.Serial(self.port, baudrate=self.baud, timeout=1)
        self._bno = BNO08X_UART(self._uart)

        for feature in (
            BNO_REPORT_ACCELEROMETER,
            BNO_REPORT_GYROSCOPE,
            BNO_REPORT_MAGNETOMETER,
            BNO_REPORT_ROTATION_VECTOR,
            BNO_REPORT_LINEAR_ACCELERATION,
            BNO_REPORT_GRAVITY,
            BNO_REPORT_GAME_ROTATION_VECTOR,
            BNO_REPORT_GEOMAGNETIC_ROTATION_VECTOR,
            BNO_REPORT_STEP_COUNTER,
        ):
            self._bno.enable_feature(feature)
        time.sleep(0.2)

        self._en_marche = True
        self._thread_lecture = threading.Thread(
            target=self._boucle_lecture, daemon=True
        )
        self._thread_lecture.start()

        self._initialise = True

    def cleanup(self):
        """Arrete le thread de lecture et ferme le port serie."""
        self._en_marche = False
        if self._thread_lecture is not None:
            self._thread_lecture.join(timeout=self.intervalle_lecture + 1.0)
        if self._uart is not None:
            self._uart.close()
        self._initialise = False

    # ------------------------------------------------------------------
    # Lecture des valeurs (thread-safe)
    # ------------------------------------------------------------------
    def get_orientation(self):
        """Retourne (yaw, pitch, roll) en degres, orientation fusionnee
        (utilise le magnetometre, plus precise mais plus sensible aux
        perturbations magnetiques)."""
        with self._lock:
            return self._yaw, self._pitch, self._roll

    def get_orientation_jeu(self):
        """Retourne (yaw, pitch, roll) en degres, orientation "game"
        (n'utilise pas le magnetometre, plus stable mais le yaw derive
        lentement dans le temps)."""
        with self._lock:
            return self._game_yaw, self._game_pitch, self._game_roll

    def get_acceleration(self):
        """Retourne (x, y, z) en m/s^2, acceleration brute (inclut la gravite)."""
        with self._lock:
            return self._accel

    def get_gyro(self):
        """Retourne (x, y, z) en rad/s, vitesse angulaire."""
        with self._lock:
            return self._gyro

    def get_magnetique(self):
        """Retourne (x, y, z) en µT, champ magnetique."""
        with self._lock:
            return self._mag

    def get_acceleration_lineaire(self):
        with self._lock:
            if self._temps_derniere_lecture is None:
                return (0.0, 0.0, 0.0), False

            age = time.monotonic() - self._temps_derniere_lecture
            valide = age < 1.5

            return self._linear, valide

    def get_gravite(self):
        """Retourne (x, y, z) en m/s^2, vecteur de gravite seul."""
        with self._lock:
            return self._gravity

    def get_pas(self):
        """Retourne le nombre de pas compte par le capteur."""
        with self._lock:
            return self._steps

    def get_derniere_erreur(self):
        """Retourne le dernier message d'erreur de lecture (ou None)."""
        with self._lock:
            return self._derniere_erreur

    # ------------------------------------------------------------------
    # Thread de lecture
    # ------------------------------------------------------------------
    def _boucle_lecture(self):
        while self._en_marche:
            try:
                accel = self._bno.acceleration
                gyro = self._bno.gyro
                mag = self._bno.magnetic
                quat = self._bno.quaternion
                game_quat = self._bno.game_quaternion
                linear = self._bno.linear_acceleration
                gravity = self._bno.gravity
                steps = self._bno.steps

                yaw, pitch, roll = _quat_to_euler_deg(*quat)
                game_yaw, game_pitch, game_roll = _quat_to_euler_deg(*game_quat)

                with self._lock:
                    self._accel = accel
                    self._gyro = gyro
                    self._mag = mag
                    self._linear = linear
                    self._gravity = gravity
                    self._steps = steps
                    self._yaw, self._pitch, self._roll = yaw, pitch, roll
                    self._game_yaw = game_yaw
                    self._game_pitch = game_pitch
                    self._game_roll = game_roll
                    self._derniere_erreur = None

            except Exception as e:
                with self._lock:
                    self._derniere_erreur = str(e)

            time.sleep(self.intervalle_lecture)