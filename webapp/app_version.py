"""Version applicative — increment automatique a chaque maj.

Regles (obligatoires pour l'agent) :
  - Toute modification de code → APP_VERSION += 0.01 (ex. 1.00 → 1.01)
  - Si l'utilisateur dit « maj principal » → APP_VERSION += 1 (ex. 1.05 → 2.05)
  - Format toujours ``X.YY`` (deux decimales), sans que l'utilisateur le rappelle.

Commande bot : /version (admin uniquement).
"""

from __future__ import annotations

# Version courante (reinitialisee a 1.00 sur demande utilisateur).
APP_VERSION = "1.00"
