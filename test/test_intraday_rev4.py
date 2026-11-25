#!/usr/bin/env python3
"""
TEST INTRADAY - Rev 4  (perpetui Kraken, 13 monete liquide, solo long, ingresso a MERCATO come Rev 3)
Stesso ingresso della Rev 3 (trend orario a struttura, minimo su supporto, ripartenza), uscita Cecchino in R
senza limite di tempo (pareggio a +1 R, trailing 1,5 R dal massimo, oltre +3 R si allarga di 0,10 per R).
Novita': CHIUSURA PARZIALE. Quando il prezzo tocca +X R si chiude META' posizione a +X R; l'altra meta'
continua con lo stesso trailing.  X = nessuna (come Rev 3), 2 R (richiesta), 3 R (confronto).
Il risultato dell'operazione e' la media delle due meta'. I costi sono gli stessi (stessa quantita' totale
comprata e venduta). Nella candela da 15 min si guarda prima lo stop, poi il livello parziale (prudente).
In fondo: risultato del portafoglio anno per anno.

Uso (nella cartella dati):  python ../test_intraday_rev4.py
"""
import calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica
from genetico_btc_guida_rev1 import portafoglio
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from test_intraday_rev1 import LIQUIDE, MIN_STOP, MAX_STOP, RISCHIO
from test_intraday_rev3 import Moneta3, chiudi, riga, INTESTA, PAREGGIO, SOGLIA_FASE2, ALLARGAMENTO, TETTO

BASE = 1.5

def gestisci(Q, b, e, stop0, R, parziale):
    """Ritorna (indice, R lordo medio delle due meta', tipo d'uscita finale, massimo in R)."""
    stop, mx, presa = stop0, e, None
    for x in range(b, min(len(Q), b + TETTO)):
        t, o, h, l, c = Q[x]
        if l <= stop:
            tipo = "stop" if stop < e else ("pareggio" if stop == e else "trailing")
            r = (min(stop, o) - e) / R
            return x, (r if presa is None else 0.5 * presa + 0.5 * r), tipo, (mx - e) / R
        if parziale and presa is None and h >= e + parziale * R: presa = parziale
        if h > mx:
            mx = h; g = (mx - e) / R
            if g >= PAREGGIO:
                dist = BASE + (ALLARGAMENTO * (g - SOGLIA_FASE2) if g >= SOGLIA_FASE2 else 0.0)
                stop = max(stop, e, mx - dist * R)
    x = min(len(Q), b + TETTO) - 1; r = (Q[x][4] - e) / R
    return x, (r if presa is None else 0.5 * presa + 0.5 * r), "tetto", (mx - e) / R

def mercato(M, P, tocchi, parziale):
    H, L, C, A, T = M.H, M.L, M.C, M.A, M.T
    ops, i = [], 220
    while i < len(C) - 1:
        k = M.m72[i]; hh = H[k]
        if k >= i - 1 or not (C[i] > H[i - 1] and C[i] < hh): i += 1; continue
        ll = min(L[k:i + 1])
        if (hh - ll) / A[i] < P or not M.trend_orario("struttura", k, ll) or M.tocchi(ll, k, A[i]) < tocchi: i += 1; continue
        e = C[i]; stop = ll - 0.3 * A[i]; R = e - stop
        if not (MIN_STOP <= R / e <= MAX_STOP): i += 1; continue
        t_in = T[i] + 3600; b = M.q_da(t_in)
        if b >= len(M.Q) - 1: break
        x, r, tipo, mfe = gestisci(M.Q, b, e, stop, R, parziale)
        ops.append(chiudi(M, t_in, x, r, tipo, mfe, e, R, "mercato"))
        i = max(i + 1, M.h_da(M.Q[x][0] + 900))
    return ops

def anni(ops, a0, a1):
    _, _, curva, _ = portafoglio([o[:6] for o in ops], RISCHIO, 5, 3.0)
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    celle = []
    for a in range(a0, a1 + 1):
        v0, v1 = valore(calendar.timegm((a, 1, 1, 0, 0, 0))), valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0)))
        celle.append(f"{(v1 / v0 - 1) * 100:>+7.1f}%")
    return "".join(celle).replace(".", ",")

def main():
    SP = spread(); monete = []
    for m in LIQUIDE:
        b = carica(m, 1)
        if b and len(b) > 5000:
            M = Moneta3(m, b, SP.get(m, SPREAD_DEFAULT))
            if len(M.Q) > 20000: monete.append(M)
    t0 = max(max(M.T[0], M.Q[0][0]) for M in monete); t1 = min(min(M.T[-1], M.Q[-1][0]) for M in monete)
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400); nm = len(monete)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{nm} monete ({' '.join(M.m for M in monete)}), dal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}.")
    print("Colonne come Rev 3. 'parz' = livello della chiusura di meta' posizione.\n")
    varianti = [(P, 2) for P in (3, 4, 5, 6)] + [(4, 1), (5, 1)]
    risultati = {}
    print(INTESTA)
    for P, toc in varianti:
        for parz in (None, 2.0, 3.0):
            ops = []
            for M in monete: ops += [o for o in mercato(M, P, toc, parz) if t0 <= o[0] <= t1]
            risultati[(P, toc, parz)] = ops
            nome = f"P {P} | tocchi {toc} | parz {'no' if parz is None else f'{parz:.0f}R'}"
            print(riga(nome, ops, taglio, durata, nm), flush=True)
        print()
    a0, a1 = time.gmtime(t0).tm_year, time.gmtime(t1).tm_year
    print("=== Portafoglio anno per anno (rischio 0,75 %) ===")
    print(f"   {'variante':<30}" + "".join(f"{a:>8}" for a in range(a0, a1 + 1)))
    for (P, toc, parz), ops in risultati.items():
        nome = f"P {P} | tocchi {toc} | parz {'no' if parz is None else f'{parz:.0f}R'}"
        print(f"   {nome:<30}{anni(ops, a0, a1)}")
    print(f"\nNota: {a0} parte dal {d(t0)}, {a1} finisce il {d(t1)}.")

if __name__ == "__main__":
    main()
