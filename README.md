# KFCPerso — démarrage from scratch

Mini-app Telegram pour commander chez KFC France (catalogue local + solde EUR).

- **Accès web** via Telegram WebApp (auth `initData`)
- **PostgreSQL** : config shop, users, sessions, articles, blacklist, commandes, paiements
- **Checkout local** : débit solde → commande `QUEUED` (traitement admin)

---

## Prérequis

| Outil | Version conseillée | Rôle |
|-------|--------------------|------|
| Python | 3.10+ | Runtime |
| PostgreSQL | 14+ | Base de données |
| Bot Telegram | token BotFather | Auth WebApp (prod) |

Auth : uniquement Telegram WebApp (`initData` signé). Pas de mode DEV.

---

## Installation (de zéro)

Ouvre un terminal dans le dossier du projet (`KFCPerso`).

### 1. Environnement Python

```bash
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Windows (cmd)
.\.venv\Scripts\activate.bat

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configuration Postgres (`.env`)

```bash
copy .env.example .env
# ou : cp .env.example .env
```

Édite `.env` :

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kfc_perso
DB_USER=postgres
DB_PASSWORD=ton_mot_de_passe

TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_AUTH_MAX_AGE_SECONDS=3600
```

Si webhook Telegram (au lieu du poll) :

```env
TELEGRAM_WEBHOOK=1
TELEGRAM_WEBHOOK_SECRET=une-chaine-longue-aleatoire
```

PostgreSQL doit tourner et l’utilisateur doit pouvoir créer une base.

### 3. Config shop (table `config`)

Paramètres shop (réduction, admin Telegram, actif, etc.) dans Postgres (`config`, ligne `id=1`).

Import one-shot depuis un ancien `config.json` (optionnel) :

```bash
copy config.example.json config.json
# renseigner reduction / admin / balance / currency
python -m db.ensure_db
python -m db.seed_config --force
```

Ou en SQL direct :

```sql
UPDATE config SET
  reduction = 100,
  admin = 123456789,
  balance = 0,
  currency = 'EUR',
  actif = true
WHERE id = 1;
```

### 4. Créer la base + migrations

```bash
python -m db.ensure_db
```

Cette commande :

1. crée la base `kfc_perso` si elle n’existe pas  
2. applique les migrations SQL  
3. importe éventuellement un ancien `store_blacklist.json`  
4. importe éventuellement `config.json` → table `config` (si encore vide)

Migrations seules (si la base existe déjà) :

```bash
python -m db.migrate
```

---

## Deux modes : local + Cloudflare / cloud (Railway)

| | **Local** (`APP_ENV=local`) | **Cloud** (`APP_ENV=cloud` ou Railway) |
|--|--|--|
| Lancement | `python -m webapp.server` | `python -m webapp.boot && gunicorn -c gunicorn.conf.py webapp.wsgi:app` |
| Écoute | `127.0.0.1` | `0.0.0.0` |
| HTTPS | Tunnel Cloudflare | URL fournie par l’hébergeur |
| Postgres | `DB_*` (+ création auto de la base) | `DATABASE_URL` (migrate seulement) |
| Telegram | Poll (défaut) | Webhook (`TELEGRAM_WEBHOOK=1`) |
| Healthcheck | `GET /health` | `GET /health` |

`APP_ENV` est auto-détecté si des variables `RAILWAY_*` sont présentes.

---

## Lancer la webapp (local)

```bash
python -m webapp.server
```

Par défaut : [http://127.0.0.1:8080](http://127.0.0.1:8080)

Port personnalisé :

```bash
# Windows PowerShell
$env:PORT="9000"; python -m webapp.server

# Linux / macOS
PORT=9000 python -m webapp.server
```

### Telegram via Cloudflare (local)

1. `TELEGRAM_BOT_TOKEN` renseigné  
2. Exposer la webapp en HTTPS (voir dossier [`cloudflare/`](cloudflare/README.md))  
3. Coller l’URL HTTPS dans BotFather (Menu Button / Mini App)  
4. Ouvrir la Mini App **depuis Telegram** (le front envoie `X-Telegram-Init-Data`)

Sans `initData` valide → les routes `/api/*` répondent **401**.  
La config shop (`reduction`, `admin`, …) n’est **jamais** exposée au client ; bootstrap via `GET /api/me`.

Quick tunnel (test) :

```bat
REM Terminal 1
python -m webapp.server

REM Terminal 2 — double-clic ou :
cloudflare\start-quick.bat
```

### Cloud / Railway (gunicorn)

Start command (voir aussi `Procfile`) :

```bash
python -m webapp.boot && gunicorn -c gunicorn.conf.py webapp.wsgi:app
```

Variables typiques :

```env
APP_ENV=cloud
DATABASE_URL=postgresql://…
TELEGRAM_BOT_TOKEN=…
TELEGRAM_WEBHOOK=1
TELEGRAM_WEBHOOK_SECRET=…
```

Puis enregistrer le webhook Telegram vers  
`https://<votre-domaine>/telegram/webhook` (header secret).

---

## Commandes utiles

| Commande | Description |
|----------|-------------|
| `pip install -r requirements.txt` | Dépendances |
| `python -m db.ensure_db` | Crée DB (local) + migrations + seed config |
| `python -m db.migrate` | Migrations uniquement |
| `python -m webapp.boot` | Prep DB selon `APP_ENV` (create local / migrate cloud) |
| `python -m db.seed_config [--force]` | Import `config.json` → table `config` |
| `python -m webapp.server` | Mini-app web (Flask, local) |
| `gunicorn -c gunicorn.conf.py webapp.wsgi:app` | Mini-app cloud |

---

## Structure rapide

```text
KFCPerso/
├── config.example.json  # modele (optionnel pour seed)
├── config.json          # legacy local, import one-shot seulement
├── .env                 # Postgres + Telegram (local)
├── Procfile             # start cloud (Railway)
├── gunicorn.conf.py     # workers / bind cloud
├── webapp/              # Flask + auth Telegram + UI
├── cloudflare/          # tunnel HTTPS local
├── kfc/                 # catalogue public (restos + menu)
├── db/                  # Postgres (connection, repos, migrate)
└── migrations/          # SQL versionné
```

---

## Dépannage

| Symptôme | Piste |
|----------|--------|
| `Connexion PostgreSQL impossible` | Postgres démarré ? Mot de passe `.env` ? `python -m db.ensure_db` |
| `401 Authentification Telegram requise` | Ouvrir la Mini App depuis Telegram (initData) |
| `KFC indisponible` | Resto blacklisté |
| `Module KFC` / imports | Lancer les commandes **depuis** le dossier `KFCPerso` avec le venv activé |

---

## Rappel sécurité

- Ne commit **jamais** `.env` ni un `config.json` rempli
- En prod : HTTPS pour la Mini App ; ne jamais exposer la table `config` au client
