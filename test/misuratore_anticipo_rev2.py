#!/usr/bin/env python3
"""
MISURATORE ANTICIPO - Rev 2: controllo del "BTC guida"
Nella Rev 1 il BTC guida e' uscito molto positivo, ma con un sospetto: molte monete negli anni passati avevano
pochi scambi, e la candela "ferma" poteva essere solo un prezzo vecchio, non una moneta in ritardo.
Qui lo stesso segnale si prova con tre ingressi:
  alla chiusura           come nella Rev 1 (ottimista: lo stesso secondo in cui chiude la candela)
  all'apertura successiva primo prezzo scambiato della candela dopo (realistico: se il prezzo era vecchio,
                          qui il recupero e' gia' avvenuto)
  una candela dopo        alla chiusura della candela successiva (in ritardo)
Si scartano anche le candele della moneta senza movimento (massimo = minimo).
Uscita dopo 4 candele dall'ingresso, stop a 1,5 ATR. Costi 0,07 % per ordine + funding.
Uso (nella cartella dati):  python ../misuratore_anticipo_rev2.py
"""
import math, os, sys, time
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import misuratore_ritest_rev1 as base
from misuratore_ritest_rev1 import carica, atr, MONETE, COSTO, FUNDING_ORA

def prova(e, d, stop, H, L, C, i0, barre, ore):
    rischio = (e - stop) * d
    if rischio <= 0: return None
    pct = rischio / e
    if pct < base.MIN_STOP or pct > base.MAX_STOP: return None
    n = len(C); j = i0; r = None
    while j < min(i0 + barre, n - 1):
        j += 1
        if (d == 1 and L[j] <= stop) or (d == -1 and H[j] >= stop): r = -1.0; break
    if r is None: r = (C[j] - e) * d / rischio
    return r - (2 * COSTO + FUNDING_ORA * ore * (j - i0)) / pct

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    print()
    for etichetta, ore in (("CANDELE DA 1 ORA", 1), ("CANDELE DA 4 ORE", 4)):
        dati = {m: carica(m, ore) for m in MONETE}
        dati = {m: b for m, b in dati.items() if b and len(b) > 700}
        b = dati["XBT"]; Tb = [x[0] for x in b]; Cb = [x[4] for x in b]
        Ab = atr([x[2] for x in b], [x[3] for x in b], Cb)
        forti = {Tb[i]: (1 if Cb[i] > Cb[i - 1] else -1) for i in range(1, len(Cb))
                 if Ab[i - 1] and abs(Cb[i] - Cb[i - 1]) / Ab[i - 1] > 2}
        T0, T1 = min(x[0][0] for x in dati.values()), max(x[-1][0] for x in dati.values())
        taglio = T0 + (T1 - T0) * 0.6; anni_tot = (T1 - T0) / (365 * 86400)
        ris = defaultdict(list)
        for m, bb in dati.items():
            if m == "XBT": continue
            T = [x[0] for x in bb]; O = [x[1] for x in bb]; H = [x[2] for x in bb]; L = [x[3] for x in bb]; C = [x[4] for x in bb]
            A = atr(H, L, C)
            for i in range(520, len(C) - 2):
                d = forti.get(T[i])
                if not d or not A[i - 1] or H[i] == L[i]: continue
                z = (C[i] - C[i - 1]) / A[i - 1] * d
                nome = "ritardatarie" if z < 0.5 else ("gia' partite" if z > 1.5 else None)
                if not nome: continue
                anno = time.gmtime(T[i]).tm_year; ver = T[i] >= taglio
                for ing, e, i0 in (("alla chiusura", C[i], i), ("all'apertura dopo", O[i + 1], i + 1), ("una candela dopo", C[i + 1], i + 1)):
                    stop = e - d * 1.5 * A[i]
                    r = prova(e, d, stop, H, L, C, i0 if ing != "all'apertura dopo" else i0 - 1 + 1, 4, ore) if ing != "all'apertura dopo" else None
                    if ing == "all'apertura dopo":
                        # entra all'apertura della candela i+1: la candela i+1 conta come prima candela tenuta
                        rischio = 1.5 * A[i]; pct = rischio / e; rr = None; j = i
                        if not (base.MIN_STOP <= pct <= base.MAX_STOP): continue
                        while j < min(i + 4, len(C) - 1):
                            j += 1
                            if (d == 1 and L[j] <= stop) or (d == -1 and H[j] >= stop): rr = -1.0; break
                        if rr is None: rr = (C[j] - e) * d / rischio
                        r = rr - (2 * COSTO + FUNDING_ORA * ore * (j - i)) / pct
                    if r is not None: ris[(nome, d, ing)].append((anno, ver, r))
        anni = sorted({a for v in ris.values() for a, _, _ in v})
        print(f"{etichetta}: {len(dati)} monete. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(taglio))}")
        print(f"{'':3}{'Gruppo':14}{'Verso':7}{'Ingresso':20}{'N/anno':>7}{'Vinte':>6}{'R prova':>9}{'R verif.':>9}" + "".join(f"{a:>7}" for a in anni))
        for nome in ("ritardatarie", "gia' partite"):
            for d in (1, -1):
                for ing in ("alla chiusura", "all'apertura dopo", "una candela dopo"):
                    g = ris.get((nome, d, ing), [])
                    if not g: continue
                    pr = [r for _, v, r in g if not v]; ve = [r for _, v, r in g if v]; tot = [r for *_, r in g]
                    mt = media(tot); sd = math.sqrt(media([(x - mt) ** 2 for x in tot])); t = mt / (sd / math.sqrt(len(tot))) if sd else 0
                    s = "🟢" if len(ve) >= 30 and media(pr) > 0.05 and media(ve) > 0.05 and t >= 3 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
                    celle = "".join(f"{media([r for a2, _, r in g if a2 == a]):>+7.2f}" for a in anni)
                    print(f"{s} {nome:14}{'long' if d == 1 else 'short':7}{ing:20}{len(g) / anni_tot:>7.0f}"
                          f"{sum(1 for r in tot if r > 0) / len(tot) * 100:>5.0f}%{media(pr):>+9.2f}{media(ve):>+9.2f}{celle}")
            print()
    print("Se il vantaggio sparisce \"all'apertura dopo\", era un prezzo vecchio e non un vero ritardo: non e' tradabile.")

if __name__ == "__main__":
    main()
