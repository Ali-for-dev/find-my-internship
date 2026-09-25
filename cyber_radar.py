#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
             CYBERSTAGE RADAR - VEILLE STAGES CYBERSÉCURITÉ FRANCE
=============================================================================
Agrégateur automatisé et système d'alertes en temps réel pour toutes
les offres de stage en Cybersécurité à travers toute la France.

Sources supportées :
  - LinkedIn Jobs (France)
  - HelloWork (France)
  - France Travail (France)

Alertes :
  - Notifications Bureau Windows (Toast / Bulle native)
  - Dashboard Web Interactif (HTML Cyberpunk / Dark Mode)
  - Discord Webhook (optionnel)
  - Telegram Bot (optionnel)
  - Export CSV & JSON
=============================================================================
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
import datetime
import argparse
import subprocess
import webbrowser
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Assurer l'encodage UTF-8 correct dans la console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "stages_cyber.db"
CONFIG_FILE = BASE_DIR / "config.json"
CSV_FILE = BASE_DIR / "stages_cyber.csv"
JSON_FILE = BASE_DIR / "stages_cyber.json"
DASHBOARD_FILE = BASE_DIR / "stages_cyber_dashboard.html"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def load_config():
    """Charge la configuration depuis config.json ou crée une config par défaut."""
    if not CONFIG_FILE.exists():
        default_cfg = {
            "search": {
                "keywords": [
                    "stage cybersécurité",
                    "stage cyber security",
                    "stage pentest",
                    "stage SOC cyber",
                    "stage sécurité informatique",
                    "stage DevSecOps",
                    "stage GRC cybersécurité"
                ],
                "location": "France",
                "sources": {
                    "linkedin": True,
                    "hellowork": True,
                    "francetravail": True
                }
            },
            "alerts": {
                "desktop_notifications": True,
                "sound": True,
                "discord_webhook_url": "",
                "telegram": {
                    "enabled": False,
                    "bot_token": "",
                    "chat_id": ""
                }
            },
            "scheduler": {
                "interval_minutes": 30
            },
            "dashboard": {
                "auto_open": True,
                "filename": "stages_cyber_dashboard.html"
            }
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_cfg, f, indent=2, ensure_ascii=False)
        return default_cfg

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Erreur lecture config.json: {e}, utilisation des paramètres par défaut.")
        return {}


def init_db():
    """Initialise la base de données SQLite pour l'historique et la déduplication."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            link TEXT UNIQUE,
            source TEXT,
            first_seen TIMESTAMP,
            notified INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def make_offer_id(link: str, title: str, company: str) -> str:
    """Génère un identifiant unique robuste basé sur le lien et le contenu."""
    clean_link = link.split("?")[0].strip().lower()
    raw = f"{clean_link}|{title.strip().lower()}|{company.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def is_cyber_stage_relevant(title: str, source: str = "") -> bool:
    """Filtre les offres pour s'assurer de leur pertinence en Cybersécurité et Stage."""
    t = title.lower()
    
    # Mots-clés cyber obligatoires
    cyber_terms = ["cyber", "sécurité", "securite", "pentest", "soc", "siem", "devsecops", "infosec", "grc", "cryptographie", "vulnerab", "forensic", "cert"]
    if not any(term in t for term in cyber_terms):
        return False
    
    # Postes hors cible (expérimentés, commerciaux ou CDI explicites)
    exclude_terms = ["senior", "directeur", "responsable", "manager", "commercial", "officier", "lead", "architecte senior"]
    if any(ex in t for ex in exclude_terms):
        return False

    # Éviter les CDI/CDD stricts si non combinés avec stage
    if "cdi" in t and "stage" not in t:
        return False
    if "cdd" in t and "stage" not in t:
        return False

    # Pour France Travail spécifiquement (qui a parfois des offres formation/CDI mélangées)
    if source == "France Travail":
        stage_terms = ["stage", "stagiaire", "pfe", "étudiant", "etudiant", "fin d'étude", "fin d'etude", "césure", "cesure"]
        if not any(st in t for st in stage_terms):
            return False

    return True


# =============================================================================
# SCRAPERS
# =============================================================================

def scrape_linkedin(keywords: str, location: str = "France", max_pages: int = 2):
    """Scrape l'API invité LinkedIn pour les offres de stage (f_JT=I)."""
    offers = []
    headers = DEFAULT_HEADERS.copy()

    for page in range(max_pages):
        start = page * 25
        encoded_kw = urllib.parse.quote(keywords)
        encoded_loc = urllib.parse.quote(location)
        url = (
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
            f"keywords={encoded_kw}&location={encoded_loc}&f_JT=I&start={start}"
        )

        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.find_all("li")
            if not items:
                break

            for li in items:
                title_el = li.find("h3", class_="base-search-card__title")
                company_el = li.find("h4", class_="base-search-card__subtitle")
                loc_el = li.find("span", class_="job-search-card__location")
                link_el = li.find("a", class_="base-card__full-link")
                time_el = li.find("time")

                if title_el and link_el:
                    title = title_el.get_text(strip=True)
                    if not is_cyber_stage_relevant(title):
                        continue

                    company = company_el.get_text(strip=True) if company_el else "Entreprise confidentielle"
                    city = loc_el.get_text(strip=True) if loc_el else "France"
                    raw_link = link_el.get("href", "").split("?")[0]
                    posted = time_el.get_text(strip=True) if time_el else "Récent"

                    offers.append({
                        "title": title,
                        "company": company,
                        "location": city,
                        "link": raw_link,
                        "source": "LinkedIn",
                        "posted": posted
                    })

            time.sleep(1)  # Respecter les limites de requêtes
        except Exception as e:
            # En cas de timeout ou légère erreur réseau
            pass

    return offers


def scrape_hellowork(keywords: str = "cybersecurite", location: str = "France"):
    """Scrape les offres de stage en cybersécurité sur HelloWork."""
    offers = []
    encoded_kw = urllib.parse.quote(keywords)
    encoded_loc = urllib.parse.quote(location)
    url = f"https://www.hellowork.com/fr-fr/emploi/recherche.html?k={encoded_kw}&c=Stage&l={encoded_loc}"
    headers = DEFAULT_HEADERS.copy()

    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li", attrs={"data-hide-offer-item-id-value": True})

            for li in cards:
                t_inp = li.find("input", attrs={"name": "title"})
                c_inp = li.find("input", attrs={"name": "company"})
                id_val = li.get("data-hide-offer-item-id-value")

                if not id_val or not t_inp:
                    continue

                title = t_inp.get("value", "").strip()
                company = c_inp.get("value", "").strip() if c_inp else "Entreprise confidentielle"
                link = f"https://www.hellowork.com/fr-fr/emplois/{id_val}.html"

                if not is_cyber_stage_relevant(title):
                    continue

                # Localisation
                city = "France"
                text_content = li.get_text(" | ", strip=True)
                parts = [p.strip() for p in text_content.split("|") if p.strip()]
                for p in parts:
                    if any(num in p for num in ["01", "06", "13", "31", "33", "35", "38", "44", "59", "67", "69", "75", "92", "93", "94", "95"]) or "Télétravail" in p:
                        city = p
                        break

                offers.append({
                    "title": title,
                    "company": company,
                    "location": city,
                    "link": link,
                    "source": "HelloWork",
                    "posted": "Récent"
                })
    except Exception as e:
        pass

    return offers


def scrape_france_travail(keywords: str = "cybersecurite"):
    """Scrape les offres de stage sur France Travail."""
    offers = []
    encoded_kw = urllib.parse.quote(keywords)
    url = f"https://candidat.pole-emploi.fr/offres/recherche?motsCles={encoded_kw}&typeContrat=FS"
    headers = DEFAULT_HEADERS.copy()

    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            results = soup.find_all("li", class_="result")

            for li in results:
                title_el = li.find(class_="media-heading-title")
                link_el = li.find("a", class_="media")
                sub_el = li.find("p", class_="subtext")

                if title_el and link_el:
                    title = title_el.get_text(strip=True)
                    if not is_cyber_stage_relevant(title, "France Travail"):
                        continue

                    raw_href = link_el.get("href", "")
                    clean_href = raw_href.split(";")[0]
                    link = f"https://candidat.pole-emploi.fr{clean_href}"

                    sub_text = sub_el.get_text(" - ", strip=True) if sub_el else ""
                    parts = [p.strip() for p in sub_text.split("-") if p.strip()]

                    company = parts[0] if len(parts) > 1 else "Non précisé"
                    city = " - ".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else "France")

                    offers.append({
                        "title": title,
                        "company": company,
                        "location": city,
                        "link": link,
                        "source": "France Travail",
                        "posted": "Récent"
                    })
    except Exception:
        pass

    return offers


# =============================================================================
# GESTION DES NOTIFICATIONS & ALERTES
# =============================================================================

def send_windows_notification(title: str, message: str):
    """Envoie une notification native Windows Toast / Bulle sans module externe."""
    try:
        # Nettoyage des apostrophes pour PowerShell
        safe_title = title.replace("'", " ")
        safe_msg = message.replace("'", " ")
        ps_script = f"""
        [void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms')
        $notify = New-Object System.Windows.Forms.NotifyIcon
        $notify.Icon = [System.Drawing.SystemIcons]::Information
        $notify.BalloonTipTitle = '{safe_title}'
        $notify.BalloonTipText = '{safe_msg}'
        $notify.Visible = $True
        $notify.ShowBalloonTip(7000)
        Start-Sleep -Seconds 1
        $notify.Dispose()
        """
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=5)
    except Exception:
        pass


def send_discord_alert(webhook_url: str, new_offers: list):
    """Envoie une alerte avec carte riche au webhook Discord."""
    if not webhook_url or not new_offers:
        return

    # Limiter le nombre de champs par message Discord (max 10)
    for chunk in [new_offers[i:i + 10] for i in range(0, len(new_offers), 10)]:
        fields = []
        for off in chunk:
            fields.append({
                "name": f"🛡️ {off['title'][:100]}",
                "value": f"🏢 **Entreprise:** {off['company']}\n📍 **Lieu:** {off['location']}\n🌐 **Source:** {off['source']}\n🔗 [👉 Postuler à l'offre]({off['link']})",
                "inline": False
            })

        payload = {
            "username": "Radar Cyber Stages France",
            "avatar_url": "https://img.icons8.com/color/96/shield.png",
            "embeds": [
                {
                    "title": f"🚨 {len(chunk)} Nouvelle(s) Offre(s) de Stage Cybersécurité détectée(s) !",
                    "description": "Voici les dernières annonces de stage en cybersécurité publiées en France :",
                    "color": 0x00FFB3,  # Cyber Turquoise
                    "fields": fields,
                    "footer": {
                        "text": f"Radar Cybersécurité France • {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
                    }
                }
            ]
        }

        try:
            requests.post(webhook_url, json=payload, timeout=8)
            time.sleep(1)
        except Exception as e:
            print(f"[!] Erreur webhook Discord: {e}")


def send_telegram_alert(bot_token: str, chat_id: str, new_offers: list):
    """Envoie un message formaté vers Telegram."""
    if not bot_token or not chat_id or not new_offers:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for off in new_offers[:10]:
        text = (
            f"🛡️ *NOUVEAU STAGE CYBERSÉCURITÉ*\n\n"
            f"🎯 *Poste:* {off['title']}\n"
            f"🏢 *Entreprise:* {off['company']}\n"
            f"📍 *Lieu:* {off['location']}\n"
            f"📡 *Plateforme:* {off['source']}\n\n"
            f"🔗 [Accéder directement à l'annonce]({off['link']})"
        )
        try:
            requests.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }, timeout=8)
            time.sleep(0.5)
        except Exception as e:
            print(f"[!] Erreur Telegram: {e}")


# =============================================================================
# EXPORT & DASHBOARD HTML CYBERPUNK
# =============================================================================

def export_csv_and_json(all_offers: list):
    """Exporte les offres vers CSV et JSON."""
    # JSON
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_offers, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Erreur export JSON: {e}")

    # CSV
    try:
        import csv
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["ID", "Titre", "Entreprise", "Localisation", "Plateforme", "Date Détection", "Lien Direct"])
            for o in all_offers:
                writer.writerow([
                    o.get("id", ""),
                    o.get("title", ""),
                    o.get("company", ""),
                    o.get("location", ""),
                    o.get("source", ""),
                    o.get("first_seen", ""),
                    o.get("link", "")
                ])
    except Exception as e:
        print(f"[!] Erreur export CSV: {e}")


def generate_html_dashboard(offers: list):
    """Génère un dashboard web interactif moderne et ultra fluide."""
    total_count = len(offers)
    sources_count = {}
    for o in offers:
        src = o.get("source", "Autre")
        sources_count[src] = sources_count.get(src, 0) + 1

    # Injection JSON pour le script client
    json_data = json.dumps(offers, ensure_ascii=False)
    gen_time = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")

    html_template = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CyberStage Radar | Stages Cybersécurité France</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #090d16;
      --card-bg: rgba(16, 23, 38, 0.85);
      --card-border: rgba(0, 240, 255, 0.18);
      --accent: #00f0ff;
      --accent-glow: rgba(0, 240, 255, 0.4);
      --accent-green: #00ff88;
      --accent-purple: #9d4edd;
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --badge-linkedin: #0a66c2;
      --badge-hellowork: #ff5400;
      --badge-francetravail: #003b80;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: 'Outfit', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.5;
      background-image: 
        radial-gradient(ellipse at 10% 20%, rgba(0, 240, 255, 0.08) 0%, transparent 40%),
        radial-gradient(ellipse at 90% 80%, rgba(157, 78, 221, 0.08) 0%, transparent 40%);
      background-attachment: fixed;
    }}
    header {{
      padding: 2.5rem 1.5rem 1.5rem;
      max-width: 1300px;
      margin: 0 auto;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1.5rem;
    }}
    .logo-block {{
      display: flex;
      align-items: center;
      gap: 1rem;
    }}
    .shield-icon {{
      width: 48px;
      height: 48px;
      background: linear-gradient(135deg, #00f0ff, #9d4edd);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
      box-shadow: 0 0 20px var(--accent-glow);
    }}
    h1 {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.8rem;
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #fff;
    }}
    .subtitle {{
      color: var(--text-muted);
      font-size: 0.95rem;
    }}
    .stats-bar {{
      display: flex;
      gap: 1rem;
      flex-wrap: wrap;
    }}
    .stat-pill {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      padding: 0.5rem 1rem;
      border-radius: 999px;
      font-size: 0.85rem;
      font-family: 'JetBrains Mono', monospace;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .stat-pill strong {{
      color: var(--accent);
      font-size: 1.05rem;
    }}
    .container {{
      max-width: 1300px;
      margin: 2rem auto;
      padding: 0 1.5rem 4rem;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      margin-bottom: 2rem;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      padding: 1rem 1.25rem;
      border-radius: 14px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
      backdrop-filter: blur(12px);
    }}
    .search-box {{
      flex: 1;
      min-width: 260px;
      position: relative;
    }}
    .search-box input {{
      width: 100%;
      background: rgba(0,0,0,0.4);
      border: 1px solid rgba(255,255,255,0.15);
      padding: 0.75rem 1rem 0.75rem 2.5rem;
      border-radius: 10px;
      color: #fff;
      font-family: inherit;
      font-size: 0.95rem;
      outline: none;
      transition: all 0.2s;
    }}
    .search-box input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 12px var(--accent-glow);
    }}
    .search-icon {{
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-muted);
    }}
    .filters {{
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }}
    .filter-btn {{
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      color: var(--text);
      padding: 0.5rem 1rem;
      border-radius: 8px;
      cursor: pointer;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      transition: all 0.2s;
    }}
    .filter-btn:hover, .filter-btn.active {{
      background: var(--accent);
      color: #000;
      border-color: var(--accent);
      font-weight: 600;
      box-shadow: 0 0 14px var(--accent-glow);
    }}
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
      gap: 1.25rem;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 1.4rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.25s, border-color 0.25s, box-shadow 0.25s;
      position: relative;
      overflow: hidden;
      backdrop-filter: blur(8px);
    }}
    .card::before {{
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, var(--accent), var(--accent-purple));
      opacity: 0.4;
      transition: opacity 0.25s;
    }}
    .card:hover {{
      transform: translateY(-4px);
      border-color: var(--accent);
      box-shadow: 0 12px 28px rgba(0, 240, 255, 0.15);
    }}
    .card:hover::before {{
      opacity: 1;
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.75rem;
      margin-bottom: 0.75rem;
    }}
    .badge {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      padding: 0.25rem 0.6rem;
      border-radius: 6px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .badge-linkedin {{ background: rgba(10, 102, 194, 0.25); color: #5db2ff; border: 1px solid rgba(10, 102, 194, 0.5); }}
    .badge-hellowork {{ background: rgba(255, 84, 0, 0.25); color: #ff9d66; border: 1px solid rgba(255, 84, 0, 0.5); }}
    .badge-francetravail {{ background: rgba(0, 110, 255, 0.25); color: #70b4ff; border: 1px solid rgba(0, 110, 255, 0.5); }}
    .badge-stage {{ background: rgba(0, 255, 136, 0.15); color: var(--accent-green); border: 1px solid rgba(0, 255, 136, 0.3); }}
    .job-title {{
      font-size: 1.15rem;
      font-weight: 700;
      color: #fff;
      margin-bottom: 0.5rem;
      line-height: 1.35;
    }}
    .company-name {{
      color: var(--accent);
      font-weight: 600;
      font-size: 0.95rem;
      margin-bottom: 0.5rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }}
    .location {{
      color: var(--text-muted);
      font-size: 0.85rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      margin-bottom: 1.25rem;
    }}
    .card-footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-top: 1rem;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      margin-top: auto;
    }}
    .detected-date {{
      font-size: 0.75rem;
      color: var(--text-muted);
      font-family: 'JetBrains Mono', monospace;
    }}
    .apply-btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: linear-gradient(135deg, var(--accent), #00b4d8);
      color: #050b14;
      text-decoration: none;
      padding: 0.55rem 1rem;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.85rem;
      transition: all 0.2s;
    }}
    .apply-btn:hover {{
      box-shadow: 0 0 16px var(--accent-glow);
      transform: scale(1.03);
    }}
    .empty-state {{
      grid-column: 1 / -1;
      text-align: center;
      padding: 4rem 1rem;
      color: var(--text-muted);
    }}
    @media (max-width: 768px) {{
      .cards-grid {{ grid-template-columns: 1fr; }}
      header {{ flex-direction: column; align-items: flex-start; }}
    }}
  </style>
</head>
<body>

  <header>
    <div class="logo-block">
      <div class="shield-icon">🛡️</div>
      <div>
        <h1>CyberStage Radar // France</h1>
        <p class="subtitle">Veille automatisée des offres de stage en Cybersécurité (Toute la France)</p>
      </div>
    </div>
    <div class="stats-bar">
      <div class="stat-pill">Total: <strong id="totalCount">{total_count}</strong></div>
      <div class="stat-pill">LinkedIn: <strong>{sources_count.get("LinkedIn", 0)}</strong></div>
      <div class="stat-pill">HelloWork: <strong>{sources_count.get("HelloWork", 0)}</strong></div>
      <div class="stat-pill">France Travail: <strong>{sources_count.get("France Travail", 0)}</strong></div>
      <div class="stat-pill">Scan: <span>{gen_time}</span></div>
    </div>
  </header>

  <div class="container">
    <div class="toolbar">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" placeholder="Rechercher par mot-clé, entreprise, ville (ex: Pentest, Capgemini, Paris, Rennes)...">
      </div>
      <div class="filters">
        <button class="filter-btn active" data-source="ALL">TOUTES</button>
        <button class="filter-btn" data-source="LinkedIn">LinkedIn</button>
        <button class="filter-btn" data-source="HelloWork">HelloWork</button>
        <button class="filter-btn" data-source="France Travail">France Travail</button>
      </div>
    </div>

    <div class="cards-grid" id="cardsGrid">
      <!-- Rendu dynamique via JavaScript -->
    </div>
  </div>

  <script>
    const ALL_OFFERS = {json_data};
    let currentSource = "ALL";
    let searchTerm = "";

    function getBadgeClass(source) {{
      if (source === "LinkedIn") return "badge-linkedin";
      if (source === "HelloWork") return "badge-hellowork";
      return "badge-francetravail";
    }}

    function renderOffers() {{
      const grid = document.getElementById("cardsGrid");
      grid.innerHTML = "";

      const filtered = ALL_OFFERS.filter(item => {{
        const matchSource = (currentSource === "ALL" || item.source === currentSource);
        const searchTarget = `${{item.title}} ${{item.company}} ${{item.location}}`.toLowerCase();
        const matchSearch = (!searchTerm || searchTarget.includes(searchTerm));
        return matchSource && matchSearch;
      }});

      document.getElementById("totalCount").innerText = filtered.length;

      if (filtered.length === 0) {{
        grid.innerHTML = `
          <div class="empty-state">
            <h3>Aucune offre ne correspond à vos critères de recherche.</h3>
            <p>Essayez de modifier votre mot-clé ou réinitialisez le filtre de plateforme.</p>
          </div>
        `;
        return;
      }}

      filtered.forEach(item => {{
        const card = document.createElement("div");
        card.className = "card";
        const badgeClass = getBadgeClass(item.source);

        card.innerHTML = `
          <div>
            <div class="card-top">
              <span class="badge badge-stage">STAGE</span>
              <span class="badge ${{badgeClass}}">${{item.source}}</span>
            </div>
            <h2 class="job-title">${{item.title}}</h2>
            <div class="company-name">🏢 ${{item.company}}</div>
            <div class="location">📍 ${{item.location}}</div>
          </div>
          <div class="card-footer">
            <span class="detected-date">⏱️ ${{item.first_seen || item.posted || 'Récent'}}</span>
            <a href="${{item.link}}" target="_blank" rel="noopener noreferrer" class="apply-btn">
              Voir & Postuler ➔
            </a>
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    // Gestion de la recherche en temps réel
    document.getElementById("searchInput").addEventListener("input", (e) => {{
      searchTerm = e.target.value.toLowerCase().trim();
      renderOffers();
    }});

    // Gestion des boutons de filtre
    document.querySelectorAll(".filter-btn").forEach(btn => {{
      btn.addEventListener("click", () => {{
        document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentSource = btn.dataset.source;
        renderOffers();
      }});
    }});

    // Premier rendu
    renderOffers();
  </script>
</body>
</html>
"""
    try:
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
            f.write(html_template)
    except Exception as e:
        print(f"[!] Erreur écriture Dashboard HTML: {e}")


# =============================================================================
# COEUR DU RADAR / ORCHESTRATION
# =============================================================================

def run_radar_scan(verbose: bool = True):
    """Effectue un cycle complet de scan, déduplication, alertes et export."""
    config = load_config()
    init_db()

    keywords_list = config.get("search", {}).get("keywords", ["stage cybersécurité"])
    location = config.get("search", {}).get("location", "France")
    sources_cfg = config.get("search", {}).get("sources", {"linkedin": True, "hellowork": True, "francetravail": True})

    if verbose:
        print("\n" + "="*70)
        print("🛡️  CYBERSTAGE RADAR - SCAN EN COURS SUR TOUTE LA FRANCE")
        print(f"🕒 Heure: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

    all_scraped = []

    # 1. LinkedIn Jobs
    if sources_cfg.get("linkedin", True):
        if verbose:
            print("📡 [1/3] Scraping LinkedIn Jobs (France entière)...")
        for kw in keywords_list[:4]:  # Top keywords pour éviter le spam
            jobs = scrape_linkedin(kw, location=location)
            all_scraped.extend(jobs)
            time.sleep(0.5)

    # 2. HelloWork
    if sources_cfg.get("hellowork", True):
        if verbose:
            print("📡 [2/3] Scraping HelloWork (Stages Cybersécurité)...")
        for kw in ["cybersecurite", "securite informatique", "pentest"]:
            jobs = scrape_hellowork(kw, location=location)
            all_scraped.extend(jobs)
            time.sleep(0.5)

    # 3. France Travail
    if sources_cfg.get("francetravail", True):
        if verbose:
            print("📡 [3/3] Scraping France Travail (Stages Cybersécurité)...")
        jobs = scrape_france_travail("cybersecurite")
        all_scraped.extend(jobs)

    # Déduplication en mémoire
    unique_candidates = {}
    for item in all_scraped:
        oid = make_offer_id(item["link"], item["title"], item["company"])
        if oid not in unique_candidates:
            item["id"] = oid
            unique_candidates[oid] = item

    if verbose:
        print(f"\n🔍 Offres brutes analysées : {len(all_scraped)} | Offres uniques : {len(unique_candidates)}")

    # Vérification avec la base de données pour détecter les NOUVELLES offres
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    new_offers = []
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    for oid, item in unique_candidates.items():
        cursor.execute("SELECT id, first_seen FROM offers WHERE id = ?", (oid,))
        row = cursor.fetchone()
        if not row:
            # Nouvelle offre détectée !
            cursor.execute("""
                INSERT INTO offers (id, title, company, location, link, source, first_seen, notified)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (oid, item["title"], item["company"], item["location"], item["link"], item["source"], now_str))
            item["first_seen"] = now_str
            new_offers.append(item)
        else:
            item["first_seen"] = row[1]

    conn.commit()

    # Récupérer toutes les offres actives pour le Dashboard
    cursor.execute("SELECT id, title, company, location, link, source, first_seen FROM offers ORDER BY first_seen DESC")
    all_db_rows = cursor.fetchall()
    conn.close()

    all_db_offers = []
    for r in all_db_rows:
        all_db_offers.append({
            "id": r[0],
            "title": r[1],
            "company": r[2],
            "location": r[3],
            "link": r[4],
            "source": r[5],
            "first_seen": r[6]
        })

    # Mise à jour des exports et du Dashboard Web
    export_csv_and_json(all_db_offers)
    generate_html_dashboard(all_db_offers)

    # Affichage Console et Envoi des Alertes
    if verbose:
        print(f"\n✨ NOUVELLES OFFRES DÉTECTÉES AUJOURD'HUI : {len(new_offers)}")
        print(f"📊 TOTAL OFFRES RÉPERTORIÉES EN BDD : {len(all_db_offers)}")

        if new_offers:
            print("\n" + "-"*70)
            for idx, off in enumerate(new_offers, 1):
                print(f"[{idx}] {off['title']}")
                print(f"    🏢 Entreprise : {off['company']}")
                print(f"    📍 Lieu       : {off['location']}")
                print(f"    🌐 Plateforme : {off['source']}")
                print(f"    🔗 Lien       : {off['link']}")
                print("-" * 70)
        else:
            print("✅ Aucune nouvelle annonce depuis le dernier scan (la base est à jour).")

    # Déclenchement des alertes pour les nouvelles offres
    if new_offers:
        alert_cfg = config.get("alerts", {})

        # Notification Bureau Windows
        if alert_cfg.get("desktop_notifications", True):
            notif_title = f"🛡️ Radar Cyber : {len(new_offers)} Nouveau(x) Stage(s) !"
            first_preview = f"{new_offers[0]['title']} chez {new_offers[0]['company']} ({new_offers[0]['location']})"
            if len(new_offers) > 1:
                first_preview += f" (+{len(new_offers)-1} autres)"
            send_windows_notification(notif_title, first_preview)

        # Discord
        discord_url = alert_cfg.get("discord_webhook_url", "").strip()
        if discord_url:
            send_discord_alert(discord_url, new_offers)

        # Telegram
        tg_cfg = alert_cfg.get("telegram", {})
        if tg_cfg.get("enabled", False) and tg_cfg.get("bot_token") and tg_cfg.get("chat_id"):
            send_telegram_alert(tg_cfg["bot_token"], tg_cfg["chat_id"], new_offers)

        # Marquer comme notifié
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for off in new_offers:
            cursor.execute("UPDATE offers SET notified = 1 WHERE id = ?", (off["id"],))
        conn.commit()
        conn.close()

    return new_offers, all_db_offers


def main():
    parser = argparse.ArgumentParser(description="Radar de détection des stages en Cybersécurité en France.")
    parser.add_argument("--now", action="store_true", help="Effectue un scan unique immédiat et quitte.")
    parser.add_argument("--daemon", action="store_true", help="Tourne en continu en arrière-plan selon l'intervalle configuré.")
    parser.add_argument("--interval", type=int, default=None, help="Intervalle en minutes pour le mode daemon (par défaut: 30 min).")
    parser.add_argument("--open", action="store_true", help="Ouvre le Dashboard HTML dans votre navigateur après le scan.")
    args = parser.parse_args()

    config = load_config()
    interval_min = args.interval or config.get("scheduler", {}).get("interval_minutes", 30)

    # Premier scan
    new_offers, all_offers = run_radar_scan(verbose=True)

    if args.open or config.get("dashboard", {}).get("auto_open", True):
        if DASHBOARD_FILE.exists():
            print(f"\n🌐 Ouverture du Dashboard dans votre navigateur : {DASHBOARD_FILE}")
            webbrowser.open(str(DASHBOARD_FILE))

    if args.daemon:
        print(f"\n🔄 Mode surveillance continue activé : prochain scan dans {interval_min} minutes.")
        print("Appuyez sur Ctrl+C pour arrêter le script à tout moment.\n")
        try:
            while True:
                time.sleep(interval_min * 60)
                run_radar_scan(verbose=True)
        except KeyboardInterrupt:
            print("\n🛑 Surveillance arrêtée par l'utilisateur.")


if __name__ == "__main__":
    main()
