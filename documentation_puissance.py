#P = Vg·(½·ρ·CdA·Vg²)                          ← aérodynamique (en supposant Va ≈ Vg, vent calme)
#  + Vg·Crr·mt·g·cos(pitch)                     ← roulement (pitch mesuré par BNO085)
#  + Vg·(91 + 8.7·Vg)·10⁻³                      ← friction roulements (empirique, optionnel)
#  + Vg·mt·g·sin(pitch)                         ← gravité (pitch mesuré par BNO085)
#  + 0.5·(mt + I/r²)·(a·Vg)                       ← terme cinétique (accélération BNO085 ou dV/dt du Hall)

Vg = vitesse sol du vélo (m/s)
Va = vitesse de l'air relative (m/s) — tient compte du vent
ρ = densité de l'air
CdA = aire de traînée (coefficient de traînée × surface frontale)
Fw = facteur de rotation des roues (traînée additionnelle due aux rayons)
Crr = coefficient de résistance au roulement
mt = masse totale (cycliste + vélo)
g = 9,81 m/s²
(91 + 8,7·Vg)·10⁻³ = terme empirique de friction des roulements de roue (dérivé de Dahn et al., 1991)
G = pente (rise/run, décimale — pas en %)
I = moment d'inertie des deux roues (~0,14 kg·m²)
r = rayon extérieur du pneu
(Vgf² − Vgi²)/(tf − ti) = terme cinétique — c'est ton terme d'accélération
Ec = efficacité de la chaîne (~0,976 mesurée dans l'étude)

Version pratique adaptée à ton setup
Tu n'as ni soufflerie ni anémomètre pour mesurer le vent tangentiel/normal séparément, ni la traînée par angle de lacet
Voici une version simplifiée mais toujours rigoureuse, exploitant ce que tu as réellement (BNO085 + Hall) :
P = Vg·(½·ρ·CdA·Vg²)                          ← aérodynamique (en supposant Va ≈ Vg, vent calme)
  + Vg·Crr·mt·g·cos(pitch)                     ← roulement (pitch mesuré par BNO085)
  + Vg·(91 + 8.7·Vg)·10⁻³                      ← friction roulements (empirique, optionnel)
  + Vg·mt·g·sin(pitch)                         ← gravité (pitch mesuré par BNO085)
  + ½·(mt + I/r²)·(a·Vg)                       ← terme cinétique (accélération BNO085 ou dV/dt du Hall)
Note sur le dernier terme : Martin et al. calculent l'accélération par différence finie (Vf²−Vi²)/(tf−ti). Pour du temps réel avec échantillonnage fréquent, la forme équivalente mt · a · Vg (avec a = dV/dt) que je te proposais avant fonctionne aussi bien et est plus naturelle en code — mathématiquement, d(V²)/dt = 2V·a, donc ½·mt·d(V²)/dt = mt·a·V. Les deux formulations sont cohérentes.
Différences clés par rapport à ton document PDF français
TermeDoc PDF françaisMartin et al. 1998Aéro½ρSCxV³équivalent, CdA = SCxRoulementCr(Mc+Mv)gVmême formule, + cos(pente) (négligeable <10%)Frottements mécaniquesCfm(Mc+Mv)gV (constante empirique)formule empirique dépendant de la vitesse (91+8.7V)10⁻³ — plus précise et validéeGravité(Mc+Mv)gV·sin(arctan(p))identiqueInertie/accélérationabsentprésent — terme clé pour toiEfficacité chaîneabsent/Ec (~2,4% de perte)
Recommandation concrète pour ton code

Utilise ton pitch du BNO085 directement pour sin(pitch) et cos(pitch) — pas besoin de passer par arctan() comme dans le PDF, tu as déjà l'angle
Utilise le terme empirique de friction des roulements (91+8.7·Vg)·10⁻³ de Martin et al. plutôt que le Cfm constant du PDF français — c'est une amélioration directe basée sur des mesures réelles (Dahn et al., 1991)
Pour le moment d'inertie des roues (I ≈ 0,14 kg·m²), c'est une valeur par défaut raisonnable si tu n'as pas les specs exactes de tes roues
Le facteur d'efficacité de chaîne Ec (diviser par ~0,97-0,98) est une correction fine — optionnelle selon ta tolérance de précision vis