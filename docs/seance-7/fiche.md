# Fiche de dimensionnement du LLM du fil rouge — groupe : ...

Une page. Chaque rubrique cite l'étape dont elle tire ses chiffres.

## Usage et volume (étapes 3 et 4)

Alertes par jour : ... ; tokens d'entrée par alerte : ... ; tokens de sortie par alerte : ... (mesurés dans une trace, identifiant de la trace : ...).

## Modèle et précision (étape 5)

Modèle retenu : ... en ... bits. Score qui le justifie : ... contre ... pour l'autre précision. Règle écrite avant : ...

## Performance (étapes 0, 1 et 2)

Démarrage à froid : ... s. Délai avant le premier token (prompt de ... tokens) : ... ms. Débit à saturation : ... tokens/s à ... requêtes simultanées.

## Lieu de service et coût (étape 3)

Choix : API ou GPU : ... Coût par jour de l'API : ... $ ; du GPU : ... $. Volume de bascule : ... alertes par jour.

Débit de sortie requis (alertes par jour × 150 ÷ 86 400) : ... tokens/s, contre un débit total mesuré à l'étape 2 de ... tokens/s. Le GPU ne gagne sur le coût que si un seul L4 tient ce débit : ...

## Trois nombres à surveiller (étapes 2 et 4)

1. ... , seuil : ...
2. ... , seuil : ...
3. ... , seuil : ...
