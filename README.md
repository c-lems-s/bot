# KFCPerso — démarrage from scratch

Mini-app Telegram pour commander chez KFC France (catalogue local + solde EUR).

- **Accès web** via Telegram WebApp (auth `initData`)
- **Bot** : `/start` (bienvenue + bouton « Accéder à la boutique »), `/actif` (admin)
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

### Cloud / Railway — démarche

Le repo est prêt (`Procfile`, `railway.toml`, gunicorn, `/health`).  
À faire une fois dans le dashboard Railway :

1. **New Project** → Deploy from GitHub (ce repo).  
   Déployez la branche qui contient le boot cloud (ex. PR `cursor/webapp-only-…`), pas un `main` sans `DATABASE_URL`.  
2. **Add Database** → **PostgreSQL** dans le **même projet** que le service web.  
3. **Variables** du service web :

| Variable | Valeur |
|----------|--------|
| `APP_ENV` | `cloud` (optionnel si `RAILWAY_*` détecté) |
| `TELEGRAM_BOT_TOKEN` | token BotFather |
| `TELEGRAM_WEBHOOK` | `1` |
| `TELEGRAM_WEBHOOK_SECRET` | longue chaîne aléatoire |
| `PUBLIC_BASE_URL` | `https://${{RAILWAY_PUBLIC_DOMAIN}}` (après Generate Domain) |
| `SET_WEBHOOK_ON_BOOT` | `1` (enregistre le webhook au démarrage) |
| `ADMIN_TELEGRAM_ID` | ton id Telegram numérique (seed `config.admin`) |
| `UPLOADS_ROOT` | `/data/uploads` (si volume monté, voir ci-dessous) |

#### Où est `DATABASE_URL` ?

Elle n’apparaît **pas** toute seule sur le service web. Elle est créée sur le service **Postgres**.

**A. Créer Postgres (si absent du canvas)**  
Canvas du projet → **+ Create** → **Database** → **Add PostgreSQL**.  
Tu dois voir **deux** boîtes : ton app **et** Postgres.

**B. Voir la valeur (sur Postgres)**  
Clique la boîte **Postgres** → onglet **Variables** → tu y vois `DATABASE_URL` (et souvent `DATABASE_PUBLIC_URL`, `PGHOST`, …).  
Ne copie pas forcément la valeur secrète dans le web — préfère une **référence**.

**C. L’injecter dans le service web (obligatoire)**  
1. Clique la boîte de **ton app** (pas Postgres) → **Variables**  
2. **New Variable** / **Raw Editor** et ajoute exactement :

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

Si ton service s’appelle autrement (ex. `PostgreSQL` ou `Postgres-abc`), adapte le nom :

```text
DATABASE_URL=${{PostgreSQL.DATABASE_URL}}
```

Le nom entre `${{…}}` = nom exact de la boîte Postgres sur le canvas (sensible à la casse).

Alternative UI : **Variables** → **Add Variable** → onglet / option **Add Reference** → choisir Postgres → `DATABASE_URL`.

3. **Deploy** / **Redeploy** le service web.

Sans ça, les logs montrent :

```text
[boot] APP_ENV=cloud
[-] Boot DB impossible : … localhost … port 5432 … Connection refused
```

Boot OK : `DATABASE_URL present (host=….railway.internal)` puis gunicorn.

4. **Domaine public + webhook Telegram** (sinon `URL manquante` au boot) :  
   - Service web → **Settings** → **Networking** → **Generate Domain**  
   - **Variables** → ajouter :
     ```text
     PUBLIC_BASE_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}
     SET_WEBHOOK_ON_BOOT=1
     TELEGRAM_WEBHOOK=1
     TELEGRAM_WEBHOOK_SECRET=<longue-chaine-aleatoire>
     ```
   - Redeploy → boot doit afficher `[+] Webhook OK`
5. **Volume uploads** (preuves paiement + photos notif) — sinon les fichiers disparaissent à chaque redeploy :  
   - Service web → **Volumes** → Add volume  
   - Mount path : `/data/uploads`  
   - Variable : `UPLOADS_ROOT=/data/uploads`  
6. Vérifier santé :  
   - `https://<domaine>/health` → `{"ok": true, "env": "cloud"}`  
   - `https://<domaine>/health?deep=1` → DB + uploads `writable`  
7. **BotFather** → Menu Button / Mini App → URL = le domaine généré (`https://….up.railway.app`).

Start manuel équivalent :

```bash
python -m webapp.boot && gunicorn -c gunicorn.conf.py webapp.wsgi:app
```

---

## Commandes utiles

| Commande | Description |
|----------|-------------|
| `pip install -r requirements.txt` | Dépendances |
| `python -m db.ensure_db` | Crée DB (local) + migrations + seed config |
| `python -m db.migrate` | Migrations uniquement |
| `python -m webapp.boot` | Prep DB selon `APP_ENV` (create local / migrate cloud) |
| `python -m db.seed_config [--force]` | Import `config.json` → table `config` |
| `python -m webapp.seed_admin_env` | Pose `config.admin` depuis `ADMIN_TELEGRAM_ID` |
| `python -m webapp.set_webhook` | Enregistre le webhook Telegram (`PUBLIC_BASE_URL`) |
| `python -m webapp.smoke_deploy [--deep]` | Smoke test post-deploy (`/health`, `/`, webhook) |
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
├── railway.toml         # build / healthcheck / start
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
| Railway : SSL / connection refused | `DATABASE_URL` lié ? `sslmode=require` ajouté auto en cloud |
| Railway : `localhost:5432 Connection refused` | Postgres non lié : Variables → Add Reference → `Postgres.DATABASE_URL` |
| Railway : healthcheck fail | `GET /health` doit répondre 200 |
| Preuves / photos perdues après deploy | Volume `/data/uploads` + `UPLOADS_ROOT=/data/uploads` |
| `/health?deep=1` uploads KO | Droits d’écriture sur le volume ; chemin `UPLOADS_ROOT` |
| Webhook Telegram KO | `PUBLIC_BASE_URL` https + `TELEGRAM_WEBHOOK_SECRET` ; `python -m webapp.set_webhook --info` |
| `401 Authentification Telegram requise` | Ouvrir la Mini App depuis Telegram (initData) |
| `KFC indisponible` | Resto blacklisté |
| `Module KFC` / imports | Lancer les commandes **depuis** le dossier `KFCPerso` avec le venv activé |

---

## Rappel sécurité

- Ne commit **jamais** `.env` ni un `config.json` rempli
- En prod : HTTPS pour la Mini App ; ne jamais exposer la table `config` au client
