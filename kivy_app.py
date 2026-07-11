from kivy.app import App

from kivy.uix.scatter import Scatter
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout

import random

class ScatterTextWidget(BoxLayout):
    def change_label_colour(self, *args):
        colour = [random.random() for i in xrange(3)] + [1]
        label = self.ids['my_label']
        label.color = colour

class PageLayout(AnchorLayout):
    pass

class TutorialApp(App):
    def build(self):
        #return ScatterTextWidget()
        return PageLayout(page1=ScatterTextWidget(), page2=ScatterTextWidget())


if __name__ == "__main__":
    TutorialApp().run()
