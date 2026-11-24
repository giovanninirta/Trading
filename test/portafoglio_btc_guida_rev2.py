#!/usr/bin/env python3
"""
PORTAFOGLIO "BTC GUIDA" - Rev 2
Stessa regola della Rev 1 (4 ore, monete gia' partite, ingresso 5 minuti dopo con prezzi da 1 minuto,
uscita dopo 16 ore, stop 1,5 ATR), con due controlli in piu':
  1) lo spread di oggi di ogni moneta pagato intero a ogni operazione (ordini a mercato)
  2) solo le 12 monete piu' liquide (spread piu' basso), confrontate con tutte le 30
Uso (nella cartella dati):  python ../portafoglio_btc_guida_rev2.py
"""
import calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portafoglio_btc_guida_rev1 as P
import genetico_btc_guida_rev2 as G2

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    ops, mancanti = P.operazioni(); SP = G2.spread()
    liquide = set(sorted({o[2] for o in ops}, key=lambda m: SP.get(m, 1))[:12])
    t0, t1 = ops[0][0], ops[-1][1]; taglio = t0 + (t1 - t0) * 0.6
    durata = (t1 - t0) / (365 * 86400); anni = sorted({time.gmtime(o[0]).tm_year for o in ops})
    print(f"\nMonete liquide: {' '.join(sorted(liquide))}")
    print(f"Spread di oggi (%): " + "  ".join(f"{m} {SP.get(m, 0) * 100:.3f}" for m in sorted(liquide)) + "\n")
    casi = [
        ("Tutte le 30, senza spread (Rev 1)", [o for o in ops]),
        ("Tutte le 30, con spread", [o[:5] + (o[5] - SP.get(o[2], G2.SPREAD_DEFAULT) / o[4],) for o in ops]),
        ("Solo 12 liquide, con spread", [o[:5] + (o[5] - SP.get(o[2], G2.SPREAD_DEFAULT) / o[4],) for o in ops if o[2] in liquide]),
    ]
    print("R PER OPERAZIONE (media, costi inclusi)")
    print(f"   {'Caso':36}{'N':>6}{'Vinte':>7}{'R prova':>9}{'R verif.':>9}" + "".join(f"{a:>7}" for a in anni))
    for nome, o in casi:
        pr = [x[5] for x in o if x[0] < taglio]; ve = [x[5] for x in o if x[0] >= taglio]
        celle = "".join(f"{media([x[5] for x in o if time.gmtime(x[0]).tm_year == a]):>+7.2f}" for a in anni)
        s = "🟢" if media(pr) > 0.05 and media(ve) > 0.05 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
        print(f"{s} {nome:36}{len(o):>6}{sum(1 for x in o if x[5] > 0) / len(o) * 100:>6.0f}%{media(pr):>+9.2f}{media(ve):>+9.2f}{celle}")
    print("\nPORTAFOGLIO (interesse composto, leva max 3)")
    print(f"   {'Caso':36}{'Rischio':>8}{'Pos.':>5}{'Annuo':>7}{'Calo':>7}" + "".join(f"{a:>7}" for a in anni))
    for nome, o in casi[1:]:
        for rischio, mp in ((0.5, 3), (0.5, 5), (0.75, 5), (1.0, 5)):
            cap, calo, _, _, _, curva = P.portafoglio(sorted(o), rischio, mp)
            def valore(t):
                v = 1.0
                for tt, c in curva:
                    if tt <= t: v = c
                    else: break
                return v
            celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
            annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
            s = "🟢" if annuo > 0 and calo >= -0.20 else ("🟡" if annuo > 0 else "🔴")
            print(f"{s} {nome:36}{rischio:>7.2f}%{mp:>5}{annuo * 100:>+6.0f}%{calo * 100:>+6.0f}%{celle}")
        print()
    print("🟢 guadagna entro il -20 % di calo   🟡 guadagna ma supera il -20 %   🔴 perde")

if __name__ == "__main__":
    main()
