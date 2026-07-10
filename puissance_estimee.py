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
    return 0.5 * masse_equivalente * acceleration_ms2 * vg


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
    return puissance_roue_w / ec


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


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

def afficher_puissance(composantes: ComposantesPuissance, *, afficher_pedalier: bool = True) -> None:
    """Affiche le détail des composantes de puissance."""
    print("=" * 48)
    print("  Estimation de puissance")
    print("-" * 48)
    print(f"  Aérodynamique        : {composantes.aerodynamique_w:7.1f} W")
    print(f"  Roulement            : {composantes.roulement_w:7.1f} W")
    print(f"  Frottement roulements: {composantes.frottement_roulements_w:7.1f} W")
    print(f"  Gravité (pente)      : {composantes.gravite_w:7.1f} W")
    print(f"  Inertie (accél.)     : {composantes.inertie_w:7.1f} W")
    print("-" * 48)
    print(f"  TOTAL au roue        : {composantes.total_roue_w:7.1f} W")
    if afficher_pedalier:
        print(f"  Aux pédales (Ec)     : {puissance_pedalier(composantes.total_roue_w):7.1f} W")
    print()


# ---------------------------------------------------------------------------
# Exemple d'utilisation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Exemple : 25 km/h sur plat, accélération légère
    mesures_exemple = Mesures(
        vitesse_sol_ms=kmh_vers_ms(25.0),
        pitch_rad=degres_vers_radians(0.0),
        acceleration_ms2=0.2,
    )

    resultat = estimer_puissance(mesures_exemple)
    afficher_puissance(resultat)

    # Exemple : montée 5 % à 15 km/h, vitesse constante
    mesures_montee = Mesures(
        vitesse_sol_ms=kmh_vers_ms(15.0),
        pitch_rad=math.atan(0.05),  # pente 5 % = rise/run
        acceleration_ms2=0.0,
    )

    resultat_montee = estimer_puissance(mesures_montee)
    afficher_puissance(resultat_montee)
