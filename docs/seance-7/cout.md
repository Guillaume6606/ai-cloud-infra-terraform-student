# Coût séance 7 — groupe : ...

Les prix restent vides : le prix de l'API est relu sur la page de tarifs le jour même, le prix horaire du GPU sur la page de tarifs de Cloud Run.

## Prix relevés

| Prix | Valeur | Source et date |
| --- | --- | --- |
| Prix horaire du GPU (L4 sur Cloud Run, région ...) | ... $ / h | ... |
| Prix d'entrée de l'API (modèle ...) | ... $ par million de tokens | ... |
| Prix de sortie de l'API | ... $ par million de tokens | ... |

## Hypothèses du fil rouge

| Hypothèse | Valeur |
| --- | --- |
| Alertes par jour | 87 216 (voir ci-dessous) |
| Tokens d'entrée par alerte | 800 |
| Tokens de sortie par alerte | 150 |
| Débit total à saturation (étape 2) | ... tokens/s |

Volume d'alertes : séance 6, 7 268 alertes sur les 72 000 premiers messages du rejeu, soit 10,09 % (Mesuré, seuil 0,0012). À 10 transactions par seconde, une journée compte 864 000 transactions : 864 000 × 7 268 ÷ 72 000 = 87 216 alertes par jour (Dérivé ; hypothèse : le taux du 1er octobre tient toute la journée). Les 800 tokens d'entrée et 150 tokens de sortie par alerte restent l'hypothèse de départ, à corriger avec la mesure de l'étape 4.

## Formules

```text
coût par million de tokens = prix horaire ÷ (tokens par seconde × 3 600 × taux d'occupation) × 1 000 000
coût API par jour          = alertes × (tokens d'entrée × prix d'entrée + tokens de sortie × prix de sortie) ÷ 1 000 000
coût GPU par jour          = prix horaire × 24
volume de bascule          = coût GPU par jour ÷ coût API d'une alerte
débit moyen nécessaire     = alertes × tokens de sortie ÷ 86 400
```

## Les nombres de la preuve (étape 3)

| Nombre | Valeur |
| --- | --- |
| Coût par million de tokens à 100 % d'occupation | ... $ |
| Coût par million de tokens à 20 % d'occupation | ... $ |
| Coût par jour, API | ... $ |
| Coût par jour, GPU | ... $ |
| Volume de bascule | ... alertes par jour |
| Coût API d'une alerte (formule de la ligne « volume de bascule ») | ... $ |
| Coût GPU par million de tokens de sortie, à comparer au prix de sortie de l'API (mêmes unités : $ par million de tokens) | ... $ contre ... $ |

## Vérification de capacité

| Mesure | Valeur |
| --- | --- |
| Débit de sortie requis (alertes par jour × 150 ÷ 86 400) | ... tokens/s |
| Débit total mesuré à l'étape 2 | ... tokens/s |
| Un seul L4 suffit au volume ? | ... |

Le GPU ne gagne sur le coût que si un seul L4 tient ce débit : sinon il faut plusieurs instances et le coût par jour du GPU se multiplie.
