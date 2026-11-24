#!/usr/bin/env python3
"""
TRAILING "BTC GUIDA" - Rev 5: trailing che si allarga col guadagno, griglia fine e SENZA limite di tempo
(4 ore, perpetui, solo long, BTC + 12 monete liquide, spread nei costi)
Ingresso: candela 4h di BTC oltre 2 ATR; monete salite oltre 1,5 ATR nella stessa candela (max 5).
Gestione: stop iniziale 1,5 ATR; pareggio dopo +1 ATR; poi lo stop segue il massimo a una distanza
  S = S0 + g x (guadagno massimo in ATR), con S0 = 1,5 o 2 ATR e g da 0 a 1 a passi di 0,05.
  Lo stop puo' solo salire. Nessuna uscita a tempo: si esce solo allo stop
  (tetto tecnico di 60 giorni; la colonna "a 60 gg" dice quante operazioni ci arrivano).
Controllo di robustezza: R medio togliendo le 5 e le 10 operazioni migliori.
Percorso del prezzo: candele da 15 minuti; ingresso alla chiusura del segnale + 0,05 % per il ritardo.
Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.
Uso (nella cartella dati):  python ../trailing_btc_guida_rev5.py
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
import genetico_btc_guida_rev2 as G2
import trailing_btc_guida_rev1 as T1
from misuratore_ritest_rev1 import COSTO, FUNDING_ORA

S0 = [1.5, 2.0]
G = [round(0.05 * k, 2) for k in range(21)]
PAREGGIO, TETTO = 1.0, 60 * 96

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
                if k + 64 >= len(q15[m]) or q15[m][k][0] != ch: continue
                segnali.append((ch, m, (C[i] - C[i - 1]) / A[i - 1], C[i], A[i], k))
    taglio = D.taglio; righe = []
    for s0 in S0:
        for g in G:
            ops = []; al_tetto = 0
            for ch, m, z, e, a, k0 in segnali:
                stop0 = e - 1.5 * a; pct = 1.5 * a / e
                if not 0.002 <= pct <= 0.10: continue
                barre = q15[m]; fine = min(len(barre), k0 + TETTO)
                stop, massimo, px, q = stop0, e, barre[fine - 1][4], fine - 1 - k0
                for j in range(k0, fine):
                    _, o, h, l, c = barre[j]
                    if l <= stop: px, q = min(stop, o), j - k0; break
                    if h > massimo:
                        massimo = h
                        if massimo >= e + PAREGGIO * a:
                            stop = max(stop, e, massimo - (s0 + g * (massimo - e) / a) * a)
                else:
                    if fine == k0 + TETTO: al_tetto += 1
                costo = 2 * COSTO + 0.0005 + SP.get(m, G2.SPREAD_DEFAULT) + FUNDING_ORA * (q + 1) / 4
                ops.append((ch, ch + (q + 1) * 900, m, z, pct, (px - e) / (e - stop0) - costo / pct))
            righe.append((s0, g, T1.scegli(ops), al_tetto))
    tutti = [o for _, _, v, _ in righe for o in v]
    durata = (max(o[0] for o in tutti) + 86400 - min(o[0] for o in tutti)) / (365 * 86400)
    anni = sorted({time.gmtime(o[0]).tm_year for o in tutti})
    print(f"\n{len(segnali)} segnali. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(taglio))}. Nessun limite di tempo (tetto 60 giorni).")
    print("Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.\n")
    print(f"   {'S0':>4}{'g':>6}{'Prese':>6}{'Vinte':>6}{'Durata':>8}{'Max':>6}{'a 60gg':>7}{'R medio':>8}{'senza 5':>8}{'senza 10':>9}{'R max':>7}"
          f"{'R prova':>8}{'R verif':>8}{'Annuo':>7}{'Calo':>7}" + "".join(f"{a:>7}" for a in anni))
    for s0, g, ops, al_tetto in righe:
        cap, calo, curva, fatte = G1.portafoglio(ops, T1.RISCHIO, T1.MAX_POS)
        rr = sorted(o[5] for o in fatte)
        pr = [o[5] for o in fatte if o[0] < taglio]; ve = [o[5] for o in fatte if o[0] >= taglio]
        def valore(t):
            v = 1.0
            for tt, c in curva:
                if tt <= t: v = c
                else: break
            return v
        celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
        annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
        ok = media(pr) > 0.05 and media(ve) > 0.05 and media(rr[:-10]) > 0
        s = "🟢" if ok and calo >= -0.20 else ("🟡" if ok else "🔴")
        dur = [(o[1] - o[0]) / 86400 for o in fatte]
        print(f"{s} {s0:>4}{g:>6.2f}{len(fatte):>6}{sum(1 for r in rr if r > 0) / len(rr) * 100:>5.0f}%{media(dur):>6.1f}gg{max(dur):>5.0f}g{al_tetto:>7}"
              f"{media(rr):>+8.2f}{media(rr[:-5]):>+8.2f}{media(rr[:-10]):>+9.2f}{rr[-1]:>+7.1f}{media(pr):>+8.2f}{media(ve):>+8.2f}"
              f"{annuo * 100:>+6.0f}%{calo * 100:>+6.0f}%{celle}".replace(".", ","))
        if g == 1.0: print()
    print("""S0, g: distanza dello stop dal massimo = S0 ATR + g ATR per ogni ATR di guadagno (g = 1: lo stop resta al pareggio).
Durata: giorni medi in posizione; Max: operazione piu' lunga; a 60gg: operazioni arrivate al tetto tecnico.
senza 5 / senza 10: R medio togliendo le 5 o 10 operazioni migliori (se crolla, il risultato dipende da pochi colpi).
🟢 positiva in prova, verifica e senza le 10 migliori, calo entro il -20 %   🟡 come sopra ma calo oltre il -20 %   🔴 no""")

if __name__ == "__main__":
    main()
