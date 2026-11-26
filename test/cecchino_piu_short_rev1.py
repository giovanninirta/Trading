#!/usr/bin/env python3
"""
CECCHINO 29 + SHORT - Rev 1  (controllo prima di un eventuale bot "Segugio Short")
1) Short n. 1 dell'algoritmo genetico (parametri fissi, nessuna nuova ottimizzazione) anno per anno su 12 liquide,
   17 nuove e 29 insieme.
2) Cecchino 29 (regola del bot Rev 8) anno per anno.
3) Portafoglio UNICO con le due strategie insieme: stesso capitale, rischio 0,75 % per operazione, ciascuna con il suo
   massimo di posizioni (5 long, 8 short), leva totale massima 3, mai long e short insieme sulla stessa moneta.
   Si confronta con Cecchino 29 da solo: gli short servono se alzano il rendimento e/o riducono il calo.
Uso (nella cartella dati):  python ../cecchino_piu_short_rev1.py
"""
import calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from verifica_monete_nuove_btc_guida_rev1 import LIQUIDE12, NUOVE
import genetico_cecchino_rev1 as G
import genetico_short_rev1 as S

SHORT1 = dict(tipo="pct", btc_atr=2.0, btc_pct=1.5, ore=8, atr_p=20, moneta=1.8, maxpos=8, salta=2, rsi=75, stop=0.9,
              pari=1.75, trail=2.0, f1=8, s2=2.5, allarga=0.10, regime=True, sma=160, toll=0.05)
CECCHINO = dict(tipo="atr", btc_atr=2.0, btc_pct=1.25, ore=4, atr_p=14, moneta=1.7, maxpos=5, salta=0, rsi=None, stop=1.0,
                pari=1.0, trail=1.5, f1=16, s2=3.0, allarga=0.10, regime=False, sma=50, toll=0.0)

def media(v): return sum(v) / len(v) if v else 0.0

def portafoglio(liste, leva=3.0, rischio=0.0075):
    """liste = {etichetta: ops}; ops = (inizio, moneta, lordo, netto, fine, pct). Ritorna cap, calo, curva, prese."""
    tutte = sorted((o[0], o[4], o[1], o[5], o[3], et) for et, ops in liste.items() for o in ops)
    cap, picco, calo, aperte, curva, prese = 1.0, 1.0, 0.0, [], [], []
    for t, fine, m, pct, r, et in tutte:
        for p in sorted(aperte, key=lambda p: p[0]):
            if p[0] <= t:
                cap += p[1] * p[2]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p[0], cap))
        aperte = [p for p in aperte if p[0] > t]
        if any(p[3] == m for p in aperte): continue
        importo = cap * rischio; noz = importo / pct
        if sum(p[4] for p in aperte) + noz > leva * cap: continue
        aperte.append((fine, importo, r, m, noz)); prese.append((t, et, r))
    for p in sorted(aperte, key=lambda p: p[0]):
        cap += p[1] * p[2]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p[0], cap))
    return cap, calo, curva, prese

def anni(curva, a0, a1):
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    return "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+8.1f}%"
                   for a in range(a0, a1 + 1)).replace(".", ",")

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
    durata = (t1 - t0) / (365 * 86400); a0, a1 = time.gmtime(t0).tm_year, time.gmtime(t1).tm_year
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nDal {d(t0)} al {d(t1)}. Rischio 0,75 % per operazione, leva massima 3.\n")
    intesta = f"   {'':<34}{'op/a':>6}{'netto':>8}{'-top10':>8}{'annuo':>8}{'calo':>7}   " + "".join(f"{a:>9}" for a in range(a0, a1 + 1))
    print(intesta)
    risultati = {}
    for nome, g, gr in (("Short n. 1 - 12 liquide", SHORT1, "12"), ("Short n. 1 - 17 nuove", SHORT1, "17"),
                        ("Short n. 1 - 29 insieme", SHORT1, "29"), ("Cecchino 29 (bot Rev 8)", CECCHINO, "29")):
        sim = S.simula if g is SHORT1 else G.simula
        ops, cap, calo, curva = sim(g, btc, gruppi[gr], t0, t1)
        risultati[nome] = ops
        net = sorted(o[3] for o in ops)
        print((f"   {nome:<34}{len(ops) / durata:>6.0f}{media(net):>+8.3f}{media(net[:-10]):>+8.3f}"
               f"{((cap ** (1 / durata) - 1) if cap > 0 else -1) * 100:>+7.1f}%{calo * 100:>+6.0f}%   {anni(curva, a0, a1)}").replace(".", ","), flush=True)
    print()
    for nome, liste in (("Cecchino 29 da solo (stesso motore)", {"long": risultati["Cecchino 29 (bot Rev 8)"]}),
                        ("CECCHINO 29 + SHORT (29 monete)", {"long": risultati["Cecchino 29 (bot Rev 8)"], "short": risultati["Short n. 1 - 29 insieme"]})):
        cap, calo, curva, prese = portafoglio(liste)
        net = sorted(p[2] for p in prese)
        nl = sum(1 for p in prese if p[1] == "long"); ns = len(prese) - nl
        print((f"   {nome:<34}{len(prese) / durata:>6.0f}{media(net):>+8.3f}{media(net[:-10]):>+8.3f}"
               f"{((cap ** (1 / durata) - 1) if cap > 0 else -1) * 100:>+7.1f}%{calo * 100:>+6.0f}%   {anni(curva, a0, a1)}"
               f"   ({nl} long, {ns} short)").replace(".", ","))
    print("\nLettura: gli short servono se nel portafoglio insieme l'annuo sale e/o il calo scende rispetto a Cecchino 29 da solo,\n"
          "e se negli anni in cui Cecchino va peggio gli short aiutano.")

if __name__ == "__main__":
    main()
