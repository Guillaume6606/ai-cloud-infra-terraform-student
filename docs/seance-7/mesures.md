# Mesures séance 7 — groupe : ...

Région attribuée : ... ; rôles pour cette étape (manipulation, mesure, analyse) : ...

## Servir (étape 0)

| Mesure | Valeur |
| --- | --- |
| Démarrage à froid (première requête, jusqu'à la réponse) | ... s |
| Requête à chaud (même requête, renvoyée juste après) | ... s |
| GPU lu dans la console | ... |
| Instances au maximum lues dans la console | ... |
| Concurrence lue dans la console | ... |

## Une requête (étape 1)

Médiane de trois mesures par ligne, mesure à froid écartée.

| Prompt (tokens) | Sortie (tokens) | Premier token (ms) | Tokens/s | Durée totale (s) | Contrôle : premier token + sortie ÷ tokens/s (s) |
| --- | --- | --- | --- | --- | --- |
| 200 | 50 | ... | ... | ... | ... |
| 200 | 200 | ... | ... | ... | ... |
| 1 500 | 50 | ... | ... | ... | ... |
| 1 500 | 200 | ... | ... | ... | ... |

Écart entre la durée mesurée et le contrôle : ... %.

Conclusion : ce qui allonge le délai avant le premier token : ... ; ce qui allonge la durée totale : ...

## Plusieurs requêtes (étape 2)

Prompt de 200 tokens, réponse de 200 tokens. Colonnes de `load.py`.

| concurrence | prompt (tokens) | sortie (tokens) | premier token médian (ms) | premier token max (ms) | tokens/s par requête | durée totale (s) | débit total (tokens/s) | erreurs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 200 | 200 | ... | ... | ... | ... | ... | ... |
| 4 | 200 | 200 | ... | ... | ... | ... | ... | ... |
| 8 | 200 | 200 | ... | ... | ... | ... | ... | ... |
| 16 | 200 | 200 | ... | ... | ... | ... | ... | ... |
| 32 | 200 | 200 | ... | ... | ... | ... | ... | ... |

Créneaux occupés pendant le palier à 16 (`/slots`) : ... ; requêtes en attente (`/metrics`) : ...

Saturation : le débit total ne monte plus à partir de ... requêtes simultanées, à ... tokens/s.

Sort des requêtes au-delà de 16 (palier à 32) : ...

## Tracer (étape 4)

| Étape du span | Durée (ms) | Tokens d'entrée | Tokens de sortie |
| --- | --- | --- | --- |
| `load_context` | ... | - | - |
| `chat <modèle>` | ... | ... | ... |
| `validate_json` | ... | - | - |

Étape la plus lente : ...

Coût d'une alerte, à partir de ses tokens : ... $ (hypothèse de l'étape 3 : 800 tokens en entrée et 150 en sortie ; corrigée en : ...).

## Juger un candidat (étape 5)

Règle écrite avant de lancer le jeu d'évaluation, à ... h ... :

- gain de score minimal exigé : ... point(s)
- perte de débit tolérée : ... %

| Modèle | Score (champs correctement extraits) | Débit (tokens/s) | Mémoire |
| --- | --- | --- | --- |
| 4 bits (notre service) | ... | ... | ... |
| 8 bits (service de l'enseignant) | ... | ... (valeur affichée) | ... (valeur affichée) |

Décision, appliquée à la règle : ...
