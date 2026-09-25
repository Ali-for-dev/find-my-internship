# 🛡️ CyberStage Radar — Veille Stages Cybersécurité (France Entière)

Un outil automatisé de surveillance, d'agrégation et d'alertes en temps réel pour **toutes les offres de stage en Cybersécurité en France**.

---

## 🚀 Fonctionnalités Clés

- 📡 **Multi-Sources Nationales** :
  - **LinkedIn Jobs** (Filtre strict stage `f_JT=I`, toute la France)
  - **HelloWork** (Filtre officiel stage `c=Stage`, couverture nationale et régionale)
  - **France Travail** (Recherche officielle stages)
- 🎯 **Filtres Cyber Précis** : Pentest, Analyste SOC, DevSecOps, GRC, SSI, Cloud Security, Forensic, etc. (élimination automatique des faux positifs et CDI).
- 🗄️ **Déduplication SQLite (`stages_cyber.db`)** : Détecte uniquement les **NOUVELLES** offres par rapport aux scans précédents pour ne jamais vous alerter deux fois.
- 🔔 **Système d'Alertes Multi-Canaux** :
  - **Notifications Bureau Windows** (Toast / Pop-up natif Windows)
  - **Discord Webhook** (Optionnel : reçoit les fiches de poste avec bouton pour postuler)
  - **Telegram Bot** (Optionnel : alertes instantanées sur smartphone)
- 🌐 **Dashboard Web Interactif Cyberpunk (`stages_cyber_dashboard.html`)** :
  - Recherche en direct par mot-clé, ville ou entreprise
  - Filtre par plateforme
  - Liens directs 1-clic pour postuler immédiatement
- 📊 **Exports automatiques** : `stages_cyber.csv` (compatible Excel) et `stages_cyber.json`.

---

## 📂 Fichiers du Projet

| Fichier | Rôle |
|---|---|
| `cyber_radar.py` | Script principal de scraping, déduplication, alertes et génération |
| `LANCER_RADAR_CYBER.bat` | Lanceur 1-clic Windows (menu interactif avec options) |
| `config.json` | Configuration (mots-clés, canaux d'alertes, fréquence de scan) |
| `stages_cyber_dashboard.html` | Interface web moderne et responsive pour consulter les offres |
| `stages_cyber.csv` | Export tabulaire pour Excel / Google Sheets |
| `stages_cyber.db` | Base SQLite locale pour l'historique et la déduplication |

---

## ⚡ Utilisation Rapide

### Option 1 : Double-cliquer sur le lanceur Windows (Le plus simple)
Double-cliquez sur :
```bat
LANCER_RADAR_CYBER.bat
```
Un menu vous permettra de choisir entre :
1. **Scan immédiat + Ouverture du Dashboard Web** (Recommandé)
2. **Mode surveillance continue** (Tourne en tâche de fond toutes les 30 min avec alertes)
3. **Consulter le Dashboard Web existant**

---

### Option 2 : Ligne de commande Python

```bash
# 1. Faire un scan immédiat et afficher les résultats
python cyber_radar.py --now --open

# 2. Lancer la surveillance continue (ex: vérification toutes les 30 minutes)
python cyber_radar.py --daemon --interval 30
```

---

## ⚙️ Configuration (`config.json`)

Vous pouvez personnaliser votre recherche dans [config.json](file:///c:/Users/HP%20AMD/Desktop/100M/Career/config.json) :

```json
{
  "search": {
    "keywords": [
      "stage cybersécurité",
      "stage pentest",
      "stage SOC cyber",
      "stage sécurité informatique",
      "stage DevSecOps"
    ],
    "location": "France"
  },
  "alerts": {
    "desktop_notifications": true,
    "discord_webhook_url": "https://discord.com/api/webhooks/...",
    "telegram": {
      "enabled": false,
      "bot_token": "",
      "chat_id": ""
    }
  },
  "scheduler": {
    "interval_minutes": 30
  }
}
```

### 💡 Pour recevoir les alertes sur Discord :
1. Dans votre serveur Discord, allez dans les paramètres d'un salon > **Intégrations** > **Webhooks** > Créer un webhook.
2. Copiez l'URL et collez-la dans le champ `"discord_webhook_url"` de `config.json`.
3. À chaque nouveau stage publié en France, vous recevrez une alerte directe sur votre Discord / téléphone !
