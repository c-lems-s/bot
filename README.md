# KFCPerso — démarrage from scratch

Mini-app Telegram + CLI pour commander chez KFC France en points fidélité.

- **1 compte KFC** partagé (table Postgres `config`) pour tous les users
- **Accès web** via Telegram WebApp (auth `initData`)
- **PostgreSQL** : config, users, sessions, articles, blacklist, historique

---

## Prérequis

| Outil | Version conseillée | Rôle |
|-------|--------------------|------|
| Python | 3.10+ | Runtime |
| PostgreSQL | 14+ | Base de données |
| Compte KFC FR | session web valide | `account_id`, Bearer, cookies |
| Bot Telegram | token BotFather | Auth WebApp (prod) |

Optionnel en local : navigateur seul avec `ALLOW_DEV_AUTH=1` (sans Telegram).

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

# Prod Telegram
TELEGRAM_BOT_TOKEN=123456:ABC...
ALLOW_DEV_AUTH=0

# Dev local hors Telegram
# ALLOW_DEV_AUTH=1
```

PostgreSQL doit tourner et l’utilisateur doit pouvoir créer une base.

### 3. Compte KFC (table `config`)

Les secrets KFC vivent dans Postgres (`config`, ligne `id=1`), **pas** dans un fichier au runtime.

Import one-shot depuis un ancien `config.json` (optionnel) :

```bash
copy config.example.json config.json
# renseigner account_id / authorization / cookies
python -m db.ensure_db
python -m db.seed_config --force
```

Ou en SQL direct :

```sql
UPDATE config SET
  account_id = 'UUID…',
  auth_token = 'Bearer …',
  cookies = '{"XSRF-TOKEN":"…","refreshToken":"…"}'::jsonb,
  balance = 100.98,
  currency = 'EUR'
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

## Lancer la webapp

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

### Mode développement (sans Telegram)

Dans `.env` :

```env
ALLOW_DEV_AUTH=1
```

Les appels API acceptent alors un user fictif (header optionnel `X-Dev-Telegram-Id`).

### Mode production (Telegram)

1. `TELEGRAM_BOT_TOKEN` renseigné  
2. `ALLOW_DEV_AUTH=0`  
3. Exposer la webapp en HTTPS (voir dossier [`cloudflare/`](cloudflare/README.md))  
4. Coller l’URL HTTPS dans BotFather (Menu Button / Mini App)  
5. Ouvrir la Mini App **depuis Telegram** (le front envoie `X-Telegram-Init-Data`)

Quick tunnel (test) :

```bat
REM Terminal 1
python -m webapp.server

REM Terminal 2 — double-clic ou :
cloudflare\start-quick.bat
```

Sans `initData` valide → les routes `/api/*` répondent **401**.

---

## Lancer le CLI (admin / test mono-user)

Le CLI utilise la table `config` et Postgres (blacklist, historique).

```bash
python main.py
```

Parcours : recherche resto → articles fidélité → checkout → submit (reCAPTCHA bypass) → check-in.

---

## Commandes utiles

| Commande | Description |
|----------|-------------|
| `pip install -r requirements.txt` | Dépendances |
| `python -m db.ensure_db` | Crée DB + migrations + seed config |
| `python -m db.migrate` | Migrations uniquement |
| `python -m db.seed_config [--force]` | Import `config.json` → table `config` |
| `python -m webapp.server` | Mini-app web |
| `python main.py` | CLI commande |

---

## Structure rapide

```text
KFCPerso/
├── config.example.json  # modele (optionnel pour seed)
├── config.json          # legacy local, import one-shot seulement
├── .env                 # Postgres + Telegram (local)
├── main.py              # CLI
├── webapp/              # Flask + auth Telegram + UI
├── kfc/                 # métier + API KFC
├── db/                  # Postgres (connection, repos, migrate)
└── migrations/          # SQL versionné
```

---

## Dépannage

| Symptôme | Piste |
|----------|--------|
| `Connexion PostgreSQL impossible` | Postgres démarré ? Mot de passe `.env` ? `python -m db.ensure_db` |
| `401 Authentification Telegram requise` | Ouvrir via Telegram, ou `ALLOW_DEV_AUTH=1` en local |
| `account_id non renseigne` | Remplir table `config` ou `python -m db.seed_config --force` |
| `KFC indisponible` | Resto blacklisté (éligibilité fidélité &lt; 31 items) |
| Échec soumission / reCAPTCHA | Bypass auto + éventuel `recaptcha_token` dans table `config` |
| `Module KFC` / imports | Lancer les commandes **depuis** le dossier `KFCPerso` avec le venv activé |

---

## Rappel sécurité

- Ne commit **jamais** `.env` ni un `config.json` rempli
- En prod : `ALLOW_DEV_AUTH=0` et HTTPS pour la Mini App
- Un seul compte KFC sert tous les users (points / session partagés côté KFC)
