#!/usr/bin/env python3
"""
VERIFICA COPPIE - controlla su Kraken spot quali monete del bot sono negoziabili
in USDT, USD ed EUR, con il nome da usare nell'API e l'ordine minimo.
Solo dati pubblici, nessuna chiave API.
"""
import json, urllib.request

MONETE = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "LINK", "AVAX", "DOT",
          "BCH", "ATOM", "UNI", "XLM", "ETC", "FIL", "AAVE", "ALGO", "TRX", "NEAR",
          "APE", "SAND", "MANA", "AXS", "CRV", "COMP", "OP", "ARB", "INJ", "XTZ"]
ALIAS = {"BTC": {"XBT", "BTC", "XXBT"}, "DOGE": {"XDG", "DOGE", "XXDG"}}
VALUTE = {"USDT": {"USDT"}, "USD": {"USD", "ZUSD"}, "EUR": {"EUR", "ZEUR"}}

with urllib.request.urlopen("https://api.kraken.com/0/public/AssetPairs", timeout=30) as r:
    js = json.load(r)
if js.get("error"):
    raise SystemExit(f"Errore Kraken: {js['error']}")

trovate = {}
for chiave, p in js["result"].items():
    ws = p.get("wsname", "")
    if "/" not in ws or p.get("status", "online") != "online":
        continue
    base, quota = ws.split("/")
    for m in MONETE:
        if base in ALIAS.get(m, {m}):
            for v, nomi in VALUTE.items():
                if quota in nomi:
                    trovate[(m, v)] = (p["altname"], p.get("ordermin", "?"), p.get("costmin", "?"))

print(f"{'Moneta':8}{'USDT':>14}{'USD':>12}{'EUR':>12}   Ordine minimo (in monete / in valuta)")
manca_usdt = []
for m in MONETE:
    celle = []
    for v in VALUTE:
        x = trovate.get((m, v))
        celle.append(f"✅ {x[0]}" if x else "❌")
    rif = trovate.get((m, "USDT")) or trovate.get((m, "USD"))
    minimo = f"{rif[1]} / {rif[2]}" if rif else "-"
    if (m, "USDT") not in trovate: manca_usdt.append(m)
    print(f"{m:8}{celle[0]:>14}{celle[1]:>12}{celle[2]:>12}   {minimo}")
print(f"\nMonete senza coppia USDT: {', '.join(manca_usdt) if manca_usdt else 'nessuna'}")
