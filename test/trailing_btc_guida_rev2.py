#!/usr/bin/env python3
"""
TRAILING "BTC GUIDA" - Rev 2  (4 ore, perpetui, BTC + 12 monete liquide, spread nei costi)
Rev 2: stesso schema del trader (pareggio, poi stop che segue il prezzo) ma con distanze in ATR,
cioe' adattate all'oscillazione normale di ogni moneta, invece che in percentuale fissa.
  stop iniziale  1,5 ATR sotto l'ingresso (come la regola attuale)
  pareggio       quando il prezzo sale di P ATR lo stop va al prezzo d'ingresso
  trailing       da quel momento lo stop segue il massimo raggiunto a una distanza di S ATR
  uscita         comunque dopo 16 ore (come la regola attuale)
Si provano P = 0,75 / 1 / 1,5 / 2 ATR e S = 1 / 1,5 / 2 / 3 ATR, confrontati con la regola attuale
(stop fisso, uscita dopo 16 ore). Stop seguiti minuto per minuto, aggiornati con il massimo del minuto
e validi dal minuto successivo. Ingresso 5 minuti dopo la chiusura della candela del segnale.
Uso (nella cartella dati):  python ../trailing_btc_guida_rev2.py
"""
import calendar, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
import genetico_btc_guida_rev2 as G2
import trailing_btc_guida_rev1 as T1
from misuratore_ritest_rev1 import COSTO, FUNDING_ORA

PAREGGI = [0.75, 1.0, 1.5, 2.0]
DISTANZE = [1.0, 1.5, 2.0, 3.0]

def segnali(D, SP, monete):
    """Per ogni segnale: (ingresso, moneta, z, prezzo, atr, minuti dopo l'ingresso)."""
    S = D.serie(4); Tb, Hb, Lb, Cb, Ab, _, _ = S["XBT"]
    forti = {Tb[i] for i in range(1, len(Cb)) if Ab[i - 1] and (Cb[i] - Cb[i - 1]) / Ab[i - 1] > T1.Z_BTC}
    cache = json.load(open("MINUTI_4h.json")); out = []; dur = 4 * 3600
    for m in monete:
        if m == "XBT": continue
        T, H, L, C, A, _, _ = S[m]
        for i in range(520, len(C) - 5):
            if T[i] not in forti or not A[i - 1] or H[i] == L[i] or (C[i] - C[i - 1]) / A[i - 1] <= T1.Z_MONETA: continue
            righe = cache.get(f"{m}_{T[i]}")
            if not righe: continue
            ch = T[i] + dur
            minuti = sorted(r for r in righe if ch <= r[0] < ch + 4 * dur)
            if len(minuti) < 0.8 * 4 * dur / 60: continue
            k = next((q for q, r in enumerate(minuti) if r[0] >= ch + 240), None)
            if k is None: continue
            out.append((ch + 240, m, (C[i] - C[i - 1]) / A[i - 1], minuti[k][4], A[i],
                        [(r[1], r[2], r[3], r[4]) for r in minuti[k + 1:]]))
    return out

def simula(sig, SP, P, S):
    ops = []
    for t, m, z, e, a, barre in sig:
        stop0 = e - 1.5 * a; pct = (e - stop0) / e
        if not 0.003 <= pct <= 0.10: continue
        stop, massimo, px, q = stop0, e, barre[-1][3], len(barre) - 1
        for k, (o, h, l, c) in enumerate(barre):
            if l <= stop: px, q = min(stop, o), k; break
            massimo = max(massimo, h)
            if P is not None and massimo >= e + P * a:
                stop = max(stop, e, massimo - S * a)
        costo = 2 * COSTO + SP.get(m, G2.SPREAD_DEFAULT) + FUNDING_ORA * (q + 1) / 60
        ops.append((t, t + (q + 1) * 60, m, z, pct, (px - e) / (e - stop0) - costo / pct))
    return T1.scegli(ops)

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    D = G1.Dati(); SP = G2.spread()
    monete = ["XBT"] + sorted(sorted((m for m in D.uno if m != "XBT"), key=lambda m: SP.get(m, 1))[:12])
    sig = segnali(D, SP, monete)
    taglio = D.taglio
    varianti = [("Attuale: stop fisso, 16 ore", None, None)] + [(f"Pareggio {p} ATR, trailing {s} ATR".replace(".", ","), p, s) for p in PAREGGI for s in DISTANZE]
    risultati = [(nome, simula(sig, SP, p, s)) for nome, p, s in varianti]
    tutti = [o for _, v in risultati for o in v]
    durata = (max(o[1] for o in tutti) - min(o[0] for o in tutti)) / (365 * 86400)
    anni = sorted({time.gmtime(o[0]).tm_year for o in tutti})
    print(f"\n{len(sig)} segnali sulle monete liquide. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(taglio))}.")
    print("Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.\n")
    print(f"   {'Variante':34}{'Vinte':>6}{'Durata':>8}{'R prova':>9}{'R verif.':>9}{'Annuo':>7}{'Calo':>7}" + "".join(f"{a:>7}" for a in anni))
    base = None
    for nome, ops in risultati:
        pr = [o[5] for o in ops if o[0] < taglio]; ve = [o[5] for o in ops if o[0] >= taglio]
        cap, calo, curva, _ = G1.portafoglio(ops, T1.RISCHIO, T1.MAX_POS)
        def valore(t):
            v = 1.0
            for tt, c in curva:
                if tt <= t: v = c
                else: break
            return v
        celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
        annuo = cap ** (1 / durata) - 1
        if base is None: base = (media(pr), media(ve)); s = "  "
        else: s = "🟢" if media(pr) > base[0] and media(ve) > base[1] else ("🟡" if media(pr) > 0.05 and media(ve) > 0.05 else "🔴")
        print(f"{s} {nome:34}{sum(1 for o in ops if o[5] > 0) / len(ops) * 100:>5.0f}%{media([(o[1] - o[0]) / 3600 for o in ops]):>7.1f}h"
              f"{media(pr):>+9.2f}{media(ve):>+9.2f}{annuo * 100:>+6.0f}%{calo * 100:>+6.0f}%{celle}")
        if nome.startswith("Attuale") or nome.endswith("3,0 ATR"): print()
    print("""🟢 migliore della regola attuale sia in prova sia in verifica   🟡 positiva ma non migliore   🔴 peggiore e debole
R: risultato per operazione in multipli del rischio iniziale (1,5 ATR), costi e spread inclusi.  Durata: ore medie in posizione.""")

if __name__ == "__main__":
    main()
