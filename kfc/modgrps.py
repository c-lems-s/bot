"""Construction des modificateurs (modgrps) d'un produit : boisson, frite, sauce, etc."""


def select_n(group: dict):
    """Sélection quand on peut choisir plusieurs modificateurs (CLI)."""
    print(f"\n=== {group['name']} ===")
    modifiers = group["modifiers"]

    for index, mod in enumerate(modifiers):
        print(f"{index + 1}. {mod['name']}")

    choice = []
    for i in range(group["max"]):
        choice_i = int(input(f"Choix {i + 1} : ")) - 1
        choice.append(choice_i)

    for mod in modifiers:
        mod["qty"] = 0

    for choice_i in choice:
        modifiers[choice_i]["qty"] += 1

    return choice


def select_group(group: dict):
    """Sélection d'un seul modificateur (CLI), avec récursion sur les sous-groupes."""
    print(f"\n=== {group['name']} ===")
    modifiers = group["modifiers"]

    for index, mod in enumerate(modifiers):
        print(f"{index + 1}. {mod['name']}")

    choice = int(input("Select option: ")) - 1

    for mod in modifiers:
        mod["qty"] = 0

    selected = modifiers[choice]
    selected["qty"] = group["max"]

    for nested_group in selected["modgrps"]:
        choose(nested_group)

    return choice


def choose(group):
    if group["max"] > 1:
        select_n(group)
    else:
        select_group(group)


def build_modifier(node):
    modifier = {
        "id": node["id"],
        "unitPrice": node["price"],
        "quantity": node["qty"],
    }
    if node["modgrps"]:
        modifier["modgrps"] = [build_modgrp(mg) for mg in node["modgrps"]]
    return modifier


def build_modgrp(group):
    return {
        "id": group["id"],
        "modifiers": [build_modifier(mod) for mod in group["modifiers"] if mod["qty"] > 0],
    }


def ChooseModifications(modgrps: list) -> list:
    """Construit la liste des modgrps sélectionnés pour un produit (CLI)."""
    for group in modgrps:
        choose(group)

    return [build_modgrp(group) for group in modgrps]
