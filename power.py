import time
from collections import deque
from math import cos, sin, radians
from statistics import median

from capteur_vitesse import CapteurVitesse
from capteur_imu import CapteurIMU
import puissance_estimee
import puissance_cible
from journal_course import JournalCourse

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Line
from kivy.clock import Clock
from kivy.uix.slider import Slider
from kivy.properties import NumericProperty, BooleanProperty, StringProperty
from kivy.uix.screenmanager import ScreenManager, Screen


TARGET_POWER = 220   # puissance cible a suivre (W)
MAX_POWER = 400      # echelle max de la jauge (W)


# taille_moyenne_mobile ajustée pour avoir une courbe plus lisse mais avec moins de latence
capteur_vitesse = CapteurVitesse(pin=4, taille_moyenne_mobile=6)
capteur_vitesse.init()
# intervalle_lecture ajusté pour avoir une courbe plus lisse mais avec moins de latence
capteur_imu = CapteurIMU(intervalle_lecture=0.2)
capteur_imu.init()


class PowerGauge(Widget):
    # NumericProperty permet au fichier .kv de "observer" cette valeur
    # et de se mettre a jour automatiquement quand elle change.
    current_power = NumericProperty(0)
    target_power = NumericProperty(TARGET_POWER)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            size=self.redraw,
            pos=self.redraw,
            current_power=self.redraw,
            target_power=self.redraw,
        )

    def redraw(self, *args):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        radius = min(self.width, self.height) / 2 - 20

        with self.canvas:
            # Anneau de fond
            Color(0.2, 0.2, 0.2, 1)
            Line(circle=(cx, cy, radius), width=8)

            # Couleur selon l'ecart avec la cible
            diff = self.current_power - self.target_power
            if abs(diff) <= 15:
                Color(0.2, 0.8, 0.3, 1)   # vert : dans la zone cible
            elif diff > 15:
                Color(0.9, 0.2, 0.2, 1)   # rouge : trop de puissance
            else:
                Color(0.9, 0.7, 0.1, 1)   # jaune : pas assez

            # Arc proportionnel a la puissance actuelle
            sweep = (self.current_power / MAX_POWER) * 360
            angle_start = 90 - sweep
            angle_end = 90
            Line(circle=(cx, cy, radius, angle_start, angle_end), width=8, cap='round')

            # Marqueur de la cible (petit trait blanc)
            target_angle = radians(90 - (self.target_power / MAX_POWER) * 360)
            x1 = cx + (radius - 15) * cos(target_angle)
            y1 = cy + (radius - 15) * sin(target_angle)
            x2 = cx + (radius + 15) * cos(target_angle)
            y2 = cy + (radius + 15) * sin(target_angle)
            Color(1, 1, 1, 1)
            Line(points=[x1, y1, x2, y2], width=3)


class Dashboard(BoxLayout):
    duree_session = NumericProperty(0)
    distance_parcourue = NumericProperty(0)
    vitesse = NumericProperty(0)
    pitch_deg = NumericProperty(0)
    acceleration_lin = NumericProperty(0)

    vitesse_manuelle = NumericProperty(0)
    pitch_deg_manuelle = NumericProperty(0)
    acceleration_lin_manuelle = NumericProperty(0)
    pitch_offset_deg = NumericProperty(0)
    calibration_en_cours = BooleanProperty(False)

    duree_str = StringProperty("00:00")
    is_running = BooleanProperty(False)
    debug_mode = BooleanProperty(False)

    def calibrer_pitch(self, duree_s=5.0, dt_echantillon=0.5):
        """
        Calcule l'offset du pitch.

        Le vélo doit être immobile et placé sur une surface
        horizontale pendant toute la calibration.
        """
        self.calibration_en_cours = True
        self._echantillons_calib = []

        def _capter(dt):
            if not capteur_imu.donnees_valides():
                erreur = capteur_imu.get_derniere_erreur()
                print(
                    "Orientation BNO085 indisponible "
                    f"pendant la calibration : {erreur}"
                )
                return

            _, pitch, _ = capteur_imu.get_orientation()
            self._echantillons_calib.append(pitch)

        def _terminer_calib(dt):
            event_capture.cancel()

            # Une calibration de 5 secondes devrait normalement
            # fournir environ 10 échantillons. On en exige 8 afin
            # de tolérer quelques lectures manquées.
            nombre_minimum_echantillons = 8

            if len(self._echantillons_calib) >= nombre_minimum_echantillons:
                self.pitch_offset_deg = (
                    sum(self._echantillons_calib)
                    / len(self._echantillons_calib)
                )
                print(
                    "Calibration terminée : "
                    f"{self.pitch_offset_deg:.2f}°, "
                    f"{len(self._echantillons_calib)} échantillons"
                )
            else:
                print(
                    "Calibration échouée : seulement "
                    f"{len(self._echantillons_calib)} échantillons valides"
                )

            self.calibration_en_cours = False

        event_capture = Clock.schedule_interval(_capter, dt_echantillon)
        Clock.schedule_once(_terminer_calib, duree_s)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_time = time.time()

        self.journal = JournalCourse()

        # Données à accumuler pour le résumé de performance
        self._somme_puissance = 0.0
        self._nb_echantillons_puissance = 0
        self._elevation_totale_m = 0.0
        self._moyenne_mobile_puissance = puissance_estimee.MoyenneMobile(fenetre=25)
        self._moyenne_mobile_pitch = puissance_estimee.MoyenneMobile(fenetre=15)

        # Historique utilisé pour calculer l'accélération à partir de la vitesse Hall
        self._historique_vitesse_acceleration = deque(maxlen=11)
        self._derniere_acceleration_hall = 0.0
        self._temps_dernier_avertissement_imu = 0.0

        self._historique_pitch_median = deque(maxlen=5)
        self._dernier_pitch_filtre = None
        self._temps_dernier_pitch_filtre = None

        Clock.schedule_interval(self.update_distance, 0.5)
        Clock.schedule_interval(self.update_vitesse, 0.2)
        Clock.schedule_interval(self.update_duree, 0.5)
        Clock.schedule_interval(self.update_orientation, 0.2)
        Clock.schedule_interval(self.update_puissance, 0.2)
        Clock.schedule_interval(self.update_target_power, 0.5)

    def calculer_acceleration_hall(self, vitesse_ms: float) -> float:
        """
        L'accélération est calculée sur environ deux secondes,
        car la fenêtre contient 11 mesures obtenues toutes les
        0,2 seconde.
        """
        temps_actuel = time.monotonic()
        self._historique_vitesse_acceleration.append((temps_actuel, vitesse_ms))

        # Il faut au moins deux mesures pour calculer une dérivée
        if len(self._historique_vitesse_acceleration) < 2:
            self._derniere_acceleration_hall = 0.0
            return 0.0

        temps_initial, vitesse_initiale = self._historique_vitesse_acceleration[0]
        delta_t_s = temps_actuel - temps_initial

        acceleration = puissance_estimee.acceleration_par_difference_finie(
            vitesse_finale_ms=vitesse_ms,
            vitesse_initiale_ms=vitesse_initiale,
            delta_t_s=delta_t_s,
        )

        # Rejet d'une accélération manifestement irréaliste.
        # Une valeur aberrante peut notamment être causée par le watchdog
        # du capteur Hall lorsqu'il fait passer la vitesse directement à zéro.
        acceleration_max_ms2 = 3.0

        if abs(acceleration) > acceleration_max_ms2:
            return self._derniere_acceleration_hall

        # Petite zone morte pour éviter les variations de puissance
        # lorsque la vitesse est presque constante
        if abs(acceleration) < 0.05:
            acceleration = 0.0

        self._derniere_acceleration_hall = acceleration
        return acceleration

    def update_distance(self, dt):
        self.distance_parcourue = capteur_vitesse.get_odometre()

    def update_vitesse(self, dt):
        if self.debug_mode:
            self.vitesse = self.vitesse_manuelle
        elif self.is_running:
            self.vitesse = capteur_vitesse.get_vitesse()
        else:
            self.vitesse = 0

    def update_orientation(self, dt):
        if not self.is_running and not self.debug_mode:
            self.pitch_deg = 0.0
            return

        if self.debug_mode:
            pitch_brut = self.pitch_deg_manuelle
        else:
            if not capteur_imu.donnees_valides():
                maintenant = time.monotonic()

                if maintenant - self._temps_dernier_avertissement_imu >= 2.0:
                    erreur = capteur_imu.get_derniere_erreur()
                    age = capteur_imu.get_age_derniere_lecture()
                    print(
                        "Orientation BNO085 indisponible : "
                        f"âge={age}, erreur={erreur}"
                    )
                    self._temps_dernier_avertissement_imu = maintenant

                # Ne pas ajouter l'ancienne orientation au filtre
                return

            _, pitch, _ = capteur_imu.get_orientation()
            pitch_brut = pitch - self.pitch_offset_deg

        # 1. Rejet des valeurs hors de la plage physique
        PITCH_MIN_DEG = -15.0
        PITCH_MAX_DEG = 15.0

        if not PITCH_MIN_DEG <= pitch_brut <= PITCH_MAX_DEG:
            print(f"Pitch rejeté, hors plage : {pitch_brut:.2f}°")
            return

        # 2. Filtre médian
        self._historique_pitch_median.append(pitch_brut)
        pitch_median = median(self._historique_pitch_median)

        # 3. Limitation de la vitesse de variation
        temps_actuel = time.monotonic()

        if self._dernier_pitch_filtre is None or self._temps_dernier_pitch_filtre is None:
            pitch_limite = pitch_median
        else:
            delta_t = temps_actuel - self._temps_dernier_pitch_filtre

            # Le pitch accepté peut varier au maximum de 3°/s
            vitesse_max_pitch_deg_s = 3.0
            variation_max_deg = vitesse_max_pitch_deg_s * delta_t
            variation_demandee = pitch_median - self._dernier_pitch_filtre
            variation_limitee = max(
                -variation_max_deg,
                min(variation_demandee, variation_max_deg),
            )
            pitch_limite = self._dernier_pitch_filtre + variation_limitee

        self._dernier_pitch_filtre = pitch_limite
        self._temps_dernier_pitch_filtre = temps_actuel

        # 4. Moyenne mobile finale
        self.pitch_deg = self._moyenne_mobile_pitch.ajouter(pitch_limite)

    def update_duree(self, dt):
        if self.is_running:
            self.duree_session += dt
            minutes = int(self.duree_session) // 60
            secondes = int(self.duree_session) % 60
            self.duree_str = f"{minutes:02d}:{secondes:02d}"

    def update_puissance(self, dt):
        if not (self.is_running or self.debug_mode):
            return

        if not self.debug_mode and not capteur_imu.donnees_valides():
            return

        # 1. Préparation des mesures
        pitch_rad = puissance_estimee.degres_vers_radians(self.pitch_deg)
        vitesse_ms = puissance_estimee.kmh_vers_ms(self.vitesse)

        if self.debug_mode:
            acceleration_ms2 = self.acceleration_lin_manuelle
        else:
            acceleration_ms2 = self.calculer_acceleration_hall(vitesse_ms)

        self.acceleration_lin = acceleration_ms2

        # 2. Validation des entrées
        vitesse_max_ms = puissance_estimee.kmh_vers_ms(60.0)
        pitch_max_rad = puissance_estimee.degres_vers_radians(25.0)
        acceleration_max_ms2 = 3.0

        mesures_valides = (
            0.0 <= vitesse_ms <= vitesse_max_ms
            and -pitch_max_rad <= pitch_rad <= pitch_max_rad
            and -acceleration_max_ms2 <= acceleration_ms2 <= acceleration_max_ms2
        )

        if not mesures_valides:
            # On ignore l'échantillon invalide et conserve la dernière puissance affichée
            return

        # 3. Calcul des composantes de puissance
        mesures_lues = puissance_estimee.creer_mesures(
            vitesse_sol_ms=vitesse_ms,
            pitch_rad=pitch_rad,
            acceleration_ms2=acceleration_ms2,
        )
        composantes_puissance = puissance_estimee.estimer_puissance(mesures_lues)

        # La puissance reste signée pendant le filtrage
        puissance_roue_signee = composantes_puissance.total_roue_w

        # 4. Lissage avant la limitation à zéro
        puissance_roue_lissee = self._moyenne_mobile_puissance.ajouter(
            puissance_roue_signee
        )

        # Deadband appliqué après le lissage
        deadband_w = 2.0

        if puissance_roue_lissee <= deadband_w:
            puissance_roue_positive = 0.0
        else:
            puissance_roue_positive = puissance_roue_lissee

        puissance_pedalier_w = puissance_estimee.puissance_pedalier(
            puissance_roue_positive
        )

        # 5. Mise à jour de l'affichage
        self.ids.gauge.current_power = puissance_pedalier_w

        # 6. Mise à jour des statistiques de la course
        if self.is_running:
            self._somme_puissance += puissance_pedalier_w
            self._nb_echantillons_puissance += 1

            delta_elevation_m = vitesse_ms * sin(pitch_rad) * dt

            # L'élévation cumulative compte uniquement les montées
            if delta_elevation_m > 0.0:
                self._elevation_totale_m += delta_elevation_m

        # 7. Enregistrement dans le journal
        self.journal.ajouter_echantillon(
            vitesse=self.vitesse,
            distance=self.distance_parcourue,
            pitch=self.pitch_deg,
            accel=acceleration_ms2,
            puissance=puissance_pedalier_w,
            cible=App.get_running_app().target_power,
        )

    def update_target_power(self, dt):
        if self.is_running:
            cible = puissance_cible.puissance_cible(self.pitch_deg)
            App.get_running_app().target_power = cible

    def demarrer_session(self):
        self._historique_vitesse_acceleration.clear()
        self._derniere_acceleration_hall = 0.0
        self.acceleration_lin = 0.0

        self._historique_pitch_median.clear()
        self._dernier_pitch_filtre = None
        self._temps_dernier_pitch_filtre = None

        self._somme_puissance = 0.0
        self._nb_echantillons_puissance = 0
        self._elevation_totale_m = 0.0
        self._moyenne_mobile_puissance.reinitialiser()
        self._moyenne_mobile_pitch.reinitialiser()
        self.duree_session = 0.0
        self.duree_str = "00:00"
        capteur_vitesse.reset_odometre()
        self.journal.demarrer()

    def terminer_session(self):
        duree_h = self.duree_session / 3600.0
        vitesse_moyenne = self.distance_parcourue / duree_h if duree_h > 0 else 0.0
        puissance_moyenne = (
            self._somme_puissance / self._nb_echantillons_puissance
            if self._nb_echantillons_puissance > 0 else 0.0
        )

        summary = App.get_running_app().root.get_screen("summary")
        summary.distance_finale = self.distance_parcourue
        summary.duree_finale = self.duree_str
        summary.vitesse_moyenne = vitesse_moyenne
        summary.puissance_moyenne = puissance_moyenne
        summary.elevation_totale = self._elevation_totale_m

        App.get_running_app().root.current = "summary"
        self.journal.arreter()

    def toggle_collection(self):
        if self.is_running:
            self.terminer_session()
        else:
            self.demarrer_session()
        self.is_running = not self.is_running

    def on_debug_mode(self, instance, value):
        self.ids.debug_switcher.current = 'debug' if value else 'normal'


class DashboardScreen(Screen):
    pass


class SummaryScreen(Screen):
    distance_finale = NumericProperty(0)
    duree_finale = StringProperty("00:00")
    vitesse_moyenne = NumericProperty(0)
    puissance_moyenne = NumericProperty(0)
    elevation_totale = NumericProperty(0)

    def nouvelle_course(self):
        app = App.get_running_app()
        app.dashboard.demarrer_session()
        app.dashboard.is_running = True
        self.manager.current = "dashboard"


class PowerApp(App):
    target_power = NumericProperty(TARGET_POWER)

    def build(self):
        self.dashboard = Dashboard()
        sm = ScreenManager()
        dash_screen = DashboardScreen(name="dashboard")
        dash_screen.add_widget(self.dashboard)
        sm.add_widget(dash_screen)
        sm.add_widget(SummaryScreen(name="summary"))
        return sm

    def on_stop(self):
        capteur_vitesse.cleanup()
        capteur_imu.cleanup()


if __name__ == "__main__":
    PowerApp().run()
