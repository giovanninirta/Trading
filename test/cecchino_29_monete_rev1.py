#!/usr/bin/env python3
"""
CECCHINO SU 29 MONETE - Rev 1  (regola identica al bot Rev 6: nessun parametro cambiato)
Cambia solo l'universo da cui si scelgono le monete (sempre le piu' forti, max 5 posizioni):
  12 liquide (bot attuale) | 17 nuove | 29 insieme | 29 senza monete con spread oltre 0,20 %
Segugio a 29 solo come informazione.
Simulazione e costi come verifica_monete_nuove_btc_guida_rev1.py (spread reale di ogni moneta).
Uso (nella cartella dati):  python ../cecchino_29_monete_rev1.py
"""
import calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
import verifica_monete_nuove_btc_guida_rev1 as V

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    SP = spread(); tutte = {}
    for m in V.LIQUIDE12 + V.NUOVE:
        b = carica(m, 1)
        if not b or len(b) < 5000: continue
        q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
        if len(q) >= 20000: tutte[m] = V.Moneta(m, b, q, SP.get(m, SPREAD_DEFAULT))
    btc = V.Moneta("XBT", carica("XBT", 1), [], 0)
    liq = [tutte[m] for m in V.LIQUIDE12 if m in tutte]
    t0 = max(max(M.T[0], M.Q[0][0]) for M in liq) + 30 * V.H4; t1 = min(min(M.T[-1], M.Q[-1][0]) for M in liq) - 2 * 86400
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    anni = list(range(time.gmtime(t0).tm_year, time.gmtime(t1).tm_year + 1))
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    universi = {
        "12 liquide (bot attuale)": [tutte[m] for m in V.LIQUIDE12 if m in tutte],
        "17 nuove": [tutte[m] for m in V.NUOVE if m in tutte],
        "29 insieme": list(tutte.values()),
        "29 senza spread > 0,20 %": [M for M in tutte.values() if M.sp <= 0.002],
    }
    esclusi = [M.m for M in tutte.values() if M.sp > 0.002]
    print(f"\nDal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}. {len(tutte)} monete caricate.")
    print(f"Escluse nella variante 'senza spread > 0,20 %': {' '.join(esclusi) or 'nessuna'}\n")
    for bot in ("Cecchino", "Segugio"):
        print(f"=== {bot}{' (solo informativo)' if bot == 'Segugio' else ''} ===")
        print(f"   {'universo':<28}{'op/a':>6}{'netto':>8}{'prova':>8}{'verif':>8}{'-top10':>8}{'vinte':>7}{'annuo':>8}{'calo':>7}"
              + "".join(f"{a:>7}" for a in anni))
        for nome, gruppo in universi.items():
            if bot == "Segugio" and nome not in ("12 liquide (bot attuale)", "29 insieme"): continue
            ops, cap, calo, curva = V.simula(btc, gruppo, V.BOT[bot], t0, t1)
            net = sorted(o[3] for o in ops)
            pr = [o[3] for o in ops if o[0] < taglio]; ve = [o[3] for o in ops if o[0] >= taglio]
            annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
            def valore(t):
                v = 1.0
                for tt, c in curva:
                    if tt <= t: v = c
                    else: break
                return v
            celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
            print(f"   {nome:<28}{len(ops) / durata:>6.0f}{media(net):>+8.3f}{media(pr):>+8.3f}{media(ve):>+8.3f}"
                  f"{media(net[:-10]):>+8.3f}{media([1.0 if x > 0 else 0.0 for x in net]) * 100:>6.0f}%"
                  f"{annuo * 100:>+7.1f}%{calo * 100:>+6.0f}%{celle}".replace(".", ","))
            if bot == "Cecchino" and nome == "29 insieme":
                quote = {}
                for o in ops: quote["liquide" if o[1] in V.LIQUIDE12 else "nuove"] = quote.get("liquide" if o[1] in V.LIQUIDE12 else "nuove", 0) + 1
                print(f"      operazioni prese: {quote.get('liquide', 0)} su monete liquide, {quote.get('nuove', 0)} su nuove")
        print()

if __name__ == "__main__":
    main()
