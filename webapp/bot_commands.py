"""Menu de commandes Telegram (setMyCommands) — public vs admin.

Usage :
    python -m webapp.bot_commands
    python -m webapp.bot_commands --show

Scopes :
  - default / all users : uniquement /start
  - chat admin          : /start + /actif (jamais propose aux users)
"""

from __future__ import annotations

import argparse
import logging
from typing import Any, Dict, List

from webapp import telegram as tg

log = logging.getLogger(__name__)

# Commandes visibles par TOUS les utilisateurs (pas d'admin ici).
PUBLIC_COMMANDS: List[Dict[str, str]] = [
    {
        "command": "start",
        "description": "Bienvenue et accès à la boutique",
    },
]

# Commandes reservees a l'admin (scope chat = id Telegram admin).
ADMIN_ONLY_COMMANDS: List[Dict[str, str]] = [
    {
        "command": "actif",
        "description": "Ouvrir ou fermer le shop (admin)",
    },
]


def admin_commands() -> List[Dict[str, str]]:
    """Liste complete pour le chat prive admin (/start + /actif)."""
    return [*PUBLIC_COMMANDS, *ADMIN_ONLY_COMMANDS]


def sync_bot_commands() -> bool:
    """Pose le menu public + menu admin (si config.admin connu).

    Retourne True si le scope public a bien ete enregistre.
    """
    if not tg.bot_token():
        log.warning("TELEGRAM_BOT_TOKEN manquant — menu commandes ignore")
        return False

    # 1) Menu public : /start uniquement
    ok = tg.set_my_commands(PUBLIC_COMMANDS, scope={"type": "default"})
    if ok is None:
        log.error("setMyCommands (default) echoue")
        return False

    # 2) Nettoyer les scopes larges (evite qu'un ancien menu admin fuite)
    for scope_type in ("all_private_chats", "all_group_chats", "all_chat_administrators"):
        tg.delete_my_commands(scope={"type": scope_type})

    # 3) Menu admin uniquement dans le chat prive admin
    try:
        from kfc.config import get_admin

        admin_id = get_admin()
    except Exception:
        log.exception("get_admin impossible — menu admin ignore")
        admin_id = None

    if admin_id is not None:
        admin_ok = tg.set_my_commands(
            admin_commands(),
            scope={"type": "chat", "chat_id": int(admin_id)},
        )
        if admin_ok is None:
            log.error("setMyCommands (admin chat=%s) echoue", admin_id)
        else:
            log.info(
                "Menu commandes : public=/start ; admin=%s → /start,/actif",
                admin_id,
            )
    else:
        log.info("Menu commandes : public=/start (pas d'admin configure)")

    return True


def _print_commands(label: str, scope: Dict[str, Any]) -> None:
    cmds = tg.get_my_commands(scope=scope)
    print(f"[{label}] {scope}")
    if cmds is None:
        print("  (echec getMyCommands)")
        return
    if not cmds:
        print("  (vide)")
        return
    for c in cmds:
        print(f"  /{c.get('command')} — {c.get('description')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Menu commandes Telegram")
    parser.add_argument(
        "--show",
        action="store_true",
        help="Affiche les menus enregistres (sans reecrire)",
    )
    args = parser.parse_args(argv)

    if not tg.bot_token():
        print("[-] TELEGRAM_BOT_TOKEN manquant")
        return 1

    if args.show:
        _print_commands("default", {"type": "default"})
        try:
            from kfc.config import get_admin

            admin_id = get_admin()
        except Exception:
            admin_id = None
        if admin_id is not None:
            _print_commands("admin", {"type": "chat", "chat_id": int(admin_id)})
        return 0

    if not sync_bot_commands():
        print("[-] Sync menu commandes echouee")
        return 1
    print("[+] Menu commandes Telegram OK")
    print("    Users  : /start")
    print("    Admin  : /start, /actif (scope chat admin uniquement)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
