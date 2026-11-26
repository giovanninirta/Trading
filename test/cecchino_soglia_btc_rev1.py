#!/usr/bin/env python3
"""
CECCHINO - SOGLIA DELLO SCATTO DI BTC - Rev 1
Regola Cecchino identica al bot (stop 1 ATR, pareggio +1, trailing 1,5, 16 ore, fase 2 oltre +3, monete > 1,7 ATR,
max 5, rischio 0,75 %, leva 3); cambia SOLO la soglia dello scatto di BTC: 1,0 / 1,25 / 1,5 / 1,75 / 2,0 ATR (attuale).
Universi: 12 liquide (prova e verifica), 17 nuove, 29 insieme (= Cecchino 29). Anno per anno sulle 29.
Uso (nella cartella dati):  python ../cecchino_soglia_btc_rev1.py
"""
import calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from verifica_monete_nuove_btc_guida_rev1 import LIQUIDE12, NUOVE
import genetico_cecchino_rev1 as G

BASE = dict(tipo="atr", btc_atr=2.0, btc_pct=1.25, ore=4, atr_p=14, moneta=1.7, maxpos=5, salta=0, rsi=None, stop=1.0,
            pari=1.0, trail=1.5, f1=16, s2=3.0, allarga=0.10, regime=False, sma=50, toll=0.0)

def media(v): return sum(v) / len(v) if v else 0.0

def anni(curva, a0, a1):
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    return "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+7.0f}%"
                   for a in range(a0, a1 + 1))

def main():
    SP = spread(); gruppi = {"12": [], "17": []}
    for nome, lista in (("12", LIQUIDE12), ("17", NUOVE)):
        for m in lista:
            b = carica(m, 1)
            if not b or len(b) < 5000: continue
            q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
            if len(q) >= 20000: gruppi[nome].append(G.Moneta(m, b, q, SP.get(m, SPREAD_DEFAULT)))
    gruppi["29"] = gruppi["12"] + gruppi["17"]
    btc = G.Moneta("XBT", carica("XBT", 1), [], 0)
    liq = gruppi["12"]
    t0 = max(max(M.uno[0][0], M.Q[0][0]) for M in liq) + 40 * 86400; t1 = min(min(M.uno[-1][0], M.Q[-1][0]) for M in liq) - 3 * 86400
    taglio = t0 + (t1 - t0) * 0.6; a0, a1 = time.gmtime(t0).tm_year, time.gmtime(t1).tm_year
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nDal {d(t0)} al {d(t1)} (prova fino al {d(taglio)}). Netto = R medio per operazione dopo i costi.\n")
    def misura(g, gr, da, a):
        ops, cap, calo, curva = G.simula(g, btc, gruppi[gr], da, a)
        anni_p = (a - da) / (365 * 86400); net = sorted(o[3] for o in ops)
        return dict(n=len(ops) / anni_p, netto=media(net), s10=media(net[:-10]), annuo=(cap ** (1 / anni_p) - 1) if cap > 0 else -1,
                    calo=calo, curva=curva)
    print(f"   {'soglia BTC':<12}| {'12 prova: op/a netto annuo calo':^32} | {'12 verifica: netto annuo calo':^29} | "
          f"{'17 nuove: op/a netto -top10 annuo calo':^40} | {'29 (Cecchino 29): op/a netto -top10 annuo calo':^46}")
    curve = {}
    for s in (1.0, 1.25, 1.5, 1.75, 2.0):
        g = dict(BASE, btc_atr=s)
        p, v, n, t = misura(g, "12", t0, taglio), misura(g, "12", taglio, t1), misura(g, "17", t0, t1), misura(g, "29", t0, t1)
        curve[s] = t["curva"]
        print((f"   {f'{s:.2f} ATR' + (' *' if s == 2.0 else ''):<12}| {p['n']:>5.0f}{p['netto']:>+8.3f}{p['annuo'] * 100:>+8.1f}%{p['calo'] * 100:>+6.0f}%   | "
               f"{v['netto']:>+8.3f}{v['annuo'] * 100:>+9.1f}%{v['calo'] * 100:>+7.0f}%    | {n['n']:>5.0f}{n['netto']:>+8.3f}{n['s10']:>+8.3f}"
               f"{n['annuo'] * 100:>+8.1f}%{n['calo'] * 100:>+6.0f}%      | {t['n']:>5.0f}{t['netto']:>+8.3f}{t['s10']:>+8.3f}"
               f"{t['annuo'] * 100:>+8.1f}%{t['calo'] * 100:>+6.0f}%").replace(".", ","), flush=True)
    print("\n   * = soglia attuale dei bot Cecchino e Cecchino 29")
    print(f"\n   29 monete, anno per anno  " + "".join(f"{a:>8}" for a in range(a0, a1 + 1)))
    for s, c in curve.items(): print(f"   {s:.2f} ATR{'':<17}{anni(c, a0, a1)}".replace(".", ","))

if __name__ == "__main__":
    main()
