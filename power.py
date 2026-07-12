"""
Exemple KIVY : jauge circulaire de puissance cycliste
Version separee : main.py (logique) + power.kv (interface/style)

Kivy charge power.kv AUTOMATIQUEMENT car il porte le meme nom que
la classe App, en minuscules et sans le suffixe "App" :
    PowerApp  ->  power.kv
Les deux fichiers doivent etre dans le meme dossier.
"""
import random
import time
from math import cos, sin, radians

from capteur_vitesse import CapteurVitesse


from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Line
from kivy.clock import Clock
from kivy.properties import NumericProperty, BooleanProperty

TARGET_POWER = 220   # puissance cible a suivre (W)
MAX_POWER = 400      # echelle max de la jauge (W)


capteur_vitesse = CapteurVitesse(pin=4)
capteur_vitesse.init() 
class PowerGauge(Widget):
    # NumericProperty permet au fichier .kv de "observer" cette valeur
    # et de se mettre a jour automatiquement quand elle change.
    current_power = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self.redraw, pos=self.redraw, current_power=self.redraw)
        self._update_event = None  # reference vers l'evenement Clock (pour pouvoir l'arreter)

    def start_collection(self):
        """Demarre la collecte/affichage si ce n'est pas deja en cours."""
        if self._update_event is None:
            self._update_event = Clock.schedule_interval(self.update_power, 0.5)

    def stop_collection(self):
        """Arrete la collecte. La derniere valeur reste affichee (pause)."""
        if self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None

    def update_power(self, dt):
        # --- Simule une lecture capteur (a remplacer par ta vraie donnee) ---
        new_value = self.current_power + random.randint(-15, 15)
        self.current_power = max(0, min(new_value, MAX_POWER))

    def redraw(self, *args):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        radius = min(self.width, self.height) / 2 - 20

        with self.canvas:
            # Anneau de fond
            Color(0.2, 0.2, 0.2, 1)
            Line(circle=(cx, cy, radius), width=8)

            # Couleur selon l'ecart avec la cible
            diff = self.current_power - TARGET_POWER
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
            target_angle = radians(90 - (TARGET_POWER / MAX_POWER) * 360)
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
    is_running = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_time = time.time()
        Clock.schedule_interval(self.update_distance, 0.5)
        Clock.schedule_interval(self.update_vitesse, 0.5)
        Clock.schedule_interval(self.update_duree, 0.5)

    def update_distance(self, dt):
        self.distance_parcourue = capteur_vitesse.get_odometre()

    def update_vitesse(self, dt):
        if self.is_running:
            self.vitesse = capteur_vitesse.get_vitesse()
        else:
            self.vitesse = 0
    
    def update_duree(self, dt):
        if self.is_running:
            self.duree_session+=dt

    def toggle_collection(self):
        if self.is_running:
            self.ids.gauge.stop_collection()
        else:
            self.ids.gauge.start_collection()
        self.is_running = not self.is_running
        


class PowerApp(App):
    target_power = NumericProperty(TARGET_POWER)

    def build(self):
        return Dashboard()

    def on_stop(self):
        capteur_vitesse.cleanup()

if __name__ == "__main__":
    PowerApp().run()
