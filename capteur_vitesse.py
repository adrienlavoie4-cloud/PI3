import time
import threading
import RPi.GPIO as GPIO


class CapteurVitesse:
    def __init__(self, pin, diametre_roue=700, taille_moyenne_mobile=8):
        """
        pin: numero GPIO (mode BCM) ou est branche le capteur
        diametre_roue: diametre de la roue en mm
        taille_moyenne_mobile: nombre d'impulsions utilisees pour lisser
                                le calcul de vitesse
        """
        self.pin = pin
        self.circonference_roue = diametre_roue * 3.141592654  # mm

        self._taille_max = taille_moyenne_mobile
        self._historique_temps = [0.0] * (self._taille_max + 1)
        self._compte = 0

        # watchdog : nombre de "ticks" (appels a _watchdog_tick) avant
        # de considerer que la roue est arretee. A 100 ms/tick, 20 = ~2s.
        self._watchdog_ticks_restants = 0
        self._watchdog_ticks_avant_arret = 20

        self._vitesse = 0.0       # km/h
        self._odometre = 0.0      # km

        self._lock = threading.Lock()
        self._thread_watchdog = None
        self._en_marche = False

        self._initialise = False

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    def init(self):
        """Configure le GPIO, enregistre le callback et demarre le watchdog."""
        if self._initialise:
            return

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(
            self.pin, GPIO.FALLING, callback=self._got_pulse, bouncetime=100
        )

        self._en_marche = True
        self._thread_watchdog = threading.Thread(
            target=self._boucle_watchdog, daemon=True
        )
        self._thread_watchdog.start()

        self._initialise = True

    def cleanup(self):
        """Arrete le thread watchdog et libere le GPIO."""
        self._en_marche = False
        if self._thread_watchdog is not None:
            self._thread_watchdog.join(timeout=1.0)
        GPIO.remove_event_detect(self.pin)
        self._initialise = False

    # ------------------------------------------------------------------
    # Lecture des valeurs (thread-safe)
    # ------------------------------------------------------------------
    def get_vitesse(self):
        """Retourne la vitesse actuelle en km/h."""
        with self._lock:
            return self._vitesse

    def get_odometre(self):
        """Retourne la distance parcourue depuis le demarrage, en km."""
        with self._lock:
            return self._odometre

    def reset_odometre(self):
        """Remet l'odometre a zero (utile pour un trajet 'partiel')."""
        with self._lock:
            self._odometre = 0.0

    # ------------------------------------------------------------------
    # Callback GPIO (appele par RPi.GPIO dans son propre thread)
    # ------------------------------------------------------------------
    def _got_pulse(self, channel):
        ctime = time.monotonic()

        with self._lock:
            self._historique_temps[self._taille_max] = ctime

            delta_temps = ctime - self._historique_temps[
                self._taille_max - self._compte
            ]

            for i in range(self._taille_max):
                self._historique_temps[i] = self._historique_temps[i + 1]

            if delta_temps <= 0.0:
                vitesse_mm_s = 0.0
            else:
                vitesse_mm_s = self._compte * self.circonference_roue / delta_temps

            self._compte += 1
            if self._compte > self._taille_max:
                self._compte = self._taille_max

            self._vitesse = vitesse_mm_s * 3600.0 / 1_000_000.0  # mm/s -> km/h
            self._odometre += self.circonference_roue / 1_000_000.0  # mm -> km

            self._watchdog_ticks_restants = self._watchdog_ticks_avant_arret

    # ------------------------------------------------------------------
    # Watchdog ("plus d'impulsion depuis un moment" => vitesse = 0)
    # ------------------------------------------------------------------
    def _boucle_watchdog(self):
        while self._en_marche:
            with self._lock:
                if self._watchdog_ticks_restants > 0:
                    self._watchdog_ticks_restants -= 1
                elif self._vitesse != 0.0:
                    self._vitesse = 0.0
            time.sleep(0.1)