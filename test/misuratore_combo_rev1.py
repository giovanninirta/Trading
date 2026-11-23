#!/usr/bin/env python3
"""
MISURATORE COMBINATO - Rev 1
Candele da 4 ore, 30 monete, perpetui Kraken, solo long, quota fissa per moneta, niente leva.
Costo 0,07 % per ordine + funding stimato 0,01 % ogni 8 ore sulle posizioni aperte (a carico del long).

1) ROBUSTEZZA DELLE BANDE: compra sotto la banda inferiore (media N - K deviazioni), vende al ritorno
   alla media o dopo N candele. N = 10, 20, 40 candele; K = 2, 2,5, 3. Con e senza filtro di trend
   (compra solo se il prezzo e' sopra la media a 200 candele).
2) PORTAFOGLIO COMBINATO: meta' capitale al trend (Canale 55/13) e meta' alle Bande (20 candele, 2,5
   deviazioni, senza filtro: la variante scelta PRIMA di questo test). Ribilanciato di continuo.
   Risultato anno per anno.

Uso (nella cartella dati):  python ../misuratore_combo_rev1.py
Solo libreria standard Python 3.8+.
"""
import csv, json, math, os, sys, time, urllib.request

MONETE = ("XBT ETH SOL XRP ADA DOGE LTC LINK AVAX DOT BCH ATOM UNI XLM ETC FIL AAVE ALGO TRX NEAR "
          "APE SAND MANA AXS CRV COMP OP ARB INJ XTZ").split()
API = "https://futures.kraken.com/api/charts/v1/trade/{sym}/1h?from={a}&to={b}"
COSTO, FUNDING, H = 0.0007, 0.00005, 4          # funding per candela da 4 ore
PER_ANNO = 365 * 24 / H
INIZIO = 200

def scarica(sym, path):
    fine = int(time.time()); t = fine - int(4.5 * 365 * 86400); righe = {}
    while t < fine:
        try:
            with urllib.request.urlopen(API.format(sym=sym, a=t, b=min(t + 1500 * 3600, fine)), timeout=30) as r:
                js = json.load(r)
        except Exception as e:
            print(f"{sym}: non scaricabile ({e})"); return False
        for c in js.get("candles", []):
            ts = int(c["time"]) // 1000
            righe[ts] = (ts, c["open"], c["high"], c["low"], c["close"])
        t += 1500 * 3600; time.sleep(0.3)
    if len(righe) < 24 * 200: return False
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows([righe[k] for k in sorted(righe)][:-1])
    return True

def carica(m):
    sym = f"PF_{m}USD"; path = f"{sym}_1h.csv"
    if not os.path.exists(path) and not scarica(sym, path): return None
    out = {}
    with open(path) as f:
        for r in csv.reader(f):
            try:
                ts = int(float(r[0]))
                if ts % (H * 3600) == 0: out[ts] = float(r[4])
            except (ValueError, IndexError): pass
    return out

def ok(c, t, n): return t >= n and all(x is not None for x in c[t - n:t + 1])

def bande(c, N, K, filtro):
    n = len(c); v = [1.0] * n; e = 1.0; pos = 0; ingresso = 0
    for t in range(1, n):
        if c[t] is None or c[t - 1] is None: v[t] = e; continue
        if pos: e *= c[t] / c[t - 1] * (1 - FUNDING)
        if ok(c, t, max(N, 200)):
            w = c[t - N + 1:t + 1]; m = sum(w) / N; sd = math.sqrt(sum((x - m) ** 2 for x in w) / N)
            if pos and (c[t] >= m or t - ingresso >= N):
                e *= 1 - COSTO; pos = 0
            elif not pos and c[t] < m - K * sd and (not filtro or c[t] > sum(c[t - 200:t]) / 200):
                e *= 1 - COSTO; pos = 1; ingresso = t
        v[t] = e
    return v

def trend(c, n_in=55, n_out=13):
    n = len(c); v = [1.0] * n; e = 1.0; pos = 0
    for t in range(1, n):
        if c[t] is None or c[t - 1] is None: v[t] = e; continue
        if pos: e *= c[t] / c[t - 1] * (1 - FUNDING)
        if ok(c, t, n_in):
            if not pos and c[t] > max(c[t - n_in:t]): e *= 1 - COSTO; pos = 1
            elif pos and c[t] < min(c[t - n_out:t]): e *= 1 - COSTO; pos = 0
        v[t] = e
    return v

def portafoglio(C, f):
    n = len(next(iter(C.values()))); s = [0.0] * n
    for c in C.values():
        for t, x in enumerate(f(c)): s[t] += x
    return [x / len(C) for x in s]

def rendimenti(v): return [0.0] + [v[t] / v[t - 1] - 1 for t in range(1, len(v))]

def valori(r):
    v = [1.0]
    for g in r[1:]: v.append(v[-1] * (1 + g))
    return v

def stat(v):
    picco, calo = v[0], 0.0
    for x in v: picco = max(picco, x); calo = min(calo, x / picco - 1)
    return (v[-1] / v[0]) ** (PER_ANNO / max(len(v) - 1, 1)) - 1, calo

def main():
    dati = {}
    for m in MONETE:
        d = carica(m)
        if d: dati[m] = d
    if "XBT" not in dati: sys.exit("Mancano i dati di BTC.")
    tempi = sorted(dati["XBT"])
    C = {m: [d.get(t) for t in tempi] for m, d in dati.items()}
    n = len(tempi); taglio = INIZIO + int((n - INIZIO) * 0.6)
    data = lambda i: time.strftime("%Y-%m-%d", time.gmtime(tempi[i]))
    print(f"\n{len(C)} monete, candele da 4 ore, dal {data(INIZIO)} al {data(n - 1)}. Prova fino al {data(taglio)}.\n")
    fmt = lambda x: f"{x[0] * 100:+.0f}%/{x[1] * 100:.0f}%"
    num = lambda x: f"x{x:.2f}".replace(".", ",")
    periodi = lambda v: (stat(v[INIZIO:taglio + 1]), stat(v[taglio:]), v[-1] / v[INIZIO])

    # 1) robustezza
    print("1) ROBUSTEZZA DELLE BANDE (rendimento annuo / calo massimo)")
    print(f"{'':3}{'Finestra / soglia':22}{'--------- senza filtro di trend ---------':>44}   {'---------- con filtro di trend ----------':>44}")
    print(f"{'':25}{'Prova':>15}{'Verifica':>15}{'Capitale':>11}      {'Prova':>15}{'Verifica':>15}{'Capitale':>11}")
    verdi = tot = 0
    for N in (10, 20, 40):
        for K in (2.0, 2.5, 3.0):
            celle, sem = [], ""
            for filtro in (False, True):
                p, q, cap = periodi(portafoglio(C, lambda c: bande(c, N, K, filtro)))
                s = "🟢" if p[0] > 0 and q[0] > 0 else "🔴"
                verdi += s == "🟢"; tot += 1
                celle.append(f"{s}{fmt(p):>13}{fmt(q):>15}{num(cap):>11}")
            print(f"   {f'{N} candele, {K:.1f} dev'.replace('.', ','):22}{celle[0]:>44}   {celle[1]:>44}")
    print(f"   Varianti in guadagno in entrambi i periodi: {verdi} su {tot}\n")

    # 2) combinato
    tenere = [1.0] * n
    for t in range(1, n):
        g = [c[t] / c[t - 1] - 1 for c in C.values() if c[t] and c[t - 1]]
        tenere[t] = tenere[t - 1] * (1 + sum(g) / len(C))
    v_t = portafoglio(C, trend); v_b = portafoglio(C, lambda c: bande(c, 20, 2.5, False))
    r_t, r_b = rendimenti(v_t), rendimenti(v_b)
    v_c = valori([0.5 * a + 0.5 * b for a, b in zip(r_t, r_b)])
    serie = [("Tenere le monete", tenere), ("Trend 55/13", v_t), ("Bande 20 / 2,5", v_b), ("COMBINATO 50 / 50", v_c)]

    print("2) PORTAFOGLIO COMBINATO")
    print(f"{'':3}{'':22}{'Prova':>15}{'Verifica':>15}{'Capitale':>11}")
    for nome, v in serie:
        p, q, cap = periodi(v)
        print(f"   {nome:22}{fmt(p):>15}{fmt(q):>15}{num(cap):>11}")

    # legame tra trend e bande (rendimenti mensili)
    mesi = {}
    for t in range(INIZIO + 1, n):
        g = time.gmtime(tempi[t]); k = (g.tm_year, g.tm_mon)
        a, b = mesi.get(k, (1.0, 1.0)); mesi[k] = (a * (1 + r_t[t]), b * (1 + r_b[t]))
    x = [a - 1 for a, _ in mesi.values()]; y = [b - 1 for _, b in mesi.values()]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    corr = sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    print(f"\n   Legame tra i mesi del trend e delle bande: {corr:+.2f}   (+1 vanno insieme, 0 indipendenti, -1 opposti)")

    print("\nANNO PER ANNO")
    anni = sorted({time.gmtime(tempi[t]).tm_year for t in range(INIZIO, n)})
    print(f"{'':3}{'':22}" + "".join(f"{a:>9}" for a in anni))
    for nome, v in serie:
        celle = []
        for a in anni:
            idx = [t for t in range(INIZIO, n) if time.gmtime(tempi[t]).tm_year == a]
            g = v[idx[-1]] / v[max(idx[0] - 1, INIZIO)] - 1
            celle.append(f"{'▲' if g > 0 else '▼'}{g * 100:+.0f}%")
        print(f"   {nome:22}" + "".join(f"{c:>9}" for c in celle))
    print("""
Caselle: rendimento annuo / calo massimo dal picco.   Capitale: quante volte il capitale iniziale.
🟢 guadagna sia in prova sia in verifica   🔴 perde in almeno un periodo.   Il primo e l'ultimo anno sono parziali.
Le bande sono robuste se il verde copre la maggior parte delle varianti vicine, non una sola.""")

if __name__ == "__main__":
    main()
