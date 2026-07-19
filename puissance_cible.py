#Donnees du test de puissance critique a entrer
#FTP
#puissance max pour effort 3 min
#puissance max pour effort 10 min
#puissance max pour effort 18 min


FTP=220


def puissance_cible(pitch_deg,ftp=FTP):
    if pitch_deg > 10:
        facteur = 1.15   # pente extrême : gros effort, vitesse faible, peu d'aéro
    elif pitch_deg > 5:
        facteur = 1.10   # pente abrupte
    elif pitch_deg > 2:
        facteur = 1.05   # pente moyenne
    elif pitch_deg > 0:
        facteur = 1.00   # faux plat montant
    elif pitch_deg > -5:
        facteur = 0.85   # léger faux plat descendant : profiter de la gravité
    else:
        facteur = 0.0     # descente marquée : rouler en roue libre, pas d'effort

    puissance_cible = facteur * FTP

    return puissance_cible


