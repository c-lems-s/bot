"""Seed / resync table article depuis le catalogue LOYALTY_PRODUCTS.

Usage (depuis KFCPerso) :
    python -m db.seed_articles
"""

from __future__ import annotations

from db.connection import get_cursor

# Catalogue manuel (price / label / name / cost pts).
LOYALTY_PRODUCTS = {
    "loyalty-3623": {
        "price": 1,
        "label": "édition spécial",
        "name": "Kentucky curly fries",
        "cost": 300,
        "categorie": "PETIT CREUX",
    },
    "loyalty-3631": {
        "price": 1,
        "label": "édition spécial",
        "name": "Sauce banane XL",
        "cost": 300,
        "categorie": "PETIT CREUX",
    },
    "loyalty-9000": {
        "price": 4.95,
        "label": "enfant",
        "name": "Menu enfant : P'tit Bucket",
        "cost": 800,
        "categorie": "MENUS CRISPY",
    },
    "loyalty-2385": {
        "price": 3.20,
        "label": "Accompagnements",
        "name": "Moyennes Frites",
        "cost": 150,
        "categorie": "BONS PLANS",
    },
    "loyalty-2383": {
        "price": 2.20,
        "label": "Accompagnements",
        "name": "Cobette® épi de maïs",
        "cost": 150,
        "categorie": "BONS PLANS",
    },
    "loyalty-3485": {
        "price": 2.95,
        "label": "Accompagnements",
        "name": "3 Crousti' Fromage Mozarella",
        "cost": 150,
        "categorie": "BONS PLANS",
    },
    "loyalty-3484": {
        "price": 2.95,
        "label": "Accompagnements",
        "name": "Crousti Fromage Raclette x3",
        "cost": 150,
        "categorie": "BONS PLANS",
    },
    "loyalty-3487": {
        "price": 2.95,
        "label": "Accompagnements",
        "name": "The Onion Rings X5",
        "cost": 150,
        "categorie": "BONS PLANS",
    },
    "loyalty-2368": {
        "price": 4.10,
        "label": "Accompagnements",
        "name": "Kentucky® Fries",
        "cost": 300,
        "categorie": "PETIT CREUX",
    },
    "loyalty-3482": {
        "price": 3.95,
        "label": "Accompagnements",
        "name": "2 Tenders",
        "cost": 300,
        "categorie": "PETIT CREUX",
    },
    "loyalty-3481": {
        "price": 3.95,
        "label": "Accompagnements",
        "name": "3 Hot Wings",
        "cost": 300,
        "categorie": "PETIT CREUX",
    },
    "loyalty-2403": {
        "price": 2.00,
        "label": "boisson",
        "name": "Thé",
        "cost": 150,
        "categorie": "BONS PLANS",
    },
    "loyalty-2397": {
        "price": 1.60,
        "label": "boisson",
        "name": "Espresso",
        "cost": 150,
        "categorie": "BONS PLANS",
    },
    "loyalty-2396": {
        "price": 3.00,
        "label": "boisson",
        "name": "Double Espresso",
        "cost": 150,
        "categorie": "BONS PLANS",
    },
    "loyalty-2323": {
        "price": 3.95,
        "label": "glace",
        "name": "Crousti'Kream Fraise",
        "cost": 600,
        "categorie": "GOURMANDISES",
    },
    "loyalty-2321": {
        "price": 3.95,
        "label": "glace",
        "name": "Crousti'Kream Snickers®",
        "cost": 600,
        "categorie": "GOURMANDISES",
    },
    "loyalty-3440": {
        "price": 3.95,
        "label": "glace",
        "name": "Crousti'Kream Nutella®",
        "cost": 600,
        "categorie": "GOURMANDISES",
    },
    "loyalty-2516": {
        "price": 2.30,
        "label": "glace",
        "name": "Sundae Chocolat Noisette",
        "cost": 300,
        "categorie": "PETIT CREUX",
    },
    "loyalty-3441": {
        "price": 2.30,
        "label": "glace",
        "name": "Sundae Caramel",
        "cost": 300,
        "categorie": "PETIT CREUX",
    },
    "loyalty-2697": {
        "price": 2.95,
        "label": "gateau",
        "name": "Cookie Double Choco",
        "cost": 600,
        "categorie": "GOURMANDISES",
    },
    "loyalty-3289": {
        "price": 3.60,
        "label": "gateau",
        "name": "Muffin Fondant Noisette",
        "cost": 600,
        "categorie": "GOURMANDISES",
    },
    "loyalty-3472": {
        "price": 3.95,
        "label": "burger",
        "name": "Crispy Burger Chicken",
        "cost": 600,
        "categorie": "GOURMANDISES",
    },
    "loyalty-3473": {
        "price": 3.95,
        "label": "burger",
        "name": "Crispy Burger Fish",
        "cost": 600,
        "categorie": "GOURMANDISES",
    },
    "loyalty-1278": {
        "price": 11.95,
        "label": "burger",
        "name": "Menu Kentucky® BBQ & Bacon",
        "cost": 1000,
        "categorie": "MEGA DEALS",
    },
    "loyalty-1279": {
        "price": 13.15,
        "label": "burger",
        "name": "Menu Double Kentucky Burger",
        "cost": 1000,
        "categorie": "MEGA DEALS",
    },
    "loyalty-1670": {
        "price": 11.45,
        "label": "burger",
        "name": "Menu Crispy Naan Creamy & Cheese",
        "cost": 1000,
        "categorie": "MEGA DEALS",
    },
    "loyalty-1675": {
        "price": 11.45,
        "label": "burger",
        "name": "Menu Crispy Spicy Naan Tikka",
        "cost": 1000,
        "categorie": "MEGA DEALS",
    },
    "loyalty-1259": {
        "price": 9.25,
        "label": "burger",
        "name": "Menu Colonel Original Veggie",
        "cost": 800,
        "categorie": "MENUS CRISPY",
    },
    "loyalty-1162": {
        "price": 10.85,
        "label": "burger",
        "name": "Menu Tower® Cheese & Bacon",
        "cost": 800,
        "categorie": "MENUS CRISPY",
    },
    "loyalty-1254": {
        "price": 9.25,
        "label": "burger",
        "name": "Menu Colonel® Original",
        "cost": 800,
        "categorie": "MENUS CRISPY",
    },
    "loyalty-3478": {
        "price": 2.50,
        "label": "burger",
        "name": "Krunchy®",
        "cost": 300,
        "categorie": "PETIT CREUX",
    },
    "loyalty-2335": {
        "price": 17.45,
        "label": "bucket",
        "name": "Bucket 10 Tenders®",
        "cost": 1000,
        "categorie": "MEGA DEALS",
    },
    "loyalty-2337": {
        "price": 17.45,
        "label": "bucket",
        "name": "Bucket 16 Hot Wings®",
        "cost": 1000,
        "categorie": "MEGA DEALS",
    },
    "loyalty-2405": {
        "price": 17.45,
        "label": "bucket",
        "name": "Bucket 7 Tenders® + 7 Hot Wings®",
        "cost": 1000,
        "categorie": "MEGA DEALS",
    },
    "loyalty-2302": {
        "price": 9.95,
        "label": "bucket",
        "name": "Menu 5 Tenders®",
        "cost": 800,
        "categorie": "MENUS CRISPY",
    },
    "loyalty-2103": {
        "price": 9.95,
        "label": "bucket",
        "name": "Menu 8 Hot Wings®",
        "cost": 800,
        "categorie": "MENUS CRISPY",
    },
    "loyalty-1050": {
        "price": 9.95,
        "label": "wrap",
        "name": "Menu Boxmaster® Original",
        "cost": 800,
        "categorie": "MENUS CRISPY",
    },
    "loyalty-1051": {
        "price": 9.95,
        "label": "wrap",
        "name": "Menu Boxmaster® Spicy",
        "cost": 800,
        "categorie": "MENUS CRISPY",
    },
    "loyalty-3470": {
        "price": 2.70,
        "label": "wrap",
        "name": "iTWIST®",
        "cost": 300,
        "categorie": "PETIT CREUX",
    },
}


def seed_articles() -> int:
    n = 0
    with get_cursor() as cur:
        for kid, meta in LOYALTY_PRODUCTS.items():
            cost = meta.get("cost")
            try:
                cost_i = int(cost) if cost is not None else None
            except (TypeError, ValueError):
                cost_i = None
            cur.execute(
                """
                INSERT INTO article (kfc_item_id, name, label, price, cost, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (kfc_item_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    label = EXCLUDED.label,
                    price = EXCLUDED.price,
                    cost = EXCLUDED.cost,
                    updated_at = NOW()
                """,
                (kid, meta["name"], meta["label"], float(meta["price"]), cost_i),
            )
            n += 1
        cur.execute("SELECT COUNT(*) AS c FROM article")
        total = int(cur.fetchone()["c"])
    print(f"[seed_articles] upsert {n} lignes — total table article = {total}")
    return n


if __name__ == "__main__":
    seed_articles()
