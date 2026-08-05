"""
Estimation de la puissance au roue (watts).

Modèle simplifié adapté au setup BNO085 + capteur Hall, inspiré de
Martin et al. (1998), en supposant vent calme (Va ≈ Vg).

Formule globale :
    P = P_aero + P_roulement + P_frottements + P_gravité + P_inertie

Références :
    - Martin, J. C., et al. (1998). A mathematical model to predict road cycling power.
    - Dahn et al. (1991) — terme empirique des roulements de roue.
"""


import math
from collections import deque
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constantes physiques
# ---------------------------------------------------------------------------

G = 9.81  # gravité (m/s²)
RHO_AIR = 1.225  # densité de l'air au niveau de la mer (~15 °C, kg/m³)

# ---------------------------------------------------------------------------
# Paramètres du vélo et du cycliste (à calibrer selon ton setup)
# ---------------------------------------------------------------------------

MASSE_TOTALE_KG = 80.0  # mt : masse cycliste + vélo
CDA = 0.35  # CdA : coefficient de traînée × surface frontale (m²)
CRR = 0.004  # Crr : coefficient de résistance au roulement

INERTIE_ROUES_KGM2 = 0.14  # I : moment d'inertie des deux roues (kg·m²)
RAYON_PNEU_M = 0.35  # r : rayon extérieur du pneu (700c ≈ 0,35 m)

# Options
INCLURE_FROTTEMENT_ROULEMENTS = True  # terme (91 + 8,7·Vg)·10⁻³
EFFICACITE_CHAINE = 0.976  # Ec : pertes de chaîne (~2,4 %), optionnel
MOYENNE_MOBILE_FENETRE = 20  # ~10 s à 0,5 s/échantillon
ACCELERATION_DEADBAND_MS2 = 0.10
ACCELERATION_MAX_MS2 = 2.0


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------

@dataclass
class Mesures:
    """Grandeurs mesurées en temps réel."""

    vitesse_sol_ms: float  # Vg : vitesse sol (m/s), capteur Hall
    pitch_rad: float  # pitch du BNO085 (rad), + = montée
    acceleration_ms2: float  # a = dVg/dt (m/s²), Hall ou BNO085


@dataclass
class ComposantesPuissance:
    """Détail de chaque terme de la puissance au roue (watts)."""

    aerodynamique_w: float
    roulement_w: float
    frottement_roulements_w: float
    gravite_w: float
    inertie_w: float

    @property
    def total_roue_w(self) -> float:
        return (
            self.aerodynamique_w
            + self.roulement_w
            + self.frottement_roulements_w
            + self.gravite_w
            + self.inertie_w
        )


# ---------------------------------------------------------------------------
# Termes individuels de la formule
# ---------------------------------------------------------------------------

def puissance_aerodynamique(
    vg: float,
    cda: float = CDA,
    rho: float = RHO_AIR,
) -> float:
    """
    Traînée aérodynamique (vent calme, Va ≈ Vg).

    P_aero = ½ · ρ · CdA · Vg³
    """
    return 0.5 * rho * cda * vg**3


def puissance_roulement(
    vg: float,
    pitch_rad: float,
    mt: float = MASSE_TOTALE_KG,
    crr: float = CRR,
    g: float = G,
) -> float:
    """
    Résistance au roulement, corrigée par l'inclinaison.

    P_roll = Vg · Crr · mt · g · cos(pitch)
    """
    return vg * crr * mt * g * math.cos(pitch_rad)


def puissance_frottement_roulements(vg: float) -> float:
    """
    Friction des roulements de roue (terme empirique).

    P_bearing = Vg · (91 + 8,7 · Vg) · 10⁻³
    """
    return vg * (91.0 + 8.7 * vg) * 1e-3


def puissance_gravite(
    vg: float,
    pitch_rad: float,
    mt: float = MASSE_TOTALE_KG,
    g: float = G,
) -> float:
    """
    Composante gravitaire de la pente.

    P_grade = Vg · mt · g · sin(pitch)
    """
    return vg * mt * g * math.sin(pitch_rad)


def puissance_inertie(
    vg: float,
    acceleration_ms2: float,
    mt: float = MASSE_TOTALE_KG,
    inertie_roues: float = INERTIE_ROUES_KGM2,
    rayon: float = RAYON_PNEU_M,
) -> float:
    """
    Énergie cinétique (translation + rotation des roues).

    P_kin = ½ · (mt + I/r²) · a · Vg

    a peut venir :
      - du BNO085 (accélération longitudinale), ou
      - d'une différence finie dV/dt sur la vitesse Hall.

    Note : ½ · mt · d(V²)/dt = mt · a · V (les deux formulations sont équivalentes).
    """
    masse_equivalente = mt + inertie_roues / (rayon**2)
    return masse_equivalente * acceleration_ms2 * vg


# ---------------------------------------------------------------------------
# Calcul global
# ---------------------------------------------------------------------------

def estimer_puissance(
    mesures: Mesures,
    *,
    mt: float = MASSE_TOTALE_KG,
    cda: float = CDA,
    crr: float = CRR,
    inertie_roues: float = INERTIE_ROUES_KGM2,
    rayon: float = RAYON_PNEU_M,
    inclure_frottement_roulements: bool = INCLURE_FROTTEMENT_ROULEMENTS,
) -> ComposantesPuissance:
    """Calcule tous les termes de puissance pour un jeu de mesures."""
    vg = mesures.vitesse_sol_ms
    pitch = mesures.pitch_rad
    a = mesures.acceleration_ms2

    frottement = (
        puissance_frottement_roulements(vg)
        if inclure_frottement_roulements
        else 0.0
    )

    return ComposantesPuissance(
        aerodynamique_w=puissance_aerodynamique(vg, cda=cda),
        roulement_w=puissance_roulement(vg, pitch, mt=mt, crr=crr),
        frottement_roulements_w=frottement,
        gravite_w=puissance_gravite(vg, pitch, mt=mt),
        inertie_w=puissance_inertie(vg, a, mt=mt, inertie_roues=inertie_roues, rayon=rayon),
    )

def puissance_pedalier(puissance_roue_w: float, ec: float = EFFICACITE_CHAINE) -> float:
    """
    Puissance à produire aux pédales, en corrigeant les pertes de chaîne.
    P_pédalier = P_roue / Ec
    """
    return max(0.0, puissance_roue_w) / ec


def puissance_cycliste_w(composantes: ComposantesPuissance, deadband_w: float = 2.0) -> float:
    """
    Puissance percue au pedalier, non negative (coasting = 0 W).
    Un deadband evite le flicker autour de 0 W du au bruit des capteurs.
    """
    total = composantes.total_roue_w
    return total if total > deadband_w else 0.0


# ---------------------------------------------------------------------------
# Utilitaires de conversion
# ---------------------------------------------------------------------------

def kmh_vers_ms(vitesse_kmh: float) -> float:
    return vitesse_kmh / 3.6


def degres_vers_radians(angle_deg: float) -> float:
    return math.radians(angle_deg)


def acceleration_par_difference_finie(
    vitesse_finale_ms: float,
    vitesse_initiale_ms: float,
    delta_t_s: float,
) -> float:
    """
    Estime a = dV/dt à partir de deux vitesses consécutives.

    Alternative à l'accélération directe du BNO085.
    """
    if delta_t_s <= 0:
        return 0.0
    return (vitesse_finale_ms - vitesse_initiale_ms) / delta_t_s


def creer_mesures(vitesse_sol_ms: float, pitch_rad: float, acceleration_ms2: float) -> Mesures:
    return Mesures(vitesse_sol_ms=vitesse_sol_ms, pitch_rad=pitch_rad, acceleration_ms2=acceleration_ms2)


# ---------------------------------------------------------------------------
# Lissage par moyenne mobile
# ---------------------------------------------------------------------------

class MoyenneMobile:
    """Moyenne glissante pour le flux temps réel (ex. affichage de la puissance)."""

    def __init__(self, fenetre: int = MOYENNE_MOBILE_FENETRE):
        self.fenetre = max(1, fenetre)
        self._buffer: deque[float] = deque(maxlen=self.fenetre)

    def ajouter(self, valeur: float) -> float:
        self._buffer.append(valeur)
        return sum(self._buffer) / len(self._buffer)

    def reinitialiser(self) -> None:
        self._buffer.clear()


def moyenne_mobile_serie(
    valeurs: list[float],
    fenetre: int = MOYENNE_MOBILE_FENETRE,
) -> list[float]:
    """Applique une moyenne mobile à une série complète (ex. replay d'une course)."""
    if fenetre <= 1:
        return list(valeurs)

    result: list[float] = []
    buffer: deque[float] = deque(maxlen=fenetre)
    for valeur in valeurs:
        buffer.append(valeur)
        result.append(sum(buffer) / len(buffer))
    return result


def filtrer_acceleration(
    acceleration_ms2: float,
    *,
    deadband_ms2: float = ACCELERATION_DEADBAND_MS2,
    max_ms2: float = ACCELERATION_MAX_MS2,
) -> float:
    """Deadband et plafond appliqués après le lissage."""
    if abs(acceleration_ms2) < deadband_ms2:
        return 0.0
    return max(-max_ms2, min(acceleration_ms2, max_ms2))


def filtrer_acceleration_serie(
    valeurs: list[float],
    fenetre: int = MOYENNE_MOBILE_FENETRE,
    *,
    deadband_ms2: float = ACCELERATION_DEADBAND_MS2,
    max_ms2: float = ACCELERATION_MAX_MS2,
) -> list[float]:
    """Même pipeline d'accélération que power.py, pour --recalculer."""
    return [
        filtrer_acceleration(a, deadband_ms2=deadband_ms2, max_ms2=max_ms2)
        for a in moyenne_mobile_serie(valeurs, fenetre)
    ]


def estimer_puissance_pedalier(
    vitesse_kmh: float,
    pitch_deg: float,
    acceleration_ms2: float,
    *,
    mt: float = MASSE_TOTALE_KG,
    cda: float = CDA,
    crr: float = CRR,
    inertie_roues: float = INERTIE_ROUES_KGM2,
    rayon: float = RAYON_PNEU_M,
    inclure_frottement_roulements: bool = INCLURE_FROTTEMENT_ROULEMENTS,
    deadband_w: float = 2.0,
    ec: float = EFFICACITE_CHAINE,
) -> float:
    """Chaîne complète vitesse/pitch/accélération → puissance au pédalier (W)."""
    mesures = creer_mesures(
        kmh_vers_ms(vitesse_kmh),
        degres_vers_radians(pitch_deg),
        acceleration_ms2,
    )
    composantes = estimer_puissance(
        mesures,
        mt=mt,
        cda=cda,
        crr=crr,
        inertie_roues=inertie_roues,
        rayon=rayon,
        inclure_frottement_roulements=inclure_frottement_roulements,
    )
    puissance_roue = puissance_cycliste_w(composantes, deadband_w=deadband_w)
    return puissance_pedalier(puissance_roue, ec=ec)
