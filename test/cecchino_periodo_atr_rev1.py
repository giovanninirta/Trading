#!/usr/bin/env python3
"""
CECCHINO - PERIODO DELL'ATR x SOGLIA DELLO SCATTO - Rev 1
Regola Cecchino identica al bot; cambiano solo il periodo dell'ATR (7, 10, 14 = attuale, 20, 28 candele da 4h: vale per
lo scatto di BTC, il movimento delle monete, lo stop e il trailing) e la soglia dello scatto di BTC (1,25 - 2,25 ATR).
CRITERIO (fissato prima): una combinazione BATTE Cecchino (14 / 2,0) se ha annuo piu' alto sia nella VERIFICA delle 12
liquide sia sulle 17 NUOVE, con calo >= -20 % su entrambe. Le 29 insieme sono mostrate per informazione (= Cecchino 29).
Uso (nella cartella dati):  python ../cecchino_periodo_atr_rev1.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from verifica_monete_nuove_btc_guida_rev1 import LIQUIDE12, NUOVE
import genetico_cecchino_rev1 as G
from cecchino_soglia_btc_rev1 import BASE

def media(v): return sum(v) / len(v) if v else 0.0

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
    taglio = t0 + (t1 - t0) * 0.6
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nDal {d(t0)} al {d(t1)} (prova fino al {d(taglio)}). Netto = R medio per operazione dopo i costi.\n")
    def misura(g, gr, da, a):
        ops, cap, calo, _ = G.simula(g, btc, gruppi[gr], da, a)
        anni_p = (a - da) / (365 * 86400); net = sorted(o[3] for o in ops)
        return dict(n=len(ops) / anni_p, netto=media(net), s10=media(net[:-10]), annuo=(cap ** (1 / anni_p) - 1) if cap > 0 else -1, calo=calo)
    print(f"   {'ATR | soglia':<14}| {'12 prova: netto annuo calo':^27} | {'12 verifica: netto annuo calo':^29} | "
          f"{'17 nuove: op/a netto -top10 annuo calo':^40} | {'29: op/a netto annuo calo':^28}")
    risultati = {}
    for ap in (7, 10, 14, 20, 28):
        for s in (1.25, 1.5, 1.75, 2.0, 2.25):
            g = dict(BASE, atr_p=ap, btc_atr=s)
            p, v, n, t = misura(g, "12", t0, taglio), misura(g, "12", taglio, t1), misura(g, "17", t0, t1), misura(g, "29", t0, t1)
            risultati[(ap, s)] = (p, v, n, t)
            segno = " *" if (ap, s) == (14, 2.0) else ""
            print((f"   {f'{ap} | {s:.2f}{segno}':<14}| {p['netto']:>+7.3f}{p['annuo'] * 100:>+8.1f}%{p['calo'] * 100:>+6.0f}%   | "
                   f"{v['netto']:>+7.3f}{v['annuo'] * 100:>+9.1f}%{v['calo'] * 100:>+7.0f}%     | {n['n']:>5.0f}{n['netto']:>+8.3f}{n['s10']:>+8.3f}"
                   f"{n['annuo'] * 100:>+8.1f}%{n['calo'] * 100:>+6.0f}%      | {t['n']:>5.0f}{t['netto']:>+8.3f}{t['annuo'] * 100:>+8.1f}%{t['calo'] * 100:>+6.0f}%")
                  .replace(".", ","), flush=True)
        print()
    _, bv, bn, _ = risultati[(14, 2.0)]
    vincenti = [(k, r) for k, r in risultati.items() if k != (14, 2.0) and r[1]["annuo"] > bv["annuo"] and r[2]["annuo"] > bn["annuo"]
                and r[1]["calo"] >= -0.20 and r[2]["calo"] >= -0.20]
    print("   * = Cecchino attuale (ATR 14, soglia 2,0)")
    if vincenti:
        print("=== Combinazioni che BATTONO Cecchino (verifica 12 e 17 nuove, calo entro -20 %): ===")
        for (ap, s), (p, v, n, t) in sorted(vincenti, key=lambda x: -(x[1][1]["annuo"] + x[1][2]["annuo"])):
            print(f"   ATR {ap}, soglia {s:.2f}: verifica {v['annuo'] * 100:+.1f} % (Cecchino {bv['annuo'] * 100:+.1f} %), "
                  f"17 nuove {n['annuo'] * 100:+.1f} % (Cecchino {bn['annuo'] * 100:+.1f} %), calo {v['calo'] * 100:.0f} / {n['calo'] * 100:.0f} %".replace(".", ","))
    else:
        print("=== Nessuna combinazione batte Cecchino attuale su entrambe le verifiche con calo entro -20 % ===")

if __name__ == "__main__":
    main()
