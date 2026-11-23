#!/usr/bin/env python3
"""
MISURATORE ACCUMULO BTC - Rev 3
Domanda: partendo da 1 BTC, un bot a trend riesce a finire con PIU' di 1 BTC?
Tutto e' misurato in BTC: 1,000 = come tenere BTC fermo, 1,100 = +10 % di bitcoin.

Tre bot, tutti con la regola "Canale N/X" (entra se chiude sopra il massimo delle ultime N candele,
esce se chiude sotto il minimo delle ultime X candele):
  A) BTC <-> EURO   si tiene BTC finche' BTC e' in trend; quando il trend si rompe si vende in euro,
                    si ricompra quando BTC rompe di nuovo il massimo. Guadagna BTC quando BTC scende.
  B) ALT CONTRO BTC si tiene BTC; quando una moneta rompe al rialzo CONTRO BTC (grafico moneta/BTC)
                    le si da' 1/10 del capitale, e si torna in BTC quando quel trend finisce.
  C) A + B insieme  la parte in BTC segue A, le quote in altre monete seguono B.
Riferimenti: tenere BTC (= 1,000) e tenere tutte le altre monete a pesi uguali senza mai scambiare.

Candele provate: 1h, 2h, 4h, 12h, 1 giorno. Canali in candele: 20/10, 55/20, 100/50.
Costi: 0,40 % per ogni scambio (ordine limite spot Kraken, coppia diretta moneta/BTC o BTC/EUR);
la colonna "a 0,80 %" ripete il conto con ordini a mercato o passaggio via euro.
Prova = primo 60 % del periodo, verifica = ultimo 40 %.

Uso (nella cartella dati):  python ../misuratore_accumulo_btc_rev3.py
Solo libreria standard Python 3.8+.
"""
import os, sys, time
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, MONETE

ORE = [1, 2, 4, 12, 24]
CANALI = [(20, 10), (55, 20), (100, 50)]
QUOTE = 10

def massimo_mobile(v, n, funz):
    """out[t] = max (o min) di v[t-n..t-1]; None se la finestra non e' piena.
    Le serie hanno valori mancanti solo all'inizio (moneta non ancora quotata)."""
    out, d = [None] * len(v), deque()
    meglio = (lambda a, b: a >= b) if funz is max else (lambda a, b: a <= b)
    for t in range(1, len(v)):
        x = v[t - 1]
        if x is not None:
            while d and meglio(x, v[d[-1]]): d.pop()
            d.append(t - 1)
        while d and d[0] < t - n: d.popleft()
        if t >= n and v[t - n] is not None and d: out[t] = v[d[0]]
    return out

def canale(v, N, X):
    alto = massimo_mobile(v, N, max)
    basso = massimo_mobile(v, X, min)
    stato, dentro = [0] * len(v), 0
    for t in range(len(v)):
        if v[t] is None or alto[t] is None or basso[t] is None:
            stato[t] = dentro if v[t] is not None else 0; continue
        if not dentro and v[t] > alto[t]: dentro = 1
        elif dentro and v[t] < basso[t]: dentro = 0
        stato[t] = dentro
    return stato

def simula(p, R, sA, sB, modo, costo):
    """p = prezzo BTC, R[c] = rapporto moneta/BTC, sA/sB = stati dei canali. Valore in BTC."""
    n = len(p)
    btc, cassa = 1.0, 0.0             # cassa espressa in BTC al prezzo corrente
    alt = {c: 0.0 for c in R}
    V = [1.0] * n; scambi = 0
    for t in range(1, n):
        if cassa: cassa *= p[t - 1] / p[t]
        for c in R:
            if alt[c]: alt[c] *= R[c][t] / R[c][t - 1]
        tot = btc + cassa + sum(alt.values())
        # A: BTC <-> euro sulla parte non in altre monete
        if modo in ("A", "C"):
            voglio_btc = sA[t] == 1
            if voglio_btc and cassa:
                btc += cassa * (1 - costo); cassa = 0.0; scambi += 1
            elif not voglio_btc and btc:
                cassa += btc * (1 - costo); btc = 0.0; scambi += 1
        # B: quote nelle monete che salgono contro BTC
        if modo in ("B", "C"):
            for c in R:
                if R[c][t] is None: continue
                if alt[c] and sB[c][t] == 0:
                    v = alt[c] * (1 - costo); alt[c] = 0.0; scambi += 1
                    if modo == "C" and sA[t] == 0: cassa += v * (1 - costo); scambi += 1
                    else: btc += v
                elif not alt[c] and sB[c][t] == 1 and sB[c][t - 1] == 0:
                    q = tot / QUOTE
                    da_btc = min(q, btc); btc -= da_btc
                    da_cassa = min(q - da_btc, cassa); cassa -= da_cassa
                    alt[c] = da_btc * (1 - costo) + da_cassa * (1 - 2 * costo)
                    if alt[c]: scambi += 1
                    else: alt[c] = 0.0
        V[t] = btc + cassa + sum(alt.values())
    return V, scambi

def calo(V, a, b):
    picco, peggio = V[a], 0.0
    for x in V[a:b]:
        picco = max(picco, x); peggio = min(peggio, x / picco - 1)
    return peggio

def pct(x): return f"{x * 100:+.0f}%"
def num(x): return f"x{x:.2f}".replace(".", ",")

def main():
    serie = {}
    for m in MONETE:
        b = carica(m, 1)
        if b: serie[m] = {x[0]: x[4] for x in b}
    if "XBT" not in serie: sys.exit("Mancano i dati di BTC.")
    print(f"{len(serie)} monete caricate. Tutto in BTC: x1,00 = come tenere BTC fermo.\n")
    print("Legenda: Prova/Verifica = BTC guadagnati o persi nel periodo / calo massimo in BTC.")
    print("Anni = BTC guadagnati o persi in quell'anno. Scambi = operazioni all'anno.")
    print("🟢 = ha guadagnato BTC sia in prova sia in verifica.\n")

    for ore in ORE:
        tempi = sorted({t - t % (ore * 3600) for t in serie["XBT"]})
        # ultima chiusura di ogni candela
        chiusura = {m: {} for m in serie}
        for m, s in serie.items():
            for t in sorted(s): chiusura[m][t - t % (ore * 3600)] = s[t]
        p = [chiusura["XBT"].get(t) for t in tempi]
        # riempi eventuali buchi di BTC
        for i in range(1, len(p)):
            if p[i] is None: p[i] = p[i - 1]
        i0 = next(i for i, x in enumerate(p) if x is not None)
        tempi, p = tempi[i0:], p[i0:]
        n = len(p); taglio = int(n * 0.6)
        R = {}
        for m in serie:
            if m == "XBT": continue
            v, ultimo = [], None
            for t, pb in zip(tempi, p):
                x = chiusura[m].get(t, ultimo if ultimo is not None else None)
                if x is not None: ultimo = x
                v.append(x / pb if x is not None else None)
            # dopo il primo valore niente None
            R[m] = v
        anni = sorted({time.gmtime(t).tm_year for t in tempi})
        idx_anno = {a: [i for i, t in enumerate(tempi) if time.gmtime(t).tm_year == a] for a in anni}
        durata_anni = (tempi[-1] - tempi[0]) / (365 * 86400)

        etichetta = f"{ore}h" if ore < 24 else "1 giorno"
        print(f"=== CANDELE {etichetta.upper()}  ({time.strftime('%Y-%m-%d', time.gmtime(tempi[0]))} -> "
              f"{time.strftime('%Y-%m-%d', time.gmtime(tempi[-1]))}) ===")
        intest = f"{'':3}{'Bot':<24}{'Prova':>13}{'Verifica':>13}{'Finale':>8}{'a 0,80%':>9}{'Scambi':>8}" + \
                 "".join(f"{a:>7}" for a in anni)
        print(intest)

        def riga(nome, V, scambi, V2=None):
            pr, ve = V[taglio] / V[0], V[-1] / V[taglio]
            verde = "🟢" if pr > 1 and ve > 1 and not nome.startswith("Tenere") else "  "
            celle = ""
            for a in anni:
                ix = idx_anno[a]
                celle += f"{pct(V[ix[-1]] / V[max(ix[0] - 1, 0)] - 1):>7}"
            fin2 = num(V2[-1]) if V2 else ""
            sc = f"{scambi / durata_anni:.0f}" if scambi is not None else ""
            print(f"{verde:<3}{nome:<24}{pct(pr - 1) + '/' + pct(calo(V, 0, taglio + 1)):>13}"
                  f"{pct(ve - 1) + '/' + pct(calo(V, taglio, n)):>13}{num(V[-1]):>8}{fin2:>9}{sc:>8}{celle}")

        # riferimento: altre monete tenute ferme a pesi uguali (in BTC)
        Vh = [1.0] * n; quote = {}
        for t in range(n):
            for m in R:
                if R[m][t] is not None and m not in quote: quote[m] = None
            vivi = [m for m in R if R[m][t] is not None and R[m][max(t - 1, 0)] is not None]
            if t and vivi:
                Vh[t] = Vh[t - 1] * (1 + sum(R[m][t] / R[m][t - 1] - 1 for m in vivi) / len(vivi))
            elif t: Vh[t] = Vh[t - 1]
        riga("Tenere BTC", [1.0] * n, None)
        riga("Tenere le altre monete", Vh, None)

        for N, X in CANALI:
            sA = canale(p, N, X)
            sB = {m: canale(R[m], N, X) for m in R}
            for modo, nome in (("A", "A BTC<->euro"), ("B", "B alt contro BTC"), ("C", "C A+B insieme")):
                V, sc = simula(p, R, sA, sB, modo, 0.004)
                V2, _ = simula(p, R, sA, sB, modo, 0.008)
                riga(f"{nome} {N}/{X}", V, sc, V2)
        print()

    print("Come leggere: il bot serve se la riga e' verde E i numeri restano positivi anche a 0,80 %")
    print("e su piu' canali vicini. Un solo verde isolato e' quasi sempre fortuna.")

if __name__ == "__main__":
    main()
