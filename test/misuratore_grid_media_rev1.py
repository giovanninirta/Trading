#!/usr/bin/env python3
"""
MISURATORE GRID E RITORNO ALLA MEDIA - Rev 1
30 monete, perpetui Kraken (dati 1 ora), una quota fissa per moneta, niente leva, solo long.

A) RITORNO ALLA MEDIA BREVE (candele da 4 ore, costo 0,07 % per ordine)
   RSI 2        compra quando l'RSI a 2 candele scende sotto 10 (crollo improvviso);
                vende quando il prezzo torna sopra la media a 5 candele, o dopo 10 candele
   Bande        compra sotto la banda inferiore (media 20 - 2,5 deviazioni);
                vende al ritorno alla media a 20, o dopo 20 candele
   Ognuna con e senza filtro di trend (compra solo se il prezzo e' sopra la media a 200 candele).

B) GRID (candele da 1 ora, ordini limite: costo 0,04 % per ordine)
   Griglia di 10 livelli sotto il prezzo di partenza, distanti G % l'uno dall'altro.
   Ogni livello toccato compra 1/10 della quota della moneta; ogni acquisto si rivende G % piu' in alto.
   Quando tutti i livelli sono venduti e il prezzo sale oltre la griglia, la griglia si sposta in alto.
   Se il prezzo scende sotto l'ultimo livello, il bot resta con le monete comprate in perdita.
   Varianti: G = 1 %, 2 %, 4 %.

Non incluso: funding dei perpetui. Prezzi di chiusura delle candele.
Uso (nella cartella dati):  python ../misuratore_grid_media_rev1.py
Solo libreria standard Python 3.8+.
"""
import csv, json, math, os, sys, time, urllib.request

MONETE = ("XBT ETH SOL XRP ADA DOGE LTC LINK AVAX DOT BCH ATOM UNI XLM ETC FIL AAVE ALGO TRX NEAR "
          "APE SAND MANA AXS CRV COMP OP ARB INJ XTZ").split()
API = "https://futures.kraken.com/api/charts/v1/trade/{sym}/1h?from={a}&to={b}"
COSTO_MEDIA, COSTO_GRID = 0.0007, 0.0004

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
            try: out[int(float(r[0]))] = float(r[4])
            except (ValueError, IndexError): pass
    return out

# ------------------------- STRATEGIE PER UNA MONETA -------------------------
# ognuna riceve la serie dei prezzi (None dove manca) e ritorna (valore della quota per candela, operazioni)
def rsi2_serie(c):
    out = [None] * len(c); su = giu = None
    for t in range(1, len(c)):
        if c[t] is None or c[t - 1] is None: su = giu = None; continue
        d = c[t] - c[t - 1]
        u, g = max(d, 0), max(-d, 0)
        su = u if su is None else (su + u) / 2
        giu = g if giu is None else (giu + g) / 2
        out[t] = 100.0 if giu == 0 else 100 - 100 / (1 + su / giu)
    return out

def media_breve(c, tipo, filtro):
    n = len(c); v = [1.0] * n; e = 1.0; pos = 0; entrata = 0; ops = []; e_in = 1.0
    rsi = rsi2_serie(c) if tipo == "rsi" else None
    for t in range(1, n):
        if c[t] is None or c[t - 1] is None: v[t] = e; continue
        if pos: e *= c[t] / c[t - 1]
        finestra_ok = t >= 200 and all(x is not None for x in c[t - 200:t + 1])
        if not finestra_ok:
            v[t] = e; continue
        tendenza = c[t] > sum(c[t - 200:t]) / 200
        if tipo == "rsi":
            m5 = sum(c[t - 4:t + 1]) / 5
            entra = rsi[t] is not None and rsi[t] < 10
            esci = c[t] > m5 or t - entrata >= 10
        else:
            w = c[t - 19:t + 1]; m = sum(w) / 20; sd = math.sqrt(sum((x - m) ** 2 for x in w) / 20)
            entra = c[t] < m - 2.5 * sd
            esci = c[t] >= m or t - entrata >= 20
        if pos and esci:
            e *= 1 - COSTO_MEDIA; ops.append(e / e_in - 1); pos = 0
        elif not pos and entra and (tendenza or not filtro):
            e *= 1 - COSTO_MEDIA; e_in = e; pos = 1; entrata = t
        v[t] = e
    return v, ops

def grid(c, G, livelli=10):
    n = len(c); v = [1.0] * n
    cassa = 1.0; unita = 1.0 / livelli; tenute = {}; ancora = None; ops = []
    for t in range(n):
        p = c[t]
        if p is None:
            v[t] = cassa + sum(q * (c[t - 1] or 0) for q, _ in tenute.values()) if t else 1.0; continue
        if ancora is None: ancora = p
        livello = lambda k: ancora * (1 - G) ** k
        # vendite: ogni unita' comprata al livello k si rivende al livello k-1
        for k in sorted(tenute):
            if p >= livello(k - 1):
                q, costo = tenute.pop(k)
                incasso = q * livello(k - 1) * (1 - COSTO_GRID); cassa += incasso; ops.append(incasso / costo - 1)
        # acquisti: livelli toccati e non ancora tenuti
        for k in range(1, livelli + 1):
            if livello(k) < p: break
            if k not in tenute and cassa >= unita * 0.999:
                q = unita * (1 - COSTO_GRID) / livello(k); tenute[k] = (q, unita); cassa -= unita
        # griglia vuota e prezzo sopra: sposta la griglia in alto
        if not tenute and p > ancora * (1 + G): ancora = p
        v[t] = cassa + sum(q * p for q, _ in tenute.values())
    return v, ops

# ------------------------- PORTAFOGLIO E STATISTICHE -------------------------
def portafoglio(C, funzione):
    n = len(next(iter(C.values()))); somma = [0.0] * n; tutte = []
    for c in C.values():
        v, ops = funzione(c); tutte += ops
        for t in range(n): somma[t] += v[t]
    return [x / len(C) for x in somma], tutte

def stat(v, per_anno):
    picco, calo = v[0], 0.0
    for x in v: picco = max(picco, x); calo = min(calo, x / picco - 1)
    return (v[-1] / v[0]) ** (per_anno / max(len(v) - 1, 1)) - 1, calo

def main():
    dati = {}
    for m in MONETE:
        d = carica(m)
        if d: dati[m] = d
    if "XBT" not in dati: sys.exit("Mancano i dati di BTC.")
    ore = sorted(dati["XBT"])
    blocchi = [("A) RITORNO ALLA MEDIA BREVE (candele da 4 ore)", 4), ("B) GRID (candele da 1 ora)", 1)]
    print(f"\n{len(dati)} monete, {len(ore) / 24 / 365:.1f} anni di dati.\n")
    fmt = lambda x: f"{x[0] * 100:+.0f} % / {x[1] * 100:.0f} %"
    num = lambda x: f"x {x:.2f}".replace(".", ",")
    for titolo, h in blocchi:
        tempi = [t for t in ore if t % (h * 3600) == 0]
        C = {m: [d.get(t) for t in tempi] for m, d in dati.items()}
        n = len(tempi); per_anno = 365 * 24 / h; inizio = 200 if h == 4 else 0
        taglio = inizio + int((n - inizio) * 0.6)
        anni = (n - inizio) / per_anno
        tenere = [1.0] * n
        for t in range(1, n):
            g = [c[t] / c[t - 1] - 1 for c in C.values() if c[t] and c[t - 1]]
            tenere[t] = tenere[t - 1] * (1 + sum(g) / len(C))
        print(titolo)
        print(f"{'':3}{'':34}{'Prova':>16}{'Verifica':>16}{'Capitale':>10}{'Operaz./anno':>14}{'Vinte':>7}{'Media vinte':>13}{'Media perse':>13}")
        def riga(nome, v, ops=None):
            p, q = stat(v[inizio:taglio + 1], per_anno), stat(v[taglio:], per_anno)
            cap = v[-1] / v[inizio]
            if ops is None:
                print(f"   {nome:34}{fmt(p):>16}{fmt(q):>16}{num(cap):>10}"); return
            sem = "🟢" if p[0] > 0 and q[0] > 0 else "🟡" if cap > 1 else "🔴"
            vin = [o for o in ops if o > 0]; per = [o for o in ops if o <= 0]
            mv = f"{sum(vin) / len(vin) * 100:+.1f} %" if vin else "-"; mp = f"{sum(per) / len(per) * 100:+.1f} %" if per else "-"
            print(f"{sem} {nome:34}{fmt(p):>16}{fmt(q):>16}{num(cap):>10}{len(ops) / anni:>14.0f}{len(vin) / max(len(ops), 1) * 100:>6.0f}%{mv:>13}{mp:>13}")
        riga("Tenere le monete (riferimento)", tenere)
        if h == 4:
            for nome, tipo, filtro in (("RSI 2", "rsi", False), ("RSI 2 + filtro di trend", "rsi", True),
                                       ("Bande", "bande", False), ("Bande + filtro di trend", "bande", True)):
                riga(nome, *portafoglio(C, lambda c, tipo=tipo, filtro=filtro: media_breve(c, tipo, filtro)))
        else:
            for G in (0.01, 0.02, 0.04):
                riga(f"Grid, livelli ogni {G * 100:.0f} %", *portafoglio(C, lambda c, G=G: grid(c, G)))
        print()
    print("""Prova / Verifica: rendimento annuo / calo massimo dal picco (primo 60 % e ultimo 40 % dei dati).
Capitale: quante volte il capitale iniziale su tutto il periodo.   Vinte: operazioni chiuse in guadagno.
🟢 guadagna sia in prova sia in verifica   🟡 guadagna solo nel complesso   🔴 perde
Per il grid conta soprattutto il calo massimo: le operazioni chiuse sono quasi tutte in guadagno per costruzione,
le perdite stanno nelle monete comprate e rimaste in mano quando il prezzo scende sotto la griglia.""")

if __name__ == "__main__":
    main()
