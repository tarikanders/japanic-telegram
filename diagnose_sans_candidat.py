import sqlite3
from datetime import date, timedelta

c = sqlite3.connect(
    r"C:\Users\ssyon\Documents\CodeSpace\L3S6\JapanicTelegram\backend\japan_auctions.db"
).cursor()

# Cas hors-fenetre : lot existe en DB mais date APRES l'enchère (reuse)
# => la VRAIE annonce pour cette enchère n'est pas en DB
rows = c.execute(
    "select a.lot_number, a.model_raw, a.auction_date, l.posted_date, l.model_raw "
    "from auctions a join listings l on l.lot_number=a.lot_number "
    "where a.auction_date>='2025-01-01' and a.year is null and a.match_confidence is null "
    "and l.posted_date > a.auction_date "
    "limit 8"
).fetchall()
print("Lots dont l'annonce en DB est APRES l'enchere (lot reutilise, vraie annonce manquante):")
for lot, au_m, au_d, lst_d, lst_m in rows:
    print(f"  lot={lot} enchere={au_d} annonce_en_db={lst_d} | au:{au_m} -> lst:{lst_m}")

# Cas hors-fenetre cote oppose : annonce AVANT l'enchère mais >7j
rows2 = c.execute(
    "select a.lot_number, a.model_raw, a.auction_date, l.posted_date "
    "from auctions a join listings l on l.lot_number=a.lot_number "
    "where a.auction_date>='2025-01-01' and a.year is null and a.match_confidence is null "
    "and l.posted_date < a.auction_date "
    "and julianday(a.auction_date)-julianday(l.posted_date) > 7 "
    "limit 5"
).fetchall()
print("\nLots dont l'annonce est AVANT l'enchere mais >7j (fenetre trop courte):")
for lot, au_m, au_d, lst_d in rows2:
    gap = (date.fromisoformat(au_d) - date.fromisoformat(lst_d)).days
    print(f"  lot={lot} model={au_m} enchere={au_d} annonce={lst_d} gap={gap}j")

# Quelle est la vraie distribution des gaps pour les lots MATCHES (high) ?
print("\nDistribution gap (jours) pour les lots MATCHES (high) en 2025+:")
gaps = c.execute(
    "select julianday(a.auction_date)-julianday(l.posted_date) as gap "
    "from auctions a join listings l on l.id=a.matched_listing_id "
    "where a.auction_date>='2025-01-01' and a.match_confidence='high' and l.posted_date is not null"
).fetchall()
from collections import Counter
gcnt = Counter(int(g[0]) for g in gaps if g[0] is not None)
for d in sorted(gcnt):
    bar = '#' * (gcnt[d] // 20)
    print(f"  {d}j: {gcnt[d]:4d} {bar}")

# Nombre de sans-candidat ou l'annonce n'existe PAS DU TOUT dans le canal
# (aucun listing avec ce lot, ni avant ni apres)
no_lot = c.execute(
    "select count(*) from auctions a "
    "where a.auction_date>='2025-01-01' and a.year is null and a.match_confidence is null "
    "and not exists (select 1 from listings l where l.lot_number=a.lot_number)"
).fetchone()[0]
print(f"\nLots INTROUVABLES en DB (vraie annonce jamais scraped ou jamais postee): {no_lot}")

# Dernier msg_id des listings pour savoir si le scrape couvre bien toute la periode
last_lst = c.execute("select max(telegram_message_id) from listings").fetchone()[0]
last_au  = c.execute("select max(telegram_message_id) from auctions where auction_date>='2025-01-01'").fetchone()[0]
print(f"Max msg_id listings: {last_lst}  |  Max msg_id auctions 2025+: {last_au}")

# Sessions 2025 avec des sans-candidat : combien d'annonces attendues vs presentes
print("\nEx. sessions 2025 avec sans-candidats (nb resultats vs nb annonces matchees):")
sessions = c.execute(
    "select auction_date, count(*) as nb_au, "
    "sum(case when year is not null then 1 else 0 end) as nb_matched "
    "from auctions where auction_date>='2025-01-01' "
    "group by auction_date having nb_au > nb_matched "
    "order by auction_date limit 5"
).fetchall()
for dt, nb, nm in sessions:
    nm = nm or 0
    # compter les annonces dans les 7j precedents
    d_min = (date.fromisoformat(dt) - timedelta(days=7)).isoformat()
    nb_lst = c.execute(
        "select count(*) from listings where posted_date<=? and posted_date>=?",
        (dt, d_min)
    ).fetchone()[0]
    print(f"  {dt}: {nm}/{nb} matchees | {nb_lst} annonces en DB dans les 7j")
