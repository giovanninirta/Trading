#!/usr/bin/env python3
"""
TEST PULLBACK 15 MIN - Rev 1  (perpetui Kraken, 13 monete liquide, solo long, ingresso a MERCATO)
Stessa regola della Rev 3/4 (miglior versione: uscita Cecchino 1,5 R senza limite di tempo, nessun parziale):
  massimo hh delle ultime W candele; trend a struttura (pivot massimi e minimi crescenti, il pullback non rompe
  l'ultimo minimo); profondita' >= P ATR; minimo del pullback entro 0,5 ATR da >= N pivot minimi delle S candele
  prima del massimo; ripartenza = chiusura sopra il massimo della candela precedente; stop 0,3 ATR sotto il minimo;
  stop tra 0,3 % e 10 % (sotto lo 0,3 % i costi mangerebbero tutto).
  Uscita: pareggio a +1 R, trailing 1,5 R dal massimo, oltre +3 R + 0,10 R per ogni R. Gestita sui 15 min.

A) RIFERIMENTO 1h, con e senza RIENTRI: dopo uno stop si puo' rientrare sullo stesso pullback (stesso massimo hh)
   se si forma una nuova ripartenza che rispetta tutte le condizioni? (Rev 3/4: si'; analisi ingressi: no)
B) 15 MIN, stessa forma: W = 72, pivot 5, storia 200 candele (stesso disegno, 4 volte piu' piccolo nel tempo)
C) 15 MIN, stessa durata: W = 288, pivot 20, storia 800 candele (stesse ore della versione 1h, ingresso a 15 min)

Costi: 0,07 % x2 + spread reale + 0,05 % ritardo + funding. Colonna "costo" = costo medio in R.
Uso (nella cartella dati):  python ../test_pullback_15m_rev1.py
"""
import bisect, os, sys, time
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, atr, COSTO, FUNDING_ORA
from genetico_btc_guida_rev1 import portafoglio
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from test_intraday_rev1 import LIQUIDE, RITARDO, MIN_STOP, MAX_STOP, RISCHIO
from test_intraday_rev3 import gestisci

class Serie:
    def __init__(self, barre, W, piv):
        self.T = [b[0] for b in barre]; self.H = [b[2] for b in barre]
        self.L = [b[3] for b in barre]; self.C = [b[4] for b in barre]
        self.A = atr(self.H, self.L, self.C); self.n = piv
        H, L = self.H, self.L
        self.ph, self.pl = [], []
        # pivot con finestre scorrevoli (veloce anche con pivot larghi)
        mxq, mnq = deque(), deque()
        for j in range(len(H)):
            while mxq and H[mxq[-1]] <= H[j]: mxq.pop()
            mxq.append(j)
            while mnq and L[mnq[-1]] >= L[j]: mnq.pop()
            mnq.append(j)
            if mxq[0] <= j - 2 * piv - 1: mxq.popleft()
            if mnq[0] <= j - 2 * piv - 1: mnq.popleft()
            c = j - piv
            if c >= piv:
                if H[mxq[0]] == H[c]: self.ph.append((c, H[c]))
                if L[mnq[0]] == L[c]: self.pl.append((c, L[c]))
        self.phi = [p[0] for p in self.ph]; self.pli = [p[0] for p in self.pl]
        q, self.mw = deque(), []
        for j, h in enumerate(H):
            while q and H[q[-1]] <= h: q.pop()
            q.append(j)
            if q[0] <= j - W: q.popleft()
            self.mw.append(q[0])

class Moneta:
    def __init__(self, m, sp, uno, quindici):
        self.m, self.sp, self.uno, self.Q = m, sp, uno, quindici
        self.QT = [q[0] for q in quindici]; self.serie = {}
    def s(self, tf, W, piv):
        k = (tf, W, piv)
        if k not in self.serie: self.serie[k] = Serie(self.uno if tf == 60 else self.Q, W, piv)
        return self.serie[k]

def operazioni(M, tf, W, piv, storia, P, tocchi, rientri, tol=0.5):
    S = M.s(tf, W, piv); H, L, C, A, T, n = S.H, S.L, S.C, S.A, S.T, S.n
    durata = tf * 60; ops, usati, i = [], set(), max(storia, 4 * piv, W) + 20
    while i < len(C) - 1:
        k = S.mw[i]; hh = H[k]
        if k >= i - 1 or not (C[i] > H[i - 1] and C[i] < hh) or (not rientri and k in usati): i += 1; continue
        ll = min(L[k:i + 1]); a = A[i]
        if (hh - ll) / a < P: i += 1; continue
        x = bisect.bisect_right(S.phi, k - n); y = bisect.bisect_right(S.pli, k - n)
        if x < 2 or y < 2 or not (S.ph[x - 1][1] > S.ph[x - 2][1] and S.pl[y - 1][1] > S.pl[y - 2][1] and ll > S.pl[y - 1][1]):
            i += 1; continue
        j0 = bisect.bisect_left(S.pli, k - storia)
        if sum(1 for p in S.pl[j0:y] if abs(p[1] - ll) <= tol * a) < tocchi: i += 1; continue
        e = C[i]; stop = ll - 0.3 * a; R = e - stop
        if not (MIN_STOP <= R / e <= MAX_STOP): i += 1; continue
        t_in = T[i] + durata; b = bisect.bisect_left(M.QT, t_in)
        if b >= len(M.Q) - 1: break
        xx, r, tipo, mfe = gestisci(M.Q, b, e, stop, R, 1.5)
        pct = R / e; t_out = M.Q[xx][0] + 900; ore = (t_out - t_in) / 3600
        costo = (2 * COSTO + M.sp + RITARDO + FUNDING_ORA * ore) / pct
        ops.append((t_in, t_out, M.m, 1, pct, r - costo, r, tipo, ore, mfe, costo))
        usati.add(k)
        i = max(i + 1, bisect.bisect_left(T, t_out))
    return ops

def riga(nome, ops, taglio, durata):
    media = lambda v: sum(v) / len(v) if v else 0.0
    pr = [o[5] for o in ops if o[0] < taglio]; ve = [o[5] for o in ops if o[0] >= taglio]
    tutte = sorted(o[5] for o in ops); N = max(1, len(ops))
    cap, calo, _, _ = portafoglio([o[:6] for o in ops], RISCHIO, 5, 3.0)
    annuo = (cap ** (1 / durata) - 1) * 100 if cap > 0 and ops else 0.0
    segno = "🟢" if media(pr) > 0.10 and media(ve) > 0.05 and media(tutte[:-10]) > 0 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
    s = (f"{segno} {nome:<28}{len(ops) / durata:>6.0f}{media([o[6] for o in ops]):>+7.3f}{media([o[10] for o in ops]):>7.2f}"
         f"{media(pr):>+8.3f}{media(ve):>+8.3f}{(media(tutte[:-10]) if len(tutte) > 20 else 0):>+8.3f}"
         f"{media([1.0 if o[5] > 0 else 0.0 for o in ops]) * 100:>5.0f}%{sum(1 for o in ops if o[7] == 'stop') / N * 100:>5.0f}%"
         f"{sum(1 for o in ops if o[6] >= 3) / N * 100:>5.0f}%{media([o[8] for o in ops]):>6.0f}{annuo:>+7.1f}%{calo * 100:>+6.0f}%")
    return s.replace(".", ",")

INTESTA = (f"   {'variante':<28}{'op/a':>6}{'lordo':>7}{'costo':>7}{'R prova':>8}{'R verif':>8}{'-top10':>8}{'vinte':>6}"
           f"{'stop':>6}{'>3R':>6}{'ore':>6}{'annuo':>8}{'calo':>7}")

def main():
    SP = spread(); monete = []
    for m in LIQUIDE:
        b = carica(m, 1)
        if not b or len(b) < 5000: continue
        q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
        if len(q) > 20000: monete.append(Moneta(m, SP.get(m, SPREAD_DEFAULT), b, q))
    t0 = max(max(M.uno[0][0], M.Q[0][0]) for M in monete); t1 = min(min(M.uno[-1][0], M.Q[-1][0]) for M in monete)
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{len(monete)} monete, dal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}.")
    print("lordo = R medio prima dei costi; costo = costo medio in R; R prova / R verif = netti; -top10 = senza le 10")
    print("migliori; stop = % uscite allo stop iniziale; >3R = % arrivate oltre +3 R; ore = durata media.\n")
    def tutte(*a):
        ops = []
        for M in monete: ops += [o for o in operazioni(M, *a) if t0 <= o[0] <= t1]
        return ops

    print("=== A) RIFERIMENTO 1h: con e senza rientri sullo stesso pullback ===")
    print(INTESTA)
    for P in (4, 5):
        for rientri in (True, False):
            print(riga(f"1h P {P} | 2 toc | rientri {'si' if rientri else 'no'}", tutte(60, 72, 5, 200, P, 2, rientri), taglio, durata), flush=True)
    print()
    for nome, W, piv, storia in (("B) 15 MIN, stessa forma (72 candele, pivot 5, storia 200)", 72, 5, 200),
                                 ("C) 15 MIN, stessa durata (288 candele, pivot 20, storia 800)", 288, 20, 800)):
        print(f"=== {nome} ===")
        print(INTESTA)
        for toc in (1, 2):
            for P in (3, 4, 5, 6):
                print(riga(f"15m P {P} | {toc} toc", tutte(15, W, piv, storia, P, toc, True), taglio, durata), flush=True)
        print(riga(f"15m P 5 | 2 toc | rientri no", tutte(15, W, piv, storia, 5, 2, False), taglio, durata), flush=True)
        print()
    print("Lettura: 🟢 = R > +0,10 in prova, > +0,05 in verifica e positivo senza le 10 migliori; 🟡 = positivo in entrambe.")

if __name__ == "__main__":
    main()
