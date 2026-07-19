"""
Exemple KIVY : jauge circulaire de puissance cycliste
Version separee : main.py (logique) + power.kv (interface/style)

Kivy charge power.kv AUTOMATIQUEMENT car il porte le meme nom que
la classe App, en minuscules et sans le suffixe "App" :
    PowerApp  ->  power.kv
Les deux fichiers doivent etre dans le meme dossier.
"""

import time
from math import cos, sin, radians


from capteur_vitesse import CapteurVitesse
from capteur_imu import CapteurIMU
import puissance_estimee
import puissance_cible

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


capteur_vitesse = CapteurVitesse(pin=4)
capteur_vitesse.init() 
capteur_imu = CapteurIMU()
capteur_imu.init()
class PowerGauge(Widget):
    # NumericProperty permet au fichier .kv de "observer" cette valeur
    # et de se mettre a jour automatiquement quand elle change.
    current_power = NumericProperty(0)
    target_power = NumericProperty(TARGET_POWER)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self.redraw, pos=self.redraw, current_power=self.redraw, target_power=self.redraw)


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

        
    duree_str = StringProperty("00:00")

    is_running = BooleanProperty(False)
    debug_mode = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_time = time.time()

        self._somme_puissance = 0.0    #données a accumuler pour le resume de performance
        self._nb_echantillons_puissance = 0
        self._elevation_totale_m = 0.0

        Clock.schedule_interval(self.update_distance, 0.5)
        Clock.schedule_interval(self.update_vitesse, 0.5)
        Clock.schedule_interval(self.update_duree, 0.5)
        Clock.schedule_interval(self.update_orientation, 0.5)
        Clock.schedule_interval(self.update_acceleration_lin, 0.5)
        Clock.schedule_interval(self.update_puissance, 0.5)
        Clock.schedule_interval(self.update_target_power, 0.5)



    def update_distance(self, dt):
        self.distance_parcourue = capteur_vitesse.get_odometre()

    def update_vitesse(self, dt):
        if self.debug_mode:
            self.vitesse=self.vitesse_manuelle
        else:
            if self.is_running:
                self.vitesse = capteur_vitesse.get_vitesse()
            else:
                self.vitesse = 0
    def update_orientation(self,dt):
        if self.debug_mode:
            self.pitch_deg=self.pitch_deg_manuelle
        else:
            if self.is_running:
                (yaw, pitch, roll)=capteur_imu.get_orientation()
                self.pitch_deg = pitch 
            else:
                self.pitch_deg = 0
    
    def update_acceleration_lin(self,dt):
        if self.debug_mode:
            self.acceleration_lin=self.acceleration_lin_manuelle
        else:
            if self.is_running:
                (x,y,z)=capteur_imu.get_acceleration_lineaire()
                self.acceleration_lin=x #TODO: confirmer l'axe une fois le capteur monté sur le vélo
            else:
                self.acceleration_lin=0

    def update_duree(self, dt):
        if self.is_running:
            self.duree_session += dt
            minutes = int(self.duree_session) // 60
            secondes = int(self.duree_session) % 60
            self.duree_str = f"{minutes:02d}:{secondes:02d}"


    def update_puissance(self, dt):
        if self.is_running or self.debug_mode:
            pitch_rad = puissance_estimee.degres_vers_radians(self.pitch_deg)
            vitesse_ms = puissance_estimee.kmh_vers_ms(self.vitesse)
            mesures_lues = puissance_estimee.creer_mesures(vitesse_ms, pitch_rad, self.acceleration_lin)
            composantes_puissance = puissance_estimee.estimer_puissance(mesures_lues)

            puissance_roue_clampee = puissance_estimee.puissance_cycliste_w(composantes_puissance)
            puissance_totale_est = puissance_estimee.puissance_pedalier(puissance_roue_clampee)
            self.ids.gauge.current_power = puissance_totale_est

            if self.is_running:  # only accumulate real ride data, not debug taps
                self._somme_puissance += puissance_totale_est
                self._nb_echantillons_puissance += 1

                delta_elevation_m = vitesse_ms * sin(pitch_rad) * dt
                if delta_elevation_m > 0:  # ne compte que la montée (élévation cumulative)
                    self._elevation_totale_m += delta_elevation_m

    def update_target_power(self, dt):
        if self.is_running:
            cible = puissance_cible.puissance_cible(self.pitch_deg)
            App.get_running_app().target_power = cible

    def demarrer_session(self):
        self._somme_puissance = 0.0
        self._nb_echantillons_puissance = 0
        self._elevation_totale_m = 0.0
        self.duree_session = 0.0
        self.duree_str = "00:00"
        capteur_vitesse.reset_odometre()

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

if __name__ == "__main__":
    PowerApp().run()
