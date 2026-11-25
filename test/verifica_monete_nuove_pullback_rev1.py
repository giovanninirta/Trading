#!/usr/bin/env python3
"""
VERIFICA SU MONETE NUOVE - pullback Rev 3  (perpetui Kraken, candele 1h, uscita sui 15 min)
Regola Rev 3 SENZA nessuna modifica: trend orario a struttura, profondita' P 5 ATR (P 4 solo informativa),
minimo su supporto toccato almeno 2 volte, ripartenza, stop 0,3 ATR sotto il minimo, uscita Cecchino 1,5 R senza
limite di tempo, rientri ammessi, una posizione per moneta.

Applicata alle 17 monete dei 30 perpetui MAI usate per costruire la regola (dati mai visti), con il loro spread
reale, confrontate con le 13 liquide su cui la regola e' nata.

CRITERIO FISSATO PRIMA DEL TEST (P 5, 2 tocchi, sulle 17 nuove):
  PROMOSSA se  lordo medio senza le 10 migliori >= +0,15 R   E   R netto medio > 0
  altrimenti si chiude la linea del pullback.

Uso (nella cartella dati):  python ../verifica_monete_nuove_pullback_rev1.py
"""
import calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, MONETE
from genetico_btc_guida_rev1 import portafoglio
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from test_intraday_rev1 import LIQUIDE, RISCHIO
from test_pullback_15m_rev1 import Moneta, operazioni, riga, INTESTA

NUOVE = [m for m in MONETE if m not in LIQUIDE]

def carica_gruppo(lista, SP):
    out = []
    for m in lista:
        b = carica(m, 1)
        if not b or len(b) < 5000: print(f"   {m}: dati 1h insufficienti, esclusa"); continue
        q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
        if len(q) < 20000: print(f"   {m}: dati 15 min insufficienti ({len(q)}), esclusa"); continue
        out.append(Moneta(m, SP.get(m, SPREAD_DEFAULT), b, q))
    return out

def media(v): return sum(v) / len(v) if v else 0.0

def anni(ops, a0, a1):
    _, _, curva, _ = portafoglio([o[:6] for o in ops], RISCHIO, 5, 3.0)
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    return "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+7.1f}%"
                   for a in range(a0, a1 + 1)).replace(".", ",")

def main():
    SP = spread()
    print("\nCaricamento (le 17 nuove possono richiedere il download dei 15 min)...")
    gruppi = {"13 liquide (origine)": carica_gruppo(LIQUIDE, SP), "17 NUOVE (mai viste)": carica_gruppo(NUOVE, SP)}
    liq = gruppi["13 liquide (origine)"]   # periodo e taglio presi dalle 13 liquide; le nuove usano i dati che hanno
    t0 = max(max(M.uno[0][0], M.Q[0][0]) for M in liq); t1 = min(min(M.uno[-1][0], M.Q[-1][0]) for M in liq)
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nPeriodo comune dal {d(t0)} al {d(t1)} (prova fino al {d(taglio)}).")
    print("Nuove (spread, inizio dati 15 min): " + "  ".join(f"{M.m} {M.sp * 100:.2f}% {d(M.Q[0][0])[:7]}".replace(".", ",")
                                                       for M in gruppi["17 NUOVE (mai viste)"]))
    print("(op/a delle nuove calcolato sull'intero periodo: per le monete con meno storia e' sottostimato)\n")
    a0, a1 = time.gmtime(t0).tm_year, time.gmtime(t1).tm_year
    esito = None
    for P in (5, 4):
        print(f"=== P {P}, supporto 2 tocchi{'  (REGOLA DA VERIFICARE)' if P == 5 else '  (solo informativa)'} ===")
        print(INTESTA)
        risultati = {}
        for nome, gruppo in gruppi.items():
            ops = []
            for M in gruppo: ops += [o for o in operazioni(M, 60, 72, 5, 200, P, 2, True) if t0 <= o[0] <= t1]
            risultati[nome] = ops
            print(riga(nome, ops, taglio, durata))
        print()
        print(f"   {'gruppo':<24}{'quante':>7}{'lordo':>8}{'lordo -top10':>13}{'lordo -top3':>12}{'netto':>8}{'mediana':>9}")
        for nome, ops in risultati.items():
            v = sorted(o[6] for o in ops); n = len(v)
            netto = media([o[5] for o in ops])
            print(f"   {nome:<24}{n:>7}{media(v):>+8.3f}{media(v[:-10]):>+13.3f}{media(v[:-3]):>+12.3f}{netto:>+8.3f}"
                  f"{(v[n // 2] if v else 0):>+9.3f}".replace(".", ","))
            if P == 5 and nome.startswith("17"):
                esito = (media(v[:-10]), netto)
        print(f"\n   portafoglio anno per anno: {'':<6}" + "".join(f"{a:>8}" for a in range(a0, a1 + 1)))
        for nome, ops in risultati.items(): print(f"   {nome:<33}{anni(ops, a0, a1)}")
        per = {}
        for o in risultati["17 NUOVE (mai viste)"]: per.setdefault(o[2], []).append(o)
        print("\n   nuove per moneta (operazioni / lordo medio / netto medio):")
        print("   " + "  ".join(f"{m} {len(x)}/{media([o[6] for o in x]):+.2f}/{media([o[5] for o in x]):+.2f}".replace(".", ",")
                              for m, x in sorted(per.items())))
        print()
    l10, net = esito
    ok = l10 >= 0.15 and net > 0
    print(f"=== VERDETTO (P 5, 17 nuove): lordo senza le 10 migliori {l10:+.3f} R (serve >= +0,15), "
          f"netto medio {net:+.3f} R (serve > 0) -> {'PROMOSSA' if ok else 'BOCCIATA'} ===".replace(".", ",").replace("+0,15", "+0,15"))

if __name__ == "__main__":
    main()
