#!/usr/bin/env python3
"""
MISURATORE TREND - Rev 5
Domanda: come si comporta il Canale 55/20 nel mercato rosso, e serve vendere allo scoperto?
30 monete, candele giornaliere, una quota fissa per moneta (1/30 del capitale), niente leva.

Varianti (tutte con le stesse regole di canale):
  1) Solo long                          il bot attuale
  2) Solo long, solo in fase verde      compra solo se BTC e' sopra la sua media a 200 giorni;
                                        se la fase diventa rossa chiude i long
  3) Long + short sempre                short quando il prezzo rompe il minimo di 55 giorni,
                                        chiude quando supera il massimo di 20
  4) Long in verde, short in rosso      fase decisa da BTC sopra/sotto la media a 200 giorni;
                                        al cambio di fase chiude le posizioni del verso sbagliato
  5) Come 4, con la media a 100 giorni
Costi: long sullo spot 0,40 % per ordine; short sui perpetui 0,07 % per ordine + funding stimato
0,01 % al giorno a carico dello short (stima prudente: nei mercati rossi il funding spesso va contro chi e' short).

Blocco 2: prova di robustezza del filtro "forza contro BTC" emerso dall'analisi delle perdite
(non comprare le monete salite piu' di BTC di oltre X % negli ultimi 55 giorni), con varie soglie.

Uso (nella cartella dati):  python ../misuratore_trend_rev5.py
Solo libreria standard Python 3.8+.
"""
import csv, json, os, sys, time, urllib.request

MONETE = ("XBT ETH SOL XRP ADA DOGE LTC LINK AVAX DOT BCH ATOM UNI XLM ETC FIL AAVE ALGO TRX NEAR "
          "APE SAND MANA AXS CRV COMP OP ARB INJ XTZ").split()
API = "https://futures.kraken.com/api/charts/v1/trade/{sym}/1h?from={a}&to={b}"
N_IN, N_OUT = 55, 20
COSTO_LONG, COSTO_SHORT, FUNDING = 0.004, 0.0007, 0.0001
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
                if ts % 86400 == 0: out[ts] = float(r[4])
            except (ValueError, IndexError): pass
    return out

def ok(s, t, n): return t >= n and all(x is not None for x in s[t - n:t + 1])
def media(v): return sum(v) / len(v)

def simula(C, btc, modo, n_fase=200, soglia_forza=None):
    """Ritorna (rendimenti giornalieri del portafoglio, quota long, quota short, operazioni)."""
    T = len(btc); N = len(C)
    somma = [0.0] * T; lunghi = [0.0] * T; corti = [0.0] * T; ops = []
    for m, c in C.items():
        pos = 0; e = 1.0; e_in = 1.0
        for t in range(1, T):
            if c[t] is None or c[t - 1] is None:
                continue
            g = pos * (c[t] / c[t - 1] - 1) - (FUNDING if pos == -1 else 0)
            if not ok(c, t, N_IN):
                somma[t] += g; continue
            verde = (btc[t] > media(btc[t - n_fase:t])) if ok(btc, t, n_fase) else None
            su, giu = c[t] > max(c[t - N_IN:t]), c[t] < min(c[t - N_IN:t])
            nuova = pos
            if pos == 1 and (c[t] < min(c[t - N_OUT:t]) or (modo in ("verde", "fasi") and verde is False)): nuova = 0
            if pos == -1 and (c[t] > max(c[t - N_OUT:t]) or (modo == "fasi" and verde is True)): nuova = 0
            if nuova == 0:
                forza_ok = True
                if soglia_forza is not None and ok(btc, t, N_IN):
                    forza_ok = (c[t] / c[t - N_IN]) - (btc[t] / btc[t - N_IN]) <= soglia_forza
                if su and forza_ok and (modo in ("long", "ls") or verde is True):
                    nuova = 1
                elif giu and (modo == "ls" or (modo == "fasi" and verde is False)):
                    nuova = -1
            if nuova != pos:
                costo = lambda p: COSTO_LONG if p == 1 else COSTO_SHORT if p == -1 else 0.0
                g -= costo(pos) + costo(nuova)
            e *= 1 + g
            if nuova != pos:
                if pos != 0: ops.append(e / e_in - 1)
                e_in = e
            pos = nuova
            somma[t] += g
            if pos == 1: lunghi[t] += 1
            if pos == -1: corti[t] += 1
    r = [s / N for s in somma]
    return r, [x / N for x in lunghi], [x / N for x in corti], ops

def statistiche(r):
    e, picco, calo = 1.0, 1.0, 0.0
    for g in r:
        e *= 1 + g; picco = max(picco, e); calo = min(calo, e / picco - 1)
    return (e ** (365 / max(len(r), 1)) - 1 if e > 0 else -1.0), calo, e

def main():
    dati = {}
    for m in MONETE:
        d = carica(m)
        if d: dati[m] = d
        else: print(f"{m}: esclusa")
    if "XBT" not in dati: sys.exit("Mancano i dati di BTC.")
    giorni = sorted(dati["XBT"])
    C = {m: [d.get(t) for t in giorni] for m, d in dati.items()}
    btc = C["XBT"]; T = len(giorni)
    taglio = INIZIO + int((T - INIZIO) * 0.6)
    data = lambda t: time.strftime("%Y-%m-%d", time.gmtime(giorni[t]))
    print(f"{len(C)} monete, dal {data(INIZIO)} al {data(T - 1)}. Prova fino al {data(taglio)}, poi verifica.\n")

    # quanto tempo il mercato e' stato verde
    fase = [btc[t] > media(btc[t - 200:t]) for t in range(INIZIO, T)]
    print(f"BTC sopra la media a 200 giorni: {sum(fase) / len(fase) * 100:.0f} % dei giorni "
          f"(prova {sum(fase[:taglio - INIZIO]) / (taglio - INIZIO) * 100:.0f} %, verifica {sum(fase[taglio - INIZIO:]) / (T - taglio) * 100:.0f} %)\n")

    fmt = lambda x: f"{x[0] * 100:+.0f} % / {x[1] * 100:.0f} %"
    num = lambda x: f"x {x:.2f}".replace(".", ",")
    testa = f"{'':3}{'':34}{'Prova':>16}{'Verifica':>16}{'Capitale':>10}{'Long':>7}{'Short':>7}{'Operaz.':>9}{'Vinte':>7}"

    def riga(nome, r, lu, co, ops, rif=None):
        p, v, tot = statistiche(r[INIZIO:taglio + 1]), statistiche(r[taglio + 1:]), statistiche(r[INIZIO + 1:])
        sem = "  "
        if rif:
            if p[0] > rif[0][0] and v[0] > rif[1][0]: sem = "🟢"
            elif tot[2] > rif[2][2]:                 sem = "🟡"
            else:                                    sem = "🔴"
        vinte = sum(1 for o in ops if o > 0) / len(ops) * 100 if ops else 0
        print(f"{sem} {nome:34}{fmt(p):>16}{fmt(v):>16}{num(tot[2]):>10}{media(lu[INIZIO:]) * 100:>6.0f}%{media(co[INIZIO:]) * 100:>6.0f}%{len(ops):>9}{vinte:>6.0f}%")
        return p, v, tot

    print("1) MERCATO ROSSO: VENDERE ALLO SCOPERTO?")
    print(testa)
    T1 = len(btc)
    tenere = [0.0] * T1
    for t in range(1, T1):
        g = [c[t] / c[t - 1] - 1 for c in C.values() if c[t] is not None and c[t - 1] is not None]
        tenere[t] = media(g) if g else 0.0
    riga("Tenere le monete (riferimento)", tenere, [1] * T1, [0] * T1, [])
    base = riga("1) Solo long (bot attuale)", *simula(C, btc, "long"))
    riga("2) Solo long, solo in fase verde", *simula(C, btc, "verde"), rif=base)
    riga("3) Long + short sempre", *simula(C, btc, "ls"), rif=base)
    riga("4) Long in verde, short in rosso", *simula(C, btc, "fasi", 200), rif=base)
    riga("5) Come 4, fase su media 100 g", *simula(C, btc, "fasi", 100), rif=base)

    print("\n2) FILTRO \"FORZA CONTRO BTC\": non comprare le monete salite piu' di BTC di oltre X % in 55 giorni (solo long)")
    print(testa)
    riga("Nessun filtro", *simula(C, btc, "long"))
    for s in (0.40, 0.20, 0.10, 0.05, 0.0, -0.10):
        riga(f"Soglia {s * 100:+.0f} %", *simula(C, btc, "long", soglia_forza=s), rif=base)

    print("""
Prova / Verifica: rendimento annuo / calo massimo.   Capitale: quante volte il capitale iniziale su tutto il periodo.
Long / Short: quota media del capitale in posizioni long e short.   Vinte: operazioni chiuse in guadagno.
🟢 meglio del bot attuale sia in prova sia in verifica   🟡 meglio solo sul capitale finale   🔴 peggio
Per il filtro: e' credibile solo se migliora in modo graduale al variare della soglia, non con una soglia sola.
Short simulati sui perpetui con funding stimato: nella realta' il funding varia e puo' pesare di piu'.""")

if __name__ == "__main__":
    main()
