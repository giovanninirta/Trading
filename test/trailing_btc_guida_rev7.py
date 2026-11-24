#!/usr/bin/env python3
"""
TRAILING "BTC GUIDA" - Rev 7: gestione in due fasi  (4 ore, perpetui, solo long, BTC + 12 monete liquide)
Ingresso: candela 4h di BTC oltre 2 ATR; monete salite oltre 1,5 ATR nella stessa candela (max 5).
FASE 1 (normale, come la regola solida di oggi):
  stop iniziale 1,5 ATR; pareggio dopo +1 ATR; poi trailing fisso a 1,5 ATR dal massimo;
  se dopo 16 ore la posizione e' ancora in fase 1, si chiude.
FASE 2 ("cassaforte"): quando il guadagno massimo supera L ATR (L = 2, 3 o 4):
  niente piu' uscita a tempo; la distanza dello stop dal massimo diventa 1,5 + g x (guadagno - L) ATR,
  quindi si allarga solo oltre la soglia. Lo stop puo' solo salire. g da 0 a 1 a passi di 0,05
  (g = 0: trailing fisso senza limite di tempo; g = 1: lo stop resta fermo al livello raggiunto a L).
Tetto tecnico 60 giorni. Percorso del prezzo: candele da 15 minuti; ingresso alla chiusura + 0,05 % di ritardo.
Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.
Uso (nella cartella dati):  python ../trailing_btc_guida_rev7.py
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
import genetico_btc_guida_rev2 as G2
import trailing_btc_guida_rev1 as T1
from misuratore_ritest_rev1 import COSTO, FUNDING_ORA

SOGLIE = [2.0, 3.0, 4.0]
G = [round(0.05 * k, 2) for k in range(21)]
TETTO, FASE1 = 60 * 96, 64

def media(v): return sum(v) / len(v) if v else 0.0

def simula(segnali, q15, SP, L, g, fisso=False):
    ops, in_fase2 = [], 0
    for ch, m, z, e, a, k0 in segnali:
        stop0 = e - 1.5 * a; pct = 1.5 * a / e
        if not 0.002 <= pct <= 0.10: continue
        barre = q15[m]; fine = min(len(barre), k0 + TETTO)
        stop, massimo, fase2 = stop0, e, False
        px, q = barre[min(fine, k0 + FASE1) - 1][4], min(fine, k0 + FASE1) - 1 - k0
        for j in range(k0, fine):
            if not fase2 and j - k0 >= FASE1: px, q = barre[j - 1][4], j - 1 - k0; break
            _, o, h, l, c = barre[j]
            if l <= stop: px, q = min(stop, o), j - k0; break
            if h > massimo:
                massimo = h; G_ = (massimo - e) / a
                if fisso:
                    if G_ >= 1: stop = max(stop, e, massimo - 1.5 * a)
                    continue
                if not fase2 and G_ >= L: fase2 = True
                if G_ >= 1:
                    dist = 1.5 + (g * (G_ - L) if fase2 else 0.0)
                    stop = max(stop, e, massimo - dist * a)
        else:
            px, q = barre[fine - 1][4], fine - 1 - k0
        in_fase2 += fase2
        costo = 2 * COSTO + 0.0005 + SP.get(m, G2.SPREAD_DEFAULT) + FUNDING_ORA * (q + 1) / 4
        ops.append((ch, ch + (q + 1) * 900, m, z, pct, (px - e) / (e - stop0) - costo / pct))
    return T1.scegli(ops), in_fase2

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
                if k + FASE1 >= len(q15[m]) or q15[m][k][0] != ch: continue
                segnali.append((ch, m, (C[i] - C[i - 1]) / A[i - 1], C[i], A[i], k))
    taglio = D.taglio
    righe = [("riferimento", "-", simula(segnali, q15, SP, 99, 0, fisso=True))]
    for L in SOGLIE:
        for g in G: righe.append((L, g, simula(segnali, q15, SP, L, g)))
    tutti = [o for _, _, (v, _) in righe for o in v]
    durata = (max(o[0] for o in tutti) + 86400 - min(o[0] for o in tutti)) / (365 * 86400)
    anni = sorted({time.gmtime(o[0]).tm_year for o in tutti})
    print(f"\n{len(segnali)} segnali. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(taglio))}.")
    print("Riferimento: fase 1 sola (pareggio a +1 ATR, trailing 1,5 ATR, uscita a 16 ore).")
    print("Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.\n")
    print(f"   {'L':>5}{'g':>6}{'Prese':>6}{'Fase 2':>7}{'Vinte':>6}{'Durata':>8}{'R medio':>8}{'senza 5':>8}{'senza 10':>9}{'R max':>7}"
          f"{'R prova':>8}{'R verif':>8}{'Annuo':>7}{'Calo':>7}" + "".join(f"{a:>7}" for a in anni))
    for L, g, (ops, f2) in righe:
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
        ok = media(pr) > 0.05 and media(ve) > 0.05 and media(rr[:-10]) > 0.05
        s = "🟢" if ok and calo >= -0.20 else ("🟡" if media(pr) > 0 and media(ve) > 0 and media(rr[:-10]) > 0 else "🔴")
        Ls = L if isinstance(L, str) else f"{L:.0f}"
        gs = g if isinstance(g, str) else f"{g:.2f}"
        print(f"{s} {Ls:>5}{gs:>6}{len(fatte):>6}{f2:>7}{sum(1 for r in rr if r > 0) / len(rr) * 100:>5.0f}%"
              f"{media([(o[1] - o[0]) / 3600 for o in fatte]):>7.0f}h{media(rr):>+8.2f}{media(rr[:-5]):>+8.2f}{media(rr[:-10]):>+9.2f}{rr[-1]:>+7.1f}"
              f"{media(pr):>+8.2f}{media(ve):>+8.2f}{annuo * 100:>+6.0f}%{calo * 100:>+6.0f}%{celle}".replace(".", ","))
        if g in ("-", 1.0): print()
    print("""L: guadagno (in ATR) oltre il quale si passa in fase 2.  g: allargamento dello stop per ogni ATR oltre L.
Fase 2: operazioni (tra tutti i segnali) che sono arrivate in fase 2.  Durata: ore medie in posizione.
senza 5 / senza 10: R medio togliendo le 5 o 10 operazioni migliori.
🟢 oltre +0,05 R in prova, verifica e senza le 10 migliori, calo entro il -20 %   🟡 positiva ma debole   🔴 no""")

if __name__ == "__main__":
    main()
