#!/usr/bin/env python3
"""
TRAILING "BTC GUIDA" - Rev 4: trailing che si allarga mentre il guadagno cresce  (4 ore, perpetui,
solo long, BTC + 12 monete liquide, spread nei costi)
Ingresso: candela 4h di BTC oltre 2 ATR; monete salite oltre 1,5 ATR nella stessa candela (max 5).
Gestione:
  stop iniziale 1,5 ATR; pareggio quando il prezzo sale di 1 ATR
  trailing: lo stop segue il massimo a una distanza  S = S0 + g x (guadagno massimo in ATR)
            g = 0 e' il trailing fisso di prima; con g > 0 piu' l'operazione corre, piu' spazio le si lascia
  lo stop puo' solo salire, mai scendere
  uscita al massimo dopo 16 ore, 2 giorni, 5 giorni o 10 giorni
Percorso del prezzo: candele da 15 minuti; ingresso alla chiusura del segnale + 0,05 % per il ritardo.
Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto
(le operazioni piu' lunghe occupano i posti piu' a lungo: alcuni segnali vengono saltati).
Uso (nella cartella dati):  python ../trailing_btc_guida_rev4.py
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
import genetico_btc_guida_rev2 as G2
import trailing_btc_guida_rev1 as T1
from misuratore_ritest_rev1 import COSTO, FUNDING_ORA

DURATE = [("16 ore", 64), ("2 giorni", 192), ("5 giorni", 480), ("10 giorni", 960)]
S0 = [1.5, 2.0]
G = [0.0, 0.25, 0.5, 1.0]
PAREGGIO = 1.0

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    D = G1.Dati(); SP = G2.spread()
    monete = ["XBT"] + sorted(sorted((m for m in D.uno if m != "XBT"), key=lambda m: SP.get(m, 1))[:12])
    q15 = {m: T1.scarica_15m(m, D.t0, D.t1 + 3600) for m in monete}
    t15 = {m: [x[0] for x in v] for m, v in q15.items()}
    S = D.serie(4); Tb, Hb, Lb, Cb, Ab, _, _ = S["XBT"]
    forti = {Tb[i] for i in range(1, len(Cb)) if Ab[i - 1] and (Cb[i] - Cb[i - 1]) / Ab[i - 1] > T1.Z_BTC}
    segnali = []
    for m in monete:
        if m == "XBT": continue
        T, H, L, C, A, _, _ = S[m]
        for i in range(520, len(C) - 2):
            if T[i] in forti and A[i - 1] and H[i] != L[i] and (C[i] - C[i - 1]) / A[i - 1] > T1.Z_MONETA:
                ch = T[i] + 4 * 3600
                k = bisect.bisect_left(t15[m], ch)
                if k >= len(q15[m]) or q15[m][k][0] != ch or k + 64 >= len(q15[m]): continue
                segnali.append((ch, m, (C[i] - C[i - 1]) / A[i - 1], C[i], A[i], q15[m][k:k + 960]))
    varianti = [("riferimento: fisso 16 ore", "16 ore", 64, None, None)]
    for dn, nq in DURATE:
        for s0 in S0:
            for g in G:
                varianti.append((f"S0 {s0} + {g} x guadagno".replace(".", ","), dn, nq, s0, g))
    taglio = D.taglio
    righe = []
    for nome, dn, nq, s0, g in varianti:
        ops = []
        for ch, m, z, e, a, barre in segnali:
            stop0 = e - 1.5 * a; pct = 1.5 * a / e
            if not 0.002 <= pct <= 0.10: continue
            n = min(nq, len(barre))
            stop, massimo, px, q = stop0, e, barre[n - 1][4], n - 1
            for j in range(n):
                o, h, l, c = barre[j][1:5]
                if l <= stop: px, q = min(stop, o), j; break
                massimo = max(massimo, h)
                if s0 is not None and massimo >= e + PAREGGIO * a:
                    guadagno = (massimo - e) / a
                    stop = max(stop, e, massimo - (s0 + g * guadagno) * a)
            costo = 2 * COSTO + 0.0005 + SP.get(m, G2.SPREAD_DEFAULT) + FUNDING_ORA * (q + 1) / 4
            ops.append((ch, ch + (q + 1) * 900, m, z, pct, (px - e) / (e - stop0) - costo / pct))
        righe.append((nome, dn, T1.scegli(ops)))
    tutti = [o for *_, v in righe for o in v]
    durata = (max(o[1] for o in tutti) - min(o[0] for o in tutti)) / (365 * 86400)
    anni = sorted({time.gmtime(o[0]).tm_year for o in tutti})
    print(f"\n{len(segnali)} segnali. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(taglio))}.")
    print("Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.\n")
    print(f"   {'Durata max':11}{'Trailing':26}{'Prese':>6}{'Vinte':>6}{'Durata':>8}{'R medio':>8}{'R max':>7}{'R prova':>9}{'R verif.':>9}{'Annuo':>7}{'Calo':>7}" + "".join(f"{a:>7}" for a in anni))
    base = None; ultimo = None
    for nome, dn, ops in righe:
        cap, calo, curva, fatte = G1.portafoglio(ops, T1.RISCHIO, T1.MAX_POS)
        pr = [o[5] for o in fatte if o[0] < taglio]; ve = [o[5] for o in fatte if o[0] >= taglio]
        def valore(t):
            v = 1.0
            for tt, c in curva:
                if tt <= t: v = c
                else: break
            return v
        celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
        annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
        if base is None: base = annuo; s = "  "
        else: s = "🟢" if annuo > base and calo >= -0.20 and media(ve) > 0.05 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
        if ultimo is not None and dn != ultimo: print()
        ultimo = dn
        rr = [o[5] for o in fatte]
        print(f"{s} {dn:11}{nome:26}{len(fatte):>6}{sum(1 for r in rr if r > 0) / len(rr) * 100:>5.0f}%"
              f"{media([(o[1] - o[0]) / 3600 for o in fatte]):>7.0f}h{media(rr):>+8.2f}{max(rr):>+7.1f}"
              f"{media(pr):>+9.2f}{media(ve):>+9.2f}{annuo * 100:>+6.0f}%{calo * 100:>+6.0f}%{celle}")
    print("""
Trailing "S0 a + g x guadagno": distanza dello stop dal massimo = a ATR + g ATR per ogni ATR di guadagno.
Prese: operazioni fatte dal portafoglio (con durate lunghe i posti restano occupati e si saltano segnali).
R max: miglior operazione.   Durata: ore medie in posizione.
🟢 rende piu' del riferimento restando entro il -20 % e positiva in verifica   🟡 positiva ma non migliore   🔴 negativa""")

if __name__ == "__main__":
    main()
