#!/usr/bin/env python3
"""
STUDIO RIENTRI E FALSA ROTTURA - Rev 1  (perpetui Kraken, 13 monete liquide, candele 1h, solo long)
Uscita sempre come Cecchino: pareggio a +1 R, trailing 1,5 R, oltre +3 R + 0,10 R per R, gestita sui 15 min.

PARTE 1 - I RIENTRI della Rev 3 (P 4 e P 5, supporto 2 tocchi): un rientro e' un ingresso su un pullback
  (stesso massimo hh) gia' usato da un'operazione precedente sulla stessa moneta. Confronto primi ingressi /
  rientri: quanti, risultato medio e mediano, peso dei 3 migliori, anno per anno, moneta per moneta, i 10 migliori.

PARTE 2 - LA FALSA ROTTURA come regola a se' (un solo ingresso per pullback, niente rientri):
  contesto: massimo hh delle ultime 72 ore, pivot massimi e minimi crescenti prima del massimo (T1-T3),
            profondita' hh - minimo >= P ATR orari
  supporto S: un pivot minimo delle 200 ore prima del massimo, con almeno N pivot minimi entro 0,5 ATR (lui compreso)
  rottura: il minimo del pullback scende SOTTO S di almeno B ATR (ma non oltre 1,5 ATR), al massimo 8 candele fa
  recupero: la candela chiude di nuovo SOPRA S e sopra il massimo della candela precedente -> ingresso alla chiusura
  stop: 0,3 ATR sotto il minimo della rottura
  T4 = in piu' il minimo della rottura resta sopra l'ultimo pivot minimo crescente (struttura non rotta)
  Griglia fissa: P 3/4/5, N 1/2, B 0,2/0,5, con e senza T4.  Si sceglie guardando solo la prova.

Uso (nella cartella dati):  python ../studio_falsa_rottura_rev1.py
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, COSTO, FUNDING_ORA
from genetico_btc_guida_rev1 import portafoglio
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from test_intraday_rev1 import LIQUIDE, RITARDO, MIN_STOP, MAX_STOP, RISCHIO
from test_intraday_rev3 import gestisci
from test_pullback_15m_rev1 import Moneta, riga, INTESTA

W, PIV, STORIA, TOL = 72, 5, 200, 0.5

def esegui(M, S, i, e, stop):
    R = e - stop; t_in = S.T[i] + 3600; b = bisect.bisect_left(M.QT, t_in)
    if b >= len(M.Q) - 1: return None
    xx, r, tipo, mfe = gestisci(M.Q, b, e, stop, R, 1.5)
    pct = R / e; t_out = M.Q[xx][0] + 900; ore = (t_out - t_in) / 3600
    costo = (2 * COSTO + M.sp + RITARDO + FUNDING_ORA * ore) / pct
    return (t_in, t_out, M.m, 1, pct, r - costo, r, tipo, ore, mfe, costo)

# ------------------------------------------------------------------ parte 1
def rev3_con_etichetta(M, P, tocchi):
    S = M.s(60, W, PIV); H, L, C, A, T = S.H, S.L, S.C, S.A, S.T
    ops, usati, i = [], set(), 300
    while i < len(C) - 1:
        k = S.mw[i]; hh = H[k]
        if k >= i - 1 or not (C[i] > H[i - 1] and C[i] < hh): i += 1; continue
        ll = min(L[k:i + 1]); a = A[i]
        if (hh - ll) / a < P: i += 1; continue
        x = bisect.bisect_right(S.phi, k - PIV); y = bisect.bisect_right(S.pli, k - PIV)
        if x < 2 or y < 2 or not (S.ph[x - 1][1] > S.ph[x - 2][1] and S.pl[y - 1][1] > S.pl[y - 2][1] and ll > S.pl[y - 1][1]):
            i += 1; continue
        j0 = bisect.bisect_left(S.pli, k - STORIA)
        if sum(1 for p in S.pl[j0:y] if abs(p[1] - ll) <= TOL * a) < tocchi: i += 1; continue
        e = C[i]; stop = ll - 0.3 * a
        if not (MIN_STOP <= (e - stop) / e <= MAX_STOP): i += 1; continue
        o = esegui(M, S, i, e, stop)
        if o is None: break
        ops.append(o + (k in usati,)); usati.add(k)
        i = max(i + 1, bisect.bisect_left(T, o[1]))
    return ops

def descrivi(nome, ops, durata):
    if not ops: print(f"   {nome:<16} nessuna"); return
    v = sorted(o[6] for o in ops); n = len(v); som = sum(v)
    print(f"   {nome:<16}{n:>6}{n / durata:>7.1f}{som / n:>+9.3f}{v[n // 2]:>+9.3f}{som:>+9.1f}{sum(v[:-3]):>+10.1f}"
          f"{sum(1 for o in ops if o[7] == 'stop') / n * 100:>7.0f}%{sum(1 for x in v if x >= 3) / n * 100:>6.0f}%".replace(".", ","))

def parte1(monete, t0, t1, durata):
    print("=== PARTE 1: i rientri della Rev 3 (R lordi, prima dei costi) ===")
    for P in (5, 4):
        ops = []
        for M in monete: ops += [o for o in rev3_con_etichetta(M, P, 2) if t0 <= o[0] <= t1]
        primi = [o for o in ops if not o[-1]]; rien = [o for o in ops if o[-1]]
        print(f"\n-- P {P}, supporto 2 tocchi --")
        print(f"   {'':<16}{'quante':>6}{'/anno':>7}{'media':>9}{'mediana':>9}{'somma R':>9}{'senza top3':>10}{'stop':>8}{'>3R':>7}")
        descrivi("primi ingressi", primi, durata); descrivi("rientri", rien, durata)
        anni = range(time.gmtime(t0).tm_year, time.gmtime(t1).tm_year + 1)
        print("   rientri anno per anno (quante / R medio):  " + "   ".join(
            f"{a}: {len(x)} / {(sum(o[6] for o in x) / len(x) if x else 0):+.2f}".replace(".", ",")
            for a in anni for x in [[o for o in rien if time.gmtime(o[0]).tm_year == a]]))
        per = {}
        for o in rien: per.setdefault(o[2], []).append(o[6])
        print("   rientri per moneta (quante / R medio):  " + "  ".join(
            f"{m} {len(v)}/{sum(v) / len(v):+.1f}".replace(".", ",") for m, v in sorted(per.items(), key=lambda x: -len(x[1]))))
        print("   i 10 rientri migliori:  " + "  ".join(
            f"{time.strftime('%Y-%m-%d', time.gmtime(o[0]))} {o[2]} {o[6]:+.1f}".replace(".", ",")
            for o in sorted(rien, key=lambda o: -o[6])[:10]))

# ------------------------------------------------------------------ parte 2
def falsa_rottura(M, P, tocchi, B, t4):
    S = M.s(60, W, PIV); H, L, C, A, T = S.H, S.L, S.C, S.A, S.T
    ops, usati, i = [], set(), 300
    while i < len(C) - 1:
        k = S.mw[i]; hh = H[k]; a = A[i]
        if k >= i - 1 or k in usati or not (C[i] > H[i - 1] and C[i] < hh): i += 1; continue
        jll = min(range(k, i + 1), key=lambda j: L[j]); ll = L[jll]
        if i - jll > 8 or (hh - ll) / a < P: i += 1; continue
        x = bisect.bisect_right(S.phi, k - PIV); y = bisect.bisect_right(S.pli, k - PIV)
        if x < 2 or y < 2 or not (S.ph[x - 1][1] > S.ph[x - 2][1] and S.pl[y - 1][1] > S.pl[y - 2][1]):
            i += 1; continue
        if t4 and not ll > S.pl[y - 1][1]: i += 1; continue
        j0 = bisect.bisect_left(S.pli, k - STORIA); livelli = S.pl[j0:y]; trovato = False
        for _, s in livelli:
            if s - 1.5 * a < ll < s - B * a and C[i] > s and sum(1 for p in livelli if abs(p[1] - s) <= TOL * a) >= tocchi:
                trovato = True; break
        if not trovato: i += 1; continue
        e = C[i]; stop = ll - 0.3 * a
        if not (MIN_STOP <= (e - stop) / e <= MAX_STOP): i += 1; continue
        o = esegui(M, S, i, e, stop)
        if o is None: break
        ops.append(o); usati.add(k)
        i = max(i + 1, bisect.bisect_left(T, o[1]))
    return ops

def anni_portafoglio(ops, a0, a1):
    _, _, curva, _ = portafoglio([o[:6] for o in ops], RISCHIO, 5, 3.0)
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    return "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+7.1f}%"
                   for a in range(a0, a1 + 1)).replace(".", ",")

def parte2(monete, t0, t1, taglio, durata):
    print("\n\n=== PARTE 2: FALSA ROTTURA del supporto come regola a se' (R netti nelle colonne prova/verif) ===")
    print(INTESTA)
    tutte = {}
    for t4 in (False, True):
        for B in (0.2, 0.5):
            for toc in (1, 2):
                for P in (3, 4, 5):
                    ops = []
                    for M in monete: ops += [o for o in falsa_rottura(M, P, toc, B, t4) if t0 <= o[0] <= t1]
                    nome = f"P{P} N{toc} B{B} {'T4' if t4 else 'noT4'}".replace(".", ",")
                    tutte[nome] = ops
                    print(riga(nome, ops, taglio, durata), flush=True)
            print()
    a0, a1 = time.gmtime(t0).tm_year, time.gmtime(t1).tm_year
    print("Portafoglio anno per anno (rischio 0,75 %), le 6 migliori in PROVA:")
    print(f"   {'variante':<22}" + "".join(f"{a:>8}" for a in range(a0, a1 + 1)))
    media = lambda v: sum(v) / len(v) if v else -9
    for nome, ops in sorted(tutte.items(), key=lambda x: -media([o[5] for o in x[1] if o[0] < taglio]))[:6]:
        print(f"   {nome:<22}{anni_portafoglio(ops, a0, a1)}")

def main():
    SP = spread(); monete = []
    for m in LIQUIDE:
        b = carica(m, 1)
        if not b or len(b) < 5000: continue
        q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
        if len(q) > 20000: monete.append(Moneta(m, SP.get(m, SPREAD_DEFAULT), b, q))
    t0 = max(max(M.uno[0][0], M.Q[0][0]) for M in monete); t1 = min(min(M.uno[-1][0], M.Q[-1][0]) for M in monete)
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{len(monete)} monete, dal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}.\n")
    parte1(monete, t0, t1, durata)
    parte2(monete, t0, t1, taglio, durata)

if __name__ == "__main__":
    main()
