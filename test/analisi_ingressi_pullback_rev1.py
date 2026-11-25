#!/usr/bin/env python3
"""
ANALISI INGRESSI PULLBACK - Rev 1  (variante di riferimento: Rev 3/4, MERCATO, P 5, supporto 2 tocchi, trailing 1,5 R)
Domanda: perche' cosi' poche operazioni? Quale condizione blocca di piu', e le operazioni bloccate sono buone?

Condizioni d'ingresso (su candele 1h):
  R  ripartenza: chiusura sopra il massimo della candela precedente e sotto il massimo hh (72 ore)
  P  profondita': hh - minimo >= P ATR orari
  T1 almeno 2 pivot massimi e 2 pivot minimi prima del massimo
  T2 massimi crescenti     T3 minimi crescenti     T4 il pullback non rompe l'ultimo minimo crescente
  S  supporto: almeno N pivot minimi (200 ore prima del massimo) entro 0,5 ATR dal minimo del pullback
  L  stop tra 0,3 % e 10 %
  B  una posizione alla volta per moneta (blocco)

1) IMBUTO: candele di ripartenza con profondita' >= 3 ATR, contando ogni pullback (massimo hh) una volta;
   quanti passano ogni condizione, in sequenza.
2) CHI BLOCCA DA SOLO: tra i pullback che passano R e P 5, quanti falliscono SOLO quella condizione
   (cioe' sarebbero presi se la togliessimo) e come sarebbero andati.
3) SCENARI: si toglie o si allenta una condizione alla volta e si ricalcola tutto (con uscita Cecchino 1,5 R
   sui 15 min, costi inclusi, SENZA blocco B, che si misura a parte).

Uso (nella cartella dati):  python ../analisi_ingressi_pullback_rev1.py
"""
import bisect, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from test_intraday_rev1 import LIQUIDE, MIN_STOP, MAX_STOP
from test_intraday_rev3 import Moneta3, gestisci, chiudi

BASE = dict(P=5, tocchi=2, tol=0.5, storia=200, finestra=72, piv=5, trend=("T1", "T2", "T3", "T4"))

def pivot(H, L, n):
    ph, pl = [], []
    for i in range(n, len(H) - n):
        if H[i] == max(H[i - n:i + n + 1]): ph.append((i, H[i]))
        if L[i] == min(L[i - n:i + n + 1]): pl.append((i, L[i]))
    return ph, [p[0] for p in ph], pl, [p[0] for p in pl]

def massimi(H, w):
    from collections import deque
    q, out = deque(), []
    for i, h in enumerate(H):
        while q and H[q[-1]] <= h: q.pop()
        q.append(i)
        if q[0] <= i - w: q.popleft()
        out.append(q[0])
    return out

class Analisi:
    def __init__(self, M):
        self.M = M; self.piv = {}; self.mx = {}
    def pv(self, n):
        if n not in self.piv: self.piv[n] = pivot(self.M.H, self.M.L, n)
        return self.piv[n]
    def mw(self, w):
        if w not in self.mx: self.mx[w] = massimi(self.M.H, w)
        return self.mx[w]

    def candidati(self, c):
        """Tutte le candele di ripartenza con le condizioni valutate secondo la configurazione c."""
        M = self.M; H, L, C, A = M.H, M.L, M.C, M.A
        ph, phi, pl, pli = self.pv(c["piv"]); m = self.mw(c["finestra"]); n = c["piv"]
        out = []
        for i in range(400, len(C) - 1):
            k = m[i]; hh = H[k]
            if k >= i - 1 or not (C[i] > H[i - 1] and C[i] < hh): continue
            ll = min(L[k:i + 1]); prof = (hh - ll) / A[i]
            if prof < 3: continue
            a = bisect.bisect_right(phi, k - n); b = bisect.bisect_right(pli, k - n)
            f = {}
            f["T1"] = a >= 2 and b >= 2
            f["T2"] = f["T1"] and ph[a - 1][1] > ph[a - 2][1]
            f["T3"] = f["T1"] and pl[b - 1][1] > pl[b - 2][1]
            f["T4"] = b >= 1 and ll > pl[b - 1][1]
            j0 = bisect.bisect_left(pli, k - c["storia"])
            f["tocchi"] = sum(1 for p in pl[j0:b] if abs(p[1] - ll) <= c["tol"] * A[i])
            e = C[i]; R = e - (ll - 0.3 * A[i])
            f["L"] = MIN_STOP <= R / e <= MAX_STOP
            out.append((i, k, prof, f, e, R))
        return out

    def passa(self, x, c, salta=()):
        i, k, prof, f, e, R = x
        if "P" not in salta and prof < c["P"]: return False
        for t in c["trend"]:
            if t not in salta and not f[t]: return False
        if "S" not in salta and f["tocchi"] < c["tocchi"]: return False
        if "L" not in salta and not f["L"]: return False
        return True

    def esito(self, x):
        i, k, prof, f, e, R = x; M = self.M
        if R <= 0: return None
        t_in = M.T[i] + 3600; b = M.q_da(t_in)
        if b >= len(M.Q) - 1: return None
        xx, r, tipo, mfe = gestisci(M.Q, b, e, e - R, R, 1.5)
        return chiudi(M, t_in, xx, r, tipo, mfe, e, R, "mercato")

def primi(cand, ok):
    """Un ingresso per pullback (massimo k): la prima candela che soddisfa ok."""
    visti, out = set(), []
    for x in cand:
        if x[1] in visti or not ok(x): continue
        visti.add(x[1]); out.append(x)
    return out

def bloccati(ops):
    """Applica il blocco di una posizione per moneta: ritorna quante restano."""
    fine, n = {}, 0
    for o in sorted(ops):
        if o[0] >= fine.get(o[2], 0): fine[o[2]] = o[1]; n += 1
    return n

def stat(ops, taglio, durata):
    media = lambda v: sum(v) / len(v) if v else 0.0
    pr = [o[5] for o in ops if o[0] < taglio]; ve = [o[5] for o in ops if o[0] >= taglio]
    tutte = sorted(o[5] for o in ops)
    s = (f"{len(ops) / durata:>6.0f}{media([o[6] for o in ops]):>+8.3f}{media(pr):>+8.3f}{media(ve):>+8.3f}"
         f"{(media(tutte[:-10]) if len(tutte) > 20 else 0):>+8.3f}")
    return s.replace(".", ",")

INT = f"{'op/a':>6}{'lordo':>8}{'prova':>8}{'verif':>8}{'-top10':>8}"

def main():
    SP = spread(); A = []
    for m in LIQUIDE:
        b = carica(m, 1)
        if b and len(b) > 5000:
            M = Moneta3(m, b, SP.get(m, SPREAD_DEFAULT))
            if len(M.Q) > 20000: A.append(Analisi(M))
    t0 = max(max(a.M.T[0], a.M.Q[0][0]) for a in A); t1 = min(min(a.M.T[-1], a.M.Q[-1][0]) for a in A)
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{len(A)} monete, dal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}. Riferimento: P 5, 2 tocchi, uscita Cecchino 1,5 R.")
    print("op/a = operazioni/anno; lordo = R medio prima dei costi; prova/verif = R netto; -top10 = senza le 10 migliori.\n")
    c = dict(BASE); cand = {a: [x for x in a.candidati(c) if t0 <= a.M.T[x[0]] <= t1] for a in A}

    # 1) imbuto
    print("=== 1) IMBUTO (ogni pullback contato una volta; profondita' minima 3 ATR) ===")
    passi = [("ripartenza + profondita' >= 3 ATR", lambda x: True),
             ("profondita' >= 5 ATR", lambda x: x[2] >= 5),
             ("+ T1 almeno 2+2 pivot", lambda x: x[2] >= 5 and x[3]["T1"]),
             ("+ T2 massimi crescenti", lambda x: x[2] >= 5 and x[3]["T2"]),
             ("+ T3 minimi crescenti", lambda x: x[2] >= 5 and x[3]["T2"] and x[3]["T3"]),
             ("+ T4 non rompe l'ultimo minimo", lambda x: x[2] >= 5 and x[3]["T2"] and x[3]["T3"] and x[3]["T4"]),
             ("+ supporto >= 1 tocco", lambda x: x[2] >= 5 and x[3]["T2"] and x[3]["T3"] and x[3]["T4"] and x[3]["tocchi"] >= 1),
             ("+ supporto >= 2 tocchi", lambda x: x[2] >= 5 and x[3]["T2"] and x[3]["T3"] and x[3]["T4"] and x[3]["tocchi"] >= 2),
             ("+ stop tra 0,3 % e 10 %", lambda x: A[0].passa(x, c))]
    prima = None
    for nome, ok in passi:
        n = sum(len(primi(cand[a], ok)) for a in A) / durata
        perso = f"   (-{(1 - n / prima) * 100:.0f} %)" if prima else ""
        print(f"   {nome:<36}{n:>7.0f} /anno{perso}"); prima = n
    ops_base = [o for a in A for o in (a.esito(x) for x in primi(cand[a], lambda x, a=a: a.passa(x, c))) if o]
    print(f"   {'+ una posizione per moneta (blocco)':<36}{bloccati(ops_base) / durata:>7.0f} /anno")

    # 2) chi blocca da solo
    print("\n=== 2) CHI BLOCCA DA SOLO: pullback (P >= 5) che falliscono SOLO questa condizione ===")
    print(f"   {'condizione':<36}{INT}")
    for nome, salta in [("T1 pochi pivot", ("T1", "T2", "T3")), ("T2 massimi crescenti", ("T2",)),
                        ("T3 minimi crescenti", ("T3",)), ("T4 rompe l'ultimo minimo", ("T4",)),
                        ("S supporto (meno di 2 tocchi)", ("S",)), ("L stop fuori limiti", ("L",))]:
        ops = []
        for a in A:
            for x in primi(cand[a], lambda x, a=a, s=salta: a.passa(x, c, s) and not a.passa(x, c)):
                o = a.esito(x)
                if o: ops.append(o)
        print(f"   {nome:<36}{stat(ops, taglio, durata)}")
    print(f"   {'(riferimento: presi da tutti i filtri)':<36}{stat(ops_base, taglio, durata)}")

    # 3) scenari
    print("\n=== 3) SCENARI: una condizione tolta o allentata alla volta (senza blocco per moneta) ===")
    print(f"   {'scenario':<42}{INT}")
    scenari = [("RIFERIMENTO P5, 2 tocchi", {}),
               ("profondita' P 4", {"P": 4}), ("profondita' P 3", {"P": 3}),
               ("supporto 1 tocco", {"tocchi": 1}), ("supporto 0 (nessuno)", {"tocchi": 0}),
               ("tolleranza supporto 1,0 ATR", {"tol": 1.0}), ("storia supporti 500 ore", {"storia": 500}),
               ("senza T2 massimi crescenti", {"trend": ("T1", "T3", "T4")}),
               ("senza T3 minimi crescenti", {"trend": ("T1", "T2", "T4")}),
               ("senza T4", {"trend": ("T1", "T2", "T3")}),
               ("senza trend (T1-T4)", {"trend": ()}),
               ("finestra massimo 120 ore", {"finestra": 120}), ("finestra massimo 48 ore", {"finestra": 48}),
               ("pivot 3 candele per lato", {"piv": 3}), ("pivot 8 candele per lato", {"piv": 8})]
    for nome, mod in scenari:
        cc = dict(BASE); cc.update(mod)
        if any(k in mod for k in ("tol", "storia", "finestra", "piv")):
            cd = {a: [x for x in a.candidati(cc) if t0 <= a.M.T[x[0]] <= t1] for a in A}
        else: cd = cand
        ops = [o for a in A for o in (a.esito(x) for x in primi(cd[a], lambda x, a=a: a.passa(x, cc))) if o]
        print(f"   {nome:<42}{stat(ops, taglio, durata)}   (con blocco: {bloccati(ops) / durata:.0f}/anno)", flush=True)

if __name__ == "__main__":
    main()
