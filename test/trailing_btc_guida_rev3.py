#!/usr/bin/env python3
"""
TRAILING "BTC GUIDA" - Rev 3: la regola su candele da 1 ora, 2 ore e 4 ore
(perpetui, solo long, BTC + 12 monete liquide, spread nei costi)
Segnale: una candela di BTC (1h, 2h o 4h) chiude in salita di oltre 2 ATR; si comprano le monete salite
di oltre 1,5 ATR nella stessa candela (al massimo 5, le piu' forti). ATR a 14 candele dello stesso tempo.
Gestione:
  FISSO      stop 1,5 ATR, uscita dopo N candele
  TRAILING   stop 1,5 ATR, a pareggio dopo +P ATR, poi segue il massimo a S ATR; uscita al massimo dopo N candele
Durata massima provata: 4 candele (come la regola a 4h) e 16 ore.
Percorso del prezzo dopo l'ingresso: candele da 15 minuti (stop controllati ogni 15 minuti, aggiornati con il
massimo e validi dalla candela successiva). Ingresso alla chiusura del segnale + 0,05 % per il ritardo.
La riga 4h fa da controllo: deve dare circa lo stesso risultato del test con i prezzi al minuto.
Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.
Uso (nella cartella dati):  python ../trailing_btc_guida_rev3.py
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
import genetico_btc_guida_rev2 as G2
import trailing_btc_guida_rev1 as T1
from misuratore_ritest_rev1 import COSTO, FUNDING_ORA

ORE = [1, 2, 4]
GESTIONI = [("fisso", None, None), ("trailing 0,75/2", 0.75, 2.0), ("trailing 1/2", 1.0, 2.0), ("trailing 1/1,5", 1.0, 1.5)]

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    D = G1.Dati(); SP = G2.spread()
    monete = ["XBT"] + sorted(sorted((m for m in D.uno if m != "XBT"), key=lambda m: SP.get(m, 1))[:12])
    q15 = {m: T1.scarica_15m(m, D.t0, D.t1 + 3600) for m in monete}
    t15 = {m: [x[0] for x in v] for m, v in q15.items()}
    taglio = D.taglio
    righe_out = []
    for ore in ORE:
        S = D.serie(ore); Tb, Hb, Lb, Cb, Ab, _, _ = S["XBT"]
        forti = {Tb[i] for i in range(1, len(Cb)) if Ab[i - 1] and (Cb[i] - Cb[i - 1]) / Ab[i - 1] > T1.Z_BTC}
        segnali = []
        for m in monete:
            if m == "XBT": continue
            T, H, L, C, A, _, _ = S[m]
            for i in range(520, len(C) - 2):
                if T[i] in forti and A[i - 1] and H[i] != L[i] and (C[i] - C[i - 1]) / A[i - 1] > T1.Z_MONETA:
                    ch = T[i] + ore * 3600
                    k = bisect.bisect_left(t15[m], ch)
                    if k + 64 >= len(q15[m]) or q15[m][k][0] != ch: continue
                    segnali.append((ch, m, (C[i] - C[i - 1]) / A[i - 1], C[i], A[i], q15[m][k:k + 64]))
        for durata_nome, n_q in (("4 candele", 4 * ore * 4), ("16 ore", 64)):
            if ore == 4 and durata_nome == "16 ore": continue
            for nome, P, Sd in GESTIONI:
                ops = []
                for ch, m, z, e, a, barre in segnali:
                    stop0 = e - 1.5 * a; pct = 1.5 * a / e
                    if not 0.002 <= pct <= 0.10: continue
                    stop, massimo, px, q = stop0, e, barre[n_q - 1][4], n_q - 1
                    for j in range(n_q):
                        o, h, l, c = barre[j][1:5]
                        if l <= stop: px, q = min(stop, o), j; break
                        massimo = max(massimo, h)
                        if P is not None and massimo >= e + P * a: stop = max(stop, e, massimo - Sd * a)
                    costo = 2 * COSTO + 0.0005 + SP.get(m, G2.SPREAD_DEFAULT) + FUNDING_ORA * (q + 1) / 4
                    ops.append((ch, ch + (q + 1) * 900, m, z, pct, (px - e) / (e - stop0) - costo / pct))
                righe_out.append((ore, durata_nome, nome, T1.scegli(ops)))
    tutti = [o for *_, v in righe_out for o in v]
    durata = (max(o[1] for o in tutti) - min(o[0] for o in tutti)) / (365 * 86400)
    anni = sorted({time.gmtime(o[0]).tm_year for o in tutti})
    print(f"\nMonete: {' '.join(monete)}. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(taglio))}.")
    print("Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.\n")
    print(f"   {'Candele':8}{'Durata max':11}{'Gestione':17}{'Oper./a':>8}{'Vinte':>6}{'R prova':>9}{'R verif.':>9}{'Annuo':>7}{'Calo':>7}" + "".join(f"{a:>7}" for a in anni))
    ultimo = None
    for ore, dn, nome, ops in righe_out:
        if ultimo is not None and ore != ultimo: print()
        ultimo = ore
        pr = [o[5] for o in ops if o[0] < taglio]; ve = [o[5] for o in ops if o[0] >= taglio]
        cap, calo, curva, _ = G1.portafoglio(ops, T1.RISCHIO, T1.MAX_POS)
        def valore(t):
            v = 1.0
            for tt, c in curva:
                if tt <= t: v = c
                else: break
            return v
        celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
        annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
        s = "🟢" if media(pr) > 0.05 and media(ve) > 0.05 and calo >= -0.20 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
        print(f"{s} {str(ore) + 'h':8}{dn:11}{nome:17}{len(ops) / durata:>8.0f}{sum(1 for o in ops if o[5] > 0) / len(ops) * 100:>5.0f}%"
              f"{media(pr):>+9.2f}{media(ve):>+9.2f}{annuo * 100:>+6.0f}%{calo * 100:>+6.0f}%{celle}")
    print("""
Gestione "trailing P/S": pareggio dopo +P ATR, poi stop a S ATR dal massimo.
🟢 positiva in prova e verifica e calo entro il -20 %   🟡 positiva ma debole o calo oltre il -20 %   🔴 negativa in un periodo""")

if __name__ == "__main__":
    main()
