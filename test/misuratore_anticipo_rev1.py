#!/usr/bin/env python3
"""
MISURATORE ANTICIPO - Rev 1
Tre strategie che entrano PRIMA del movimento. 30 monete, perpetui Kraken, candele da 1 ora e 4 ore.

1) COMPRESSIONE  Il range delle ultime 20 candele e' tra i piu' stretti degli ultimi 500 (entro 1,25 volte
                 il minimo). Si entra dentro il range, nel verso della media a 200 candele, senza aspettare
                 la rottura. Stop: dall'altra parte del range (meno 0,1 ATR). Un segnale ogni 20 candele.
2) CACCIA STOP   Supporto = minimo delle candele da 50 a 4 candele fa (vecchio di almeno 10 candele).
                 Il prezzo lo buca di almeno 0,1 ATR (al massimo 1,5 ATR) e entro 3 candele richiude sopra:
                 long. Stop sotto il minimo della trappola (meno 0,1 ATR). Short: lo stesso sulle resistenze.
3) BTC GUIDA     BTC fa una candela forte (oltre 2 ATR). Le monete che nella stessa candela si sono mosse
                 poco (meno di 0,5 ATR nello stesso verso) si comprano (vendono) scommettendo che recuperino.
                 Confronto: le monete che invece avevano gia' seguito BTC (oltre 1,5 ATR).
Uscite:   1 e 2: OBIETTIVO 2R (o dopo 60 candele) oppure TREND (chiude oltre il minimo/massimo di 20 candele).
          3:     dopo 4 candele (stop a 1,5 ATR).
Riferimento: ingresso a caso nel verso della media a 200 candele, stessa uscita.
Costi: 0,07 % per ordine + funding 0,01 % ogni 8 ore. Risultato in R (R = -1 stop pieno).

Uso (nella cartella dati):  python ../misuratore_anticipo_rev1.py
Solo libreria standard Python 3.8+.
"""
import math, os, sys, time
from collections import defaultdict, deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import misuratore_ritest_rev1 as base
from misuratore_ritest_rev1 import carica, atr, MONETE, COSTO, FUNDING_ORA

def minimo_mobile(v, n, verso=1):
    """out[i] = min (verso 1) o max (verso -1) di v[i-n+1..i]."""
    out, d = [None] * len(v), deque()
    for i, x in enumerate(v):
        while d and (v[d[-1]] >= x if verso == 1 else v[d[-1]] <= x): d.pop()
        d.append(i)
        while d[0] <= i - n: d.popleft()
        if i >= n - 1: out[i] = v[d[0]]
    return out

def simula_tempo(i, d, stop, H, L, C, barre, ore):
    e = C[i]; rischio = (e - stop) * d
    if rischio <= 0: return None
    pct = rischio / e
    if pct < base.MIN_STOP or pct > base.MAX_STOP: return None
    n = len(C); j = i; r = None
    while j < min(i + barre, n - 1):
        j += 1
        if (d == 1 and L[j] <= stop) or (d == -1 and H[j] >= stop): r = -1.0; break
    if r is None: r = (C[j] - e) * d / rischio
    return r - (2 * COSTO + FUNDING_ORA * ore * (j - i)) / pct

def segnali_moneta(barre):
    T = [b[0] for b in barre]; H = [b[2] for b in barre]; L = [b[3] for b in barre]; C = [b[4] for b in barre]
    A = atr(H, L, C); n = len(C)
    hi20, lo20 = minimo_mobile(H, 20, -1), minimo_mobile(L, 20, 1)
    rng = [None if hi20[i] is None else (hi20[i] - lo20[i]) / C[i] for i in range(n)]
    rng_min = minimo_mobile([x if x is not None else 9e9 for x in rng], 500, 1)
    out = []; ultimo_c = -99; ultimo_s = {1: -99, -1: -99}
    s200 = 0.0
    for i in range(n):
        s200 += C[i]
        if i >= 200: s200 -= C[i - 200]
        if i < 520: continue
        a = A[i]; d_trend = 1 if C[i] > s200 / 200 else -1
        if i % 7 == 0:
            out.append(("Ingresso a caso", d_trend, i, C[i] - d_trend * 1.5 * a, "R"))
        # 1) compressione
        if i - ultimo_c >= 20 and rng[i] <= 1.25 * rng_min[i - 1]:
            ultimo_c = i
            stop = lo20[i] - 0.1 * a if d_trend == 1 else hi20[i] + 0.1 * a
            out.append(("Compressione", d_trend, i, stop, "R"))
        # 2) caccia agli stop
        for d in (1, -1):
            if i - ultimo_s[d] < 10: continue
            finestra = range(i - 50, i - 3)
            if d == 1:
                k = min(finestra, key=lambda x: L[x]); liv = L[k]
                trappola = min(L[i - 2:i + 1])
                ok = (k <= i - 10 and liv - 1.5 * a <= trappola < liv - 0.1 * a and C[i] > liv
                      and (C[i - 1] <= liv or L[i] < liv - 0.1 * a))
                stop = trappola - 0.1 * a
            else:
                k = max(finestra, key=lambda x: H[x]); liv = H[k]
                trappola = max(H[i - 2:i + 1])
                ok = (k <= i - 10 and liv + 0.1 * a < trappola <= liv + 1.5 * a and C[i] < liv
                      and (C[i - 1] >= liv or H[i] > liv + 0.1 * a))
                stop = trappola + 0.1 * a
            if ok:
                ultimo_s[d] = i
                out.append(("Caccia agli stop", d, i, stop, "R"))
    return out, (T, H, L, C, A)

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    print()
    for etichetta, ore in (("CANDELE DA 1 ORA", 1), ("CANDELE DA 4 ORE", 4)):
        dati = {m: carica(m, ore) for m in MONETE}
        dati = {m: b for m, b in dati.items() if b and len(b) > 700}
        if "XBT" not in dati: sys.exit("Mancano i dati di BTC.")
        anni_tot = max(len(b) for b in dati.values()) * ore / 24 / 365
        T0 = min(b[0][0] for b in dati.values()); T1 = max(b[-1][0] for b in dati.values())
        taglio_t = T0 + (T1 - T0) * 0.6
        risultati = []                                   # (nome, d, uscita, anno, verifica, R)
        serie = {}
        for m, barre in dati.items():
            ops, (T, H, L, C, A) = segnali_moneta(barre)
            serie[m] = (T, H, L, C, A)
            for nome, d, i, stop, _ in ops:
                for uscita in ("2R", "TREND"):
                    r = base.simula(i, d, stop, None, H, L, C, uscita, ore)
                    if r is not None:
                        risultati.append((nome, d, uscita, time.gmtime(T[i]).tm_year, T[i] >= taglio_t, r))
        # 3) BTC guida
        Tb, Hb, Lb, Cb, Ab = serie["XBT"]
        forti = {}
        for i in range(1, len(Cb)):
            if not Ab[i - 1]: continue
            z = (Cb[i] - Cb[i - 1]) / Ab[i - 1]
            if abs(z) > 2: forti[Tb[i]] = 1 if z > 0 else -1
        for m, (T, H, L, C, A) in serie.items():
            if m == "XBT": continue
            for i in range(520, len(C) - 1):
                if i % 7 == 3:
                    d = 1 if C[i] > C[i - 200] else -1
                    r = simula_tempo(i, d, C[i] - d * 1.5 * A[i], H, L, C, 4, ore)
                    if r is not None:
                        risultati.append(("Ingresso a caso", d, "4 candele", time.gmtime(T[i]).tm_year, T[i] >= taglio_t, r))
                d = forti.get(T[i])
                if not d: continue
                if not A[i - 1]: continue
                z = (C[i] - C[i - 1]) / A[i - 1] * d
                if z < 0.5: nome = "BTC guida: ritardatarie"
                elif z > 1.5: nome = "BTC guida: gia' partite"
                else: continue
                r = simula_tempo(i, d, C[i] - d * 1.5 * A[i], H, L, C, 4, ore)
                if r is not None:
                    risultati.append((nome, d, "4 candele", time.gmtime(T[i]).tm_year, T[i] >= taglio_t, r))

        anni = sorted({x[3] for x in risultati})
        print(f"{etichetta}: {len(dati)} monete, {anni_tot:.1f} anni. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(taglio_t))}")
        print(f"{'':3}{'Strategia':26}{'Uscita':10}{'Verso':7}{'N/anno':>7}{'Vinte':>6}{'R prova':>9}{'R verif.':>9}"
              + "".join(f"{a:>7}" for a in anni))
        gruppi = defaultdict(list)
        for nome, d, u, a, v, r in risultati: gruppi[(nome, u, d)].append((a, v, r))
        ordine = ["Compressione", "Caccia agli stop", "BTC guida: ritardatarie", "BTC guida: gia' partite", "Ingresso a caso"]
        for nome in ordine:
            for u in ("2R", "TREND", "4 candele"):
                for d in (1, -1):
                    g = gruppi.get((nome, u, d))
                    if not g: continue
                    pr = [r for a, v, r in g if not v]; ve = [r for a, v, r in g if v]; tot = [r for _, _, r in g]
                    mt = media(tot); sd = math.sqrt(media([(x - mt) ** 2 for x in tot]))
                    tstat = mt / (sd / math.sqrt(len(tot))) if sd else 0
                    if nome == "Ingresso a caso": s = "  "
                    elif len(ve) >= 30 and media(pr) > 0.05 and media(ve) > 0.05 and tstat >= 3: s = "🟢"
                    elif media(pr) > 0 and media(ve) > 0: s = "🟡"
                    else: s = "🔴"
                    celle = "".join(f"{media([r for a2, _, r in g if a2 == a]):>+7.2f}" if any(a2 == a for a2, _, _ in g)
                                    else f"{'':>7}" for a in anni)
                    print(f"{s} {nome:26}{u:10}{'long' if d == 1 else 'short':7}{len(g) / anni_tot:>7.0f}"
                          f"{sum(1 for r in tot if r > 0) / len(tot) * 100:>5.0f}%{media(pr):>+9.2f}{media(ve):>+9.2f}{celle}")
        print()
    print("""N/anno: operazioni all'anno su tutte le monete.  R: risultato medio per operazione in multipli del rischio,
costi e funding inclusi (+0,10 R con rischio 1 % = +0,1 % del capitale per operazione).
Colonne anni: R medio delle operazioni aperte in quell'anno.
🟢 positivo in prova e in verifica (> +0,05 R), abbastanza casi e troppo netto per essere fortuna
🟡 positivo in entrambi ma non dimostrato   🔴 negativo in almeno un periodo
Per valere qualcosa una strategia deve battere l'"Ingresso a caso" con la stessa uscita.""")

if __name__ == "__main__":
    main()
