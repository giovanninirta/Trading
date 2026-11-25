#!/usr/bin/env python3
"""
CECCHINO 29 - numero massimo di posizioni - Rev 1
Regola Cecchino (bot Rev 6) sulle 29 monete; cambia solo il massimo di posizioni aperte insieme
(5 = bot attuale, 10 = richiesta per Cecchino 29) e, per confronto, il rischio per operazione.
Leva massima sempre 3 volte il capitale. Simulazione di verifica_monete_nuove_btc_guida_rev1.py.
Uso (nella cartella dati):  python ../cecchino_29_posizioni_rev1.py
"""
import calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
import verifica_monete_nuove_btc_guida_rev1 as V

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    SP = spread(); monete = []
    for m in V.LIQUIDE12 + V.NUOVE:
        b = carica(m, 1)
        if not b or len(b) < 5000: continue
        q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
        if len(q) >= 20000: monete.append(V.Moneta(m, b, q, SP.get(m, SPREAD_DEFAULT)))
    btc = V.Moneta("XBT", carica("XBT", 1), [], 0)
    liq = [M for M in monete if M.m in V.LIQUIDE12]
    t0 = max(max(M.T[0], M.Q[0][0]) for M in liq) + 30 * V.H4; t1 = min(min(M.T[-1], M.Q[-1][0]) for M in liq) - 2 * 86400
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    anni = list(range(time.gmtime(t0).tm_year, time.gmtime(t1).tm_year + 1))
    print(f"\n{len(monete)} monete, dal {time.strftime('%Y-%m-%d', time.gmtime(t0))}. Leva massima 3.\n")
    print(f"   {'max posizioni | rischio':<26}{'op/a':>6}{'netto':>8}{'prova':>8}{'verif':>8}{'-top10':>8}{'annuo':>8}{'calo':>7}"
          f"{'pos.max':>8}" + "".join(f"{a:>7}" for a in anni))
    for maxp, rischio in ((5, 0.0075), (10, 0.0075), (10, 0.005), (8, 0.0075)):
        V.MAX_POS, V.RISCHIO = maxp, rischio
        ops, cap, calo, curva = V.simula(btc, monete, V.BOT["Cecchino"], t0, t1)
        net = sorted(o[3] for o in ops)
        pr = [o[3] for o in ops if o[0] < taglio]; ve = [o[3] for o in ops if o[0] >= taglio]
        annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
        # massimo di posizioni aperte insieme
        ev = sorted([(o[0], 1) for o in ops] + [(o[0] + o[5] * 3600, -1) for o in ops], key=lambda x: (x[0], x[1]))
        aperte = picco = 0
        for _, dv in ev: aperte += dv; picco = max(picco, aperte)
        def valore(t):
            v = 1.0
            for tt, c in curva:
                if tt <= t: v = c
                else: break
            return v
        celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
        print(f"   {f'{maxp} | {rischio * 100:.2f} %':<26}{len(ops) / durata:>6.0f}{media(net):>+8.3f}{media(pr):>+8.3f}{media(ve):>+8.3f}"
              f"{media(net[:-10]):>+8.3f}{annuo * 100:>+7.1f}%{calo * 100:>+6.0f}%{picco:>8}{celle}".replace(".", ","))
    print("\npos.max = massimo di posizioni aperte contemporaneamente nel periodo.")

if __name__ == "__main__":
    main()
