#!/usr/bin/env python3
"""
TEST INTRADAY - Rev 2  (perpetui Kraken, 13 monete liquide, candele 1h, solo long)
Pullback dentro un trend ORARIO, con conferma del minimo su un SUPPORTO orizzontale.
Tutto e' misurato sul grafico orario. Nessuna ottimizzazione: griglia piccola e fissa, si confrontano i pezzi.

Punti di svolta (pivot): un massimo (minimo) orario piu' alto (basso) delle 5 candele prima e delle 5 dopo.
Si usa un pivot solo quando e' confermato (5 candele dopo), quindi nessun dato futuro.

1) MASSIMO DEL PULLBACK  hh: il massimo delle ultime 72 ore (indice k, almeno 2 candele fa).
2) FILTRO TREND ORARIO, misurato al momento del massimo k (il trend che c'era prima del pullback):
     nessuno   = controllo
     EMA       = EMA 50 sopra EMA 200 orarie e EMA 50 in salita rispetto a 10 ore prima
     struttura = ultimi due pivot massimi crescenti e ultimi due pivot minimi crescenti (massimi e minimi
                 crescenti) e il pullback non rompe l'ultimo minimo crescente (ll sopra l'ultimo pivot minimo)
3) PULLBACK: dal massimo hh il prezzo scende di almeno P ATR orari; ll = minimo da k ad adesso.
4) SUPPORTO: il minimo ll deve cadere entro 0,5 ATR orari da un livello gia' toccato dal prezzo nelle
   200 ore prima del massimo k:
     nessuno   = controllo
     minimi    = almeno un pivot minimo precedente
     min+max   = pivot minimo precedente oppure pivot massimo precedente (vecchia resistenza diventata supporto)
5) RIPARTENZA: la candela chiude sopra il massimo della candela precedente e sotto hh. Ingresso alla chiusura.
6) STOP: ll - 0,3 ATR orari (sotto il supporto).
   Uscite:  2R      = obiettivo 2R, al massimo 48 ore
            massimo = obiettivo il massimo hh del pullback, al massimo 72 ore
            trail   = trailing 3 ATR orari dal massimo raggiunto, al massimo 120 ore

Costi: 0,07 % per ordine x2 + spread reale + 0,05 % ritardo + funding. Stop e obiettivo nella stessa candela = stop.
Colonna "lordo" = R medio PRIMA dei costi: dice se c'e' un vantaggio di base.

Uso (nella cartella dati):  python ../test_intraday_rev2.py
"""
import bisect, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, COSTO
from genetico_btc_guida_rev1 import portafoglio
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from test_intraday_rev1 import Moneta, LIQUIDE, RITARDO, MIN_STOP, MAX_STOP, RISCHIO

FIN, PIV, TOL, STORIA = 72, 5, 0.5, 200

def ema(x, n):
    a, out, k = None, [], 2 / (n + 1)
    for v in x:
        a = v if a is None else a + k * (v - a); out.append(a)
    return out

class Moneta2(Moneta):
    def __init__(self, m, barre, sp):
        super().__init__(m, barre, sp)
        H, L, n = self.H, self.L, len(self.H)
        self.e50, self.e200 = ema(self.C, 50), ema(self.C, 200)
        self.ph, self.pl = [], []      # pivot (indice, prezzo), in ordine
        for i in range(PIV, n - PIV):
            w = range(i - PIV, i + PIV + 1)
            if H[i] == max(H[j] for j in w): self.ph.append((i, H[i]))
            if L[i] == min(L[j] for j in w): self.pl.append((i, L[i]))
        self.phi = [p[0] for p in self.ph]; self.pli = [p[0] for p in self.pl]
        from collections import deque
        q, self.m72 = deque(), []
        for i, h in enumerate(H):
            while q and H[q[-1]] <= h: q.pop()
            q.append(i)
            if q[0] <= i - FIN: q.popleft()
            self.m72.append(q[0])

    def confermati(self, lista, idx, k):
        """Pivot confermati prima dell'indice k (pivot + 5 <= k)."""
        return lista[:bisect.bisect_right(idx, k - PIV)]

    def trend_orario(self, tipo, k, ll):
        if tipo == "nessuno": return True
        if tipo == "EMA":
            return k >= 210 and self.e50[k] > self.e200[k] and self.e50[k] > self.e50[k - 10]
        ph = self.confermati(self.ph, self.phi, k); pl = self.confermati(self.pl, self.pli, k)
        if len(ph) < 2 or len(pl) < 2: return False
        return ph[-1][1] > ph[-2][1] and pl[-1][1] > pl[-2][1] and ll > pl[-1][1]

    def supporto(self, tipo, k, ll, a):
        if tipo == "nessuno": return True
        livelli = [p for p in self.confermati(self.pl, self.pli, k) if p[0] >= k - STORIA]
        if tipo == "min+max":
            livelli += [p for p in self.confermati(self.ph, self.phi, k) if p[0] >= k - STORIA]
        return any(abs(p[1] - ll) <= TOL * a for p in livelli)

def esci(M, i, e, stop, uscita, rischio, hh):
    H, L, C, A = M.H, M.L, M.C, M.A; n = len(C)
    limite, tp = {"2R": (48, e + 2 * rischio), "massimo": (72, hh), "trail": (120, None)}[uscita]
    estremo = e; j = i
    while j < min(i + limite, n - 1):
        j += 1
        if L[j] <= stop: return j, (stop - e) / rischio
        if tp is not None and H[j] >= tp: return j, (tp - e) / rischio
        if uscita == "trail":
            estremo = max(estremo, H[j]); stop = max(stop, estremo - 3 * A[j])
    return j, (C[j] - e) / rischio

def pullback(M, P, trend, supp, uscita):
    H, L, C, A, T = M.H, M.L, M.C, M.A, M.T
    ops, i = [], 220
    while i < len(C) - 1:
        k = M.m72[i]; hh = H[k]
        if k >= i - 1 or not (C[i] > H[i - 1] and C[i] < hh): i += 1; continue
        ll = min(L[k:i + 1])
        if (hh - ll) / A[i] < P or not M.trend_orario(trend, k, ll) or not M.supporto(supp, k, ll, A[i]): i += 1; continue
        e = C[i]; stop = ll - 0.3 * A[i]; rischio = e - stop; pct = rischio / e
        if not (MIN_STOP <= pct <= MAX_STOP): i += 1; continue
        j, r = esci(M, i, e, stop, uscita, rischio, hh)
        ops.append((T[i] + 3600, T[j] + 3600, M.m, 1, pct, r - M.costo(pct, j - i), r))
        i = j + 1
    return ops

def riga(nome, ops, taglio, durata, n_monete):
    media = lambda x: sum(x) / len(x) if x else 0.0
    pr = [o[5] for o in ops if o[0] < taglio]; ve = [o[5] for o in ops if o[0] >= taglio]
    tutte = sorted(o[5] for o in ops)
    senza10 = media(tutte[:-10]) if len(tutte) > 20 else 0.0
    lordo = media([o[6] for o in ops]); vinte = media([1.0 if o[5] > 0 else 0.0 for o in ops]) * 100
    cap, calo, _, fatte = portafoglio([o[:6] for o in ops], RISCHIO, 5, 3.0)
    annuo = (cap ** (1 / durata) - 1) * 100 if cap > 0 else -100
    segno = "🟢" if media(pr) > 0.10 and media(ve) > 0.05 and senza10 > 0 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
    return (f"{segno} {nome:<36}{len(ops) / durata:>6.0f}{len(ops) / durata / n_monete:>6.0f}{lordo:>+7.3f}{media(pr):>+8.3f}"
            f"{media(ve):>+8.3f}{senza10:>+8.3f}{vinte:>6.0f}%{annuo:>+7.1f}%{calo * 100:>+6.0f}%").replace(".", ",")

INTESTA = (f"   {'trend | supporto | P | uscita':<36}{'op/a':>6}{'/mon':>6}{'lordo':>7}{'R prova':>8}{'R verif':>8}"
           f"{'-top10':>8}{'vinte':>7}{'annuo':>8}{'calo':>7}")

def main():
    SP = spread(); monete = []
    for m in LIQUIDE:
        b = carica(m, 1)
        if b and len(b) > 5000: monete.append(Moneta2(m, b, SP.get(m, SPREAD_DEFAULT)))
    t0 = max(M.T[0] for M in monete); t1 = min(M.T[-1] for M in monete)
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400); nm = len(monete)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{nm} monete liquide, dal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}.")
    print("op/a = operazioni/anno in totale, /mon = per moneta; lordo = R medio prima dei costi;")
    print("R prova / R verif = R medio costi inclusi; -top10 = senza le 10 migliori; annuo e calo = portafoglio 0,75 %.\n")
    def tutte(*a):
        ops = []
        for M in monete: ops += [o for o in pullback(M, *a) if t0 <= o[0] <= t1]
        return ops
    print("=== A) tutte le combinazioni trend x supporto, uscita 2R ===")
    print(INTESTA)
    for trend in ("nessuno", "EMA", "struttura"):
        for supp in ("nessuno", "minimi", "min+max"):
            for P in (2, 3, 4):
                print(riga(f"{trend} | {supp} | {P} | 2R", tutte(P, trend, supp, "2R"), taglio, durata, nm), flush=True)
        print()
    print("=== B) altre uscite, P = 3 ===")
    print(INTESTA)
    for uscita in ("massimo", "trail"):
        for trend in ("nessuno", "EMA", "struttura"):
            for supp in ("nessuno", "minimi", "min+max"):
                print(riga(f"{trend} | {supp} | 3 | {uscita}", tutte(3, trend, supp, uscita), taglio, durata, nm), flush=True)
        print()
    print("Lettura: confrontare le righe con 'nessuno' (controllo) con quelle con filtro: se il filtro trend o il\n"
          "supporto servono, il 'lordo' e l'R in prova devono salire. 🟢 = R > +0,10 in prova, > +0,05 in verifica e\n"
          "positivo senza le 10 migliori; 🟡 = positivo in entrambe; 🔴 = no.")

if __name__ == "__main__":
    main()
