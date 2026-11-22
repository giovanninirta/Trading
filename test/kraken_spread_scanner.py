#!/usr/bin/env python3
"""
Scanner spread Kraken: trova le coppie dove il market making può coprire le commissioni.

Per ogni coppia in EUR calcola:
  - spread attuale (ask - bid) / prezzo medio
  - margine netto = spread - 2 x commissione maker (compri e vendi entrambi con ordini limite)
  - volume 24 h in EUR e numero di scambi 24 h
Ripete la misura N volte (lo spread di un istante non basta) e usa la mediana.

Uso:
  python kraken_spread_scanner.py                 # 5 campioni a 60 s
  python kraken_spread_scanner.py --samples 20 --every 180 --fee 0.004 --quote ZEUR
Solo dati pubblici, nessuna chiave API. Solo libreria standard Python.
"""
import argparse, json, time, statistics, urllib.request, csv
from datetime import datetime

API = "https://api.kraken.com/0/public/"

def get(path):
    with urllib.request.urlopen(API + path, timeout=30) as r:
        js = json.load(r)
    if js.get("error"):
        raise RuntimeError(js["error"])
    return js["result"]

def pairs_for(quote):
    res = get("AssetPairs")
    return {k: v["wsname"] for k, v in res.items()
            if v.get("quote") == quote and v.get("status", "online") == "online" and ".d" not in k}

def ticker(keys):
    out = {}
    for i in range(0, len(keys), 50):          # Kraken accetta più coppie per chiamata
        out.update(get("Ticker?pair=" + ",".join(keys[i:i + 50])))
        time.sleep(1)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quote", default="ZEUR", help="valuta di quotazione Kraken (ZEUR, ZUSD...)")
    ap.add_argument("--fee", type=float, default=0.0040, help="commissione maker (Tier 1 = 0.004)")
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--every", type=int, default=60, help="secondi tra i campioni")
    ap.add_argument("--min-vol", type=float, default=20000, help="volume 24h minimo in EUR")
    ap.add_argument("--min-trades", type=int, default=200, help="scambi 24h minimi")
    args = ap.parse_args()

    names = pairs_for(args.quote)
    keys = list(names)
    spreads = {k: [] for k in keys}
    last = {}
    for s in range(args.samples):
        t = ticker(keys)
        for k, v in t.items():
            bid, ask = float(v["b"][0]), float(v["a"][0])
            if bid > 0 and ask > 0:
                spreads.setdefault(k, []).append((ask - bid) / ((ask + bid) / 2))
                last[k] = v
        print(f"campione {s + 1}/{args.samples} preso alle {datetime.now():%H:%M:%S}")
        if s < args.samples - 1:
            time.sleep(args.every)

    rows = []
    for k, sp in spreads.items():
        if not sp or k not in last:
            continue
        v = last[k]
        vol_eur = float(v["v"][1]) * float(v["p"][1])     # volume base x vwap 24h
        trades = int(v["t"][1])
        med = statistics.median(sp)
        net = med - 2 * args.fee
        rows.append(dict(pair=names.get(k, k), spread=med, net=net, vol=vol_eur, trades=trades,
                         ok=net > 0.002 and vol_eur >= args.min_vol and trades >= args.min_trades))

    rows.sort(key=lambda r: (not r["ok"], -r["net"]))
    print(f"\nCommissione maker {args.fee*100:.2f} %  ->  serve spread > {2*args.fee*100:.2f} % solo per pareggiare")
    print(f"{'':2}{'Coppia':14}{'Spread':>9}{'Netto':>9}{'Vol 24h EUR':>14}{'Scambi':>9}")
    for r in rows[:40]:
        flag = "✅" if r["ok"] else "  "
        print(f"{flag}{r['pair']:14}{r['spread']*100:>8.2f}%{r['net']*100:>8.2f}%{r['vol']:>14,.0f}{r['trades']:>9}")

    with open("spread_scan.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"\n✅ = margine netto > 0,2 %, volume >= {args.min_vol:,.0f} EUR, scambi >= {args.min_trades}")
    print("Elenco completo salvato in spread_scan.csv")

if __name__ == "__main__":
    main()
