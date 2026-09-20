# Pronos NBA 2026-27

Ligue de pronostics entre amis : chacun a classé les 30 équipes avant la saison,
la page compare avec le classement réel et calcule les points.

- **Page** : https://zrmzur24.github.io/pronos-nba/
- **Pronos** : `data/predictions.json` (pour renommer un joueur, modifier son nom ici)
- **Référence bookmaker** : `data/reference.json`
- **Classement réel** : `data/standings.json`, mis à jour chaque nuit par le robot (`.github/workflows/update.yml`)
- **Historique** : `data/history.json`, alimenté automatiquement pour la courbe

Pour forcer une mise à jour : onglet *Actions* → *Mise à jour du classement NBA* → *Run workflow*.
