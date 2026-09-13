"""
Requêtes bas-niveau vers l'API KFC.

IMPORTANT : aucun identifiant n'est codé en dur ici.
Les cookies et le jeton d'autorisation sont lus depuis la table Postgres
`config` (voir kfc/config.py).

Les valeurs BRAZE ci-dessous correspondent à la clé publique du SDK web
Braze utilisée par le site (télémétrie facultative, désactivée par défaut
via enable_analytics).
"""

import uuid

BRAZE_APIKEY = "a2efe7e4-929c-43f5-a085-7df8358ad687"
BRAZE_SESSIONID = str(uuid.uuid4())
BRAZE_DEVICEID = str(uuid.uuid4())
BRAZE_USERAPPID = str(uuid.uuid4())
