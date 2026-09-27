# Cloudflare Tunnel — URL publique pour la Mini App

Expose `http://127.0.0.1:8080` (Flask) en **HTTPS** accessible par Telegram.

Deux modes :

| Mode | Compte Cloudflare | URL | Usage |
|------|-------------------|-----|--------|
| **Quick** | Non | `https://….trycloudflare.com` (change à chaque lancement) | Test rapide |
| **Named** | Oui | Sous-domaine stable (`miniapp.tondomaine.com`) | Prod / BotFather |

---

## Prérequis

1. [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) installé
2. La webapp déjà lancée :

```bash
python -m webapp.server
```

Vérifier : [http://127.0.0.1:8080](http://127.0.0.1:8080)

---

## Mode Quick (recommandé pour commencer)

### Windows

Depuis la racine du projet `KFCPerso` (double-clic ou cmd) :

```bat
cloudflare\start-quick.bat
```

Ou manuellement :

```bat
cloudflared tunnel --url http://127.0.0.1:8080
```

### Linux / macOS

```bash
chmod +x cloudflare/start-quick.sh
./cloudflare/start-quick.sh
```

Dans les logs, récupère la ligne :

```text
https://xxxxx.trycloudflare.com
```

Cette URL est celle à coller dans BotFather / bouton Menu / lien Mini App.

---

## Brancher Telegram

1. Ouvre [@BotFather](https://t.me/BotFather)
2. `/mybots` → ton bot → **Bot Settings** → **Menu Button** → **Configure menu button**
3. URL = l’URL HTTPS Cloudflare (ex. `https://xxxxx.trycloudflare.com`)
4. Ou crée une Mini App : `/newapp` → URL = même HTTPS

Puis dans Telegram : ouvre le bot → bouton menu / ouvrir l’app  
(ou `/start` si tu as aussi un handler bot — pas inclus ici).

Dans `.env` :

```env
TELEGRAM_BOT_TOKEN=...   # token BotFather
ALLOW_DEV_AUTH=0         # en vrai usage Telegram
```

Redémarre `python -m webapp.server` après modification du `.env`.

---

## Mode Named (URL stable)

### 1. Login + tunnel

```bash
cloudflared tunnel login
cloudflared tunnel create kfc-perso
```

Note l’**Tunnel ID** affiché.

### 2. DNS

```bash
cloudflared tunnel route dns kfc-perso miniapp.tondomaine.com
```

### 3. Config locale

```bash
copy cloudflare\config.example.yml cloudflare\config.yml
```

Édite `cloudflare/config.yml` : `tunnel`, `credentials-file`, `hostname`.

Le fichier `config.yml` et les credentials restent **locaux** (voir `.gitignore`).

### 4. Lancer

```bat
cloudflare\start-named.bat
```

Ou :

```bat
cloudflared tunnel --config cloudflare\config.yml run
```

---

## Ordre de démarrage typique

```text
Terminal 1 :  python -m webapp.server
Terminal 2 :  cloudflare\start-quick.bat
Telegram   :  ouvrir la Mini App via l’URL HTTPS affichee
```

---

## Dépannage

| Problème | Piste |
|----------|--------|
| `cloudflared` introuvable | Installer le binaire et l’ajouter au `PATH` |
| `QUIC connection failed` / port **7844** / `hard_fail=true` | Un VPN (souvent **Mullvad**) bloque UDP/TCP 7844 vers Cloudflare. **Couper le VPN** (ou split-tunnel exclure `cloudflared`), puis relancer. `api.cloudflare.com:443` OK ne suffit pas. |
| Tunnel OK mais page blanche / erreur | Vérifier que Flask écoute bien sur `127.0.0.1:8080` |
| `401` dans la Mini App | `TELEGRAM_BOT_TOKEN` correct + ouverture **depuis** Telegram (`initData`) |
| URL trycloudflare change | Normal en mode Quick → repaster dans BotFather, ou passer en Named |
| Bot ne propose rien au `/start` | Le tunnel n’envoie pas de `/start` : configurer le **Menu Button** / Mini App BotFather |

---

## Fichiers

```text
cloudflare/
├── README.md              # ce guide
├── config.example.yml     # modele tunnel nomme
├── start-quick.bat        # Windows — URL trycloudflare (double-clic)
├── start-quick.ps1        # Windows PowerShell (optionnel)
├── start-quick.sh         # Linux/macOS
├── start-named.bat        # Windows — tunnel nomme
└── start-named.ps1        # Windows PowerShell (optionnel)
```
