#!/usr/bin/env python3
"""
TEST INTRADAY - Rev 3  (perpetui Kraken, 13 monete liquide, solo long)
Pullback dentro il trend ORARIO a struttura (massimi e minimi crescenti), minimo su un SUPPORTO orizzontale.
Novita' rispetto alla Rev 2:
  - uscita come Cecchino/Segugio, in R (R = distanza dello stop iniziale), SENZA limite di tempo:
      pareggio quando il guadagno arriva a +1 R; da li' lo stop segue il massimo a 1,5 R;
      oltre +3 R la distanza si allarga: 1,5 + 0,10 x (guadagno - 3) R.
    Confronto: stessa uscita con distanza base 1,0 R invece di 1,5.
    (tetto tecnico di 30 giorni, solo per sicurezza: si conta quante volte scatta)
  - uscite e ordini limite simulati sulle candele da 15 minuti; lo stop esce a min(stop, apertura) se c'e' un buco
  - selettivita': profondita' del pullback P = 3, 4, 5, 6 ATR orari; supporto toccato almeno 1 o 2 volte
    (numero di pivot minimi delle 200 ore prima del massimo entro 0,5 ATR dal livello)
  - due modi di entrare:
      MERCATO = come Rev 2: il minimo del pullback e' su un supporto, la candela oraria chiude sopra il massimo
                della precedente -> si compra alla chiusura. Stop 0,3 ATR sotto il minimo.
      LIMITE  = ordine di acquisto limite appoggiato al supporto PRIMA che il prezzo ci arrivi:
                alla chiusura di ogni ora, se c'e' il trend a struttura e un supporto S sotto il prezzo
                (entro 3 ATR, non ancora toccato in questo pullback, non sotto l'ultimo minimo crescente di
                oltre 0,5 ATR) tale che dal massimo hh al prezzo d'ordine ci siano almeno P ATR:
                ordine a S + 0,2 ATR, valido 12 ore, annullato se il prezzo torna sopra hh.
                Eseguito se una candela da 15 min scende SOTTO il prezzo d'ordine. Stop S - 0,5 o S - 1,0 ATR.
                Se nella candela dell'esecuzione si tocca anche lo stop, si conta lo stop (prudente).
Costi:  MERCATO 0,07 % x2 + spread + 0,05 % ritardo + funding
        LIMITE  0,02 % (commissione maker) + 0,07 % in uscita + meta' spread + funding
Portafoglio: rischio 0,75 %, max 5 posizioni, leva 3. Decisioni SOLO sulla prova (primo 60 %).

Uso (nella cartella dati):  python ../test_intraday_rev3.py
"""
import bisect, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, COSTO, FUNDING_ORA
from genetico_btc_guida_rev1 import portafoglio
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from test_intraday_rev1 import LIQUIDE, RITARDO, MIN_STOP, MAX_STOP, RISCHIO
from test_intraday_rev2 import Moneta2, TOL, STORIA, PIV

MAKER = 0.0002
PAREGGIO, SOGLIA_FASE2, ALLARGAMENTO = 1.0, 3.0, 0.10
TETTO = 30 * 96          # 30 giorni in candele da 15 min
VALIDITA = 48            # 12 ore in candele da 15 min

class Moneta3(Moneta2):
    def __init__(self, m, barre, sp):
        super().__init__(m, barre, sp)
        self.Q = scarica_15m(m, self.T[0], self.T[-1] + 3600)
        self.QT = [q[0] for q in self.Q]

    def q_da(self, t):
        """Indice della prima candela da 15 min che inizia a t o dopo."""
        return bisect.bisect_left(self.QT, t)

    def h_da(self, t):
        """Indice della prima candela oraria che inizia a t o dopo."""
        return bisect.bisect_left(self.T, t)

    def tocchi(self, livello, k, a):
        return sum(1 for p in self.confermati(self.pl, self.pli, k) if p[0] >= k - STORIA and abs(p[1] - livello) <= TOL * a)

def gestisci(Q, b, e, stop0, R, base):
    """Uscita Cecchino in R dalla candela 15m b. Ritorna (indice, R lordo, tipo, massimo in R)."""
    stop, mx = stop0, e
    for x in range(b, min(len(Q), b + TETTO)):
        t, o, h, l, c = Q[x]
        if l <= stop:
            tipo = "stop" if stop < e else ("pareggio" if stop == e else "trailing")
            return x, (min(stop, o) - e) / R, tipo, (mx - e) / R
        if h > mx:
            mx = h; g = (mx - e) / R
            if g >= PAREGGIO:
                dist = base + (ALLARGAMENTO * (g - SOGLIA_FASE2) if g >= SOGLIA_FASE2 else 0.0)
                stop = max(stop, e, mx - dist * R)
    x = min(len(Q), b + TETTO) - 1
    return x, (Q[x][4] - e) / R, "tetto", (mx - e) / R

def chiudi(M, t_in, x, r, tipo, mfe, e, R, modo):
    pct = R / e; ore = (M.Q[x][0] + 900 - t_in) / 3600
    if modo == "mercato": costo = 2 * COSTO + M.sp + RITARDO
    else:                 costo = MAKER + COSTO + M.sp / 2
    netto = r - (costo + FUNDING_ORA * ore) / pct
    return (t_in, M.Q[x][0] + 900, M.m, 1, pct, netto, r, tipo, ore, mfe)

def mercato(M, P, tocchi, base):
    H, L, C, A, T = M.H, M.L, M.C, M.A, M.T
    ops, i = [], 220
    while i < len(C) - 1:
        k = M.m72[i]; hh = H[k]
        if k >= i - 1 or not (C[i] > H[i - 1] and C[i] < hh): i += 1; continue
        ll = min(L[k:i + 1])
        if (hh - ll) / A[i] < P or not M.trend_orario("struttura", k, ll) or M.tocchi(ll, k, A[i]) < tocchi: i += 1; continue
        e = C[i]; stop = ll - 0.3 * A[i]; R = e - stop
        if not (MIN_STOP <= R / e <= MAX_STOP): i += 1; continue
        t_in = T[i] + 3600; b = M.q_da(t_in)
        if b >= len(M.Q) - 1: break
        x, r, tipo, mfe = gestisci(M.Q, b, e, stop, R, base)
        ops.append(chiudi(M, t_in, x, r, tipo, mfe, e, R, "mercato"))
        i = max(i + 1, M.h_da(M.Q[x][0] + 900))
    return ops, None

def limite(M, P, tocchi, sotto, base):
    H, L, C, A, T, Q = M.H, M.L, M.C, M.A, M.T, M.Q
    ops, ordini, eseguiti, i = [], 0, 0, 220
    while i < len(C) - 1:
        k = M.m72[i]; hh = H[k]; a = A[i]
        if k >= i: i += 1; continue
        ll = min(L[k:i + 1])
        if not M.trend_orario("struttura", k, ll): i += 1; continue
        ultimo_min = M.confermati(M.pl, M.pli, k)[-1][1]
        S = None
        for j, s in reversed(M.confermati(M.pl, M.pli, k)):
            if j < k - STORIA: break
            prezzo = s + 0.2 * a
            if (prezzo < C[i] - 0.1 * a and s >= C[i] - 3 * a and ll > prezzo and s >= ultimo_min - 0.5 * a
                    and (hh - prezzo) / a >= P and M.tocchi(s, k, a) >= tocchi):
                if S is None or s > S: S = s
        if S is None: i += 1; continue
        prezzo = S + 0.2 * a; stop = S - sotto * a; R = prezzo - stop
        if not (MIN_STOP <= R / prezzo <= MAX_STOP): i += 1; continue
        ordini += 1
        t_ord = T[i] + 3600; b = M.q_da(t_ord); fine = min(len(Q), b + VALIDITA); fatto = None
        if b >= len(Q) - 1: break
        x = b
        for x in range(b, fine):
            if Q[x][3] < prezzo: fatto = x; break
            if Q[x][2] > hh: break
        if fatto is None:
            i = max(i + 1, M.h_da(Q[min(x, len(Q) - 1)][0] + 900)); continue
        eseguiti += 1
        e = min(prezzo, Q[fatto][1]); R = e - stop
        if Q[fatto][3] <= stop:
            x, r, tipo, mfe = fatto, (min(stop, Q[fatto][1]) - e) / R, "stop", 0.0
        else:
            x, r, tipo, mfe = gestisci(Q, fatto + 1, e, stop, R, base)
        ops.append(chiudi(M, Q[fatto][0], x, r, tipo, mfe, e, R, "limite"))
        i = max(i + 1, M.h_da(Q[x][0] + 900))
    return ops, (ordini, eseguiti)

def riga(nome, ops, taglio, durata, n_monete, ordini=None):
    media = lambda x: sum(x) / len(x) if x else 0.0
    pr = [o[5] for o in ops if o[0] < taglio]; ve = [o[5] for o in ops if o[0] >= taglio]
    tutte = sorted(o[5] for o in ops); N = max(1, len(ops))
    senza10 = media(tutte[:-10]) if len(tutte) > 20 else 0.0
    lordo = media([o[6] for o in ops]); vinte = media([1.0 if o[5] > 0 else 0.0 for o in ops]) * 100
    quota = lambda t: sum(1 for o in ops if o[7] == t) / N * 100
    corse = sum(1 for o in ops if o[6] >= 3) / N * 100
    ore = media([o[8] for o in ops]); tetto = sum(1 for o in ops if o[7] == "tetto")
    cap, calo, _, fatte = portafoglio([o[:6] for o in ops], RISCHIO, 5, 3.0)
    annuo = (cap ** (1 / durata) - 1) * 100 if cap > 0 and ops else 0.0
    segno = "🟢" if media(pr) > 0.10 and media(ve) > 0.05 and senza10 > 0 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
    es = f"{ordini[1] / ordini[0] * 100:>5.0f}%" if ordini and ordini[0] else "     -"
    s = (f"{segno} {nome:<30}{len(ops) / durata:>5.0f}{es}{lordo:>+7.3f}{media(pr):>+8.3f}{media(ve):>+8.3f}{senza10:>+8.3f}"
         f"{vinte:>5.0f}%{quota('stop'):>5.0f}%{quota('pareggio'):>5.0f}%{quota('trailing'):>5.0f}%{corse:>5.0f}%{ore:>6.0f}"
         f"{annuo:>+7.1f}%{calo * 100:>+6.0f}%")
    return s.replace(".", ",") + (f"  (tetto 30 g: {tetto})" if tetto else "")

INTESTA = (f"   {'variante':<30}{'op/a':>5}{'eseg':>6}{'lordo':>7}{'R prova':>8}{'R verif':>8}{'-top10':>8}{'vinte':>6}"
           f"{'stop':>6}{'pari':>6}{'trail':>6}{'>3R':>6}{'ore':>6}{'annuo':>8}{'calo':>7}")

def main():
    SP = spread(); monete = []
    for m in LIQUIDE:
        b = carica(m, 1)
        if b and len(b) > 5000:
            M = Moneta3(m, b, SP.get(m, SPREAD_DEFAULT))
            if len(M.Q) > 20000: monete.append(M)
            else: print(f"{m}: dati 15 min insufficienti, esclusa")
    t0 = max(max(M.T[0], M.Q[0][0]) for M in monete); t1 = min(min(M.T[-1], M.Q[-1][0]) for M in monete)
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400); nm = len(monete)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{nm} monete liquide, dal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}.")
    print("op/a = operazioni/anno; eseg = ordini limite eseguiti; lordo = R medio prima dei costi; R prova / R verif = netti;")
    print("-top10 = senza le 10 migliori; stop/pari/trail = come escono (stop iniziale, pareggio, trailing);")
    print(">3R = operazioni arrivate oltre +3 R lordi; ore = durata media; annuo e calo = portafoglio 0,75 %.\n")

    def tutte(f, *a):
        ops, ordini = [], [0, 0]
        for M in monete:
            o, n = f(M, *a)
            ops += [x for x in o if t0 <= x[0] <= t1]
            if n: ordini[0] += n[0]; ordini[1] += n[1]
        return ops, ordini

    print("=== MERCATO (ingresso alla ripartenza) ===")
    print(INTESTA)
    for base in (1.5, 1.0):
        for toc in (1, 2):
            for P in (3, 4, 5, 6):
                ops, _ = tutte(mercato, P, toc, base)
                print(riga(f"P {P} | tocchi {toc} | trail {base}R", ops, taglio, durata, nm), flush=True)
        print()
    print("=== LIMITE (ordine appoggiato al supporto) ===")
    print(INTESTA)
    for base in (1.5, 1.0):
        for sotto in (0.5, 1.0):
            for toc in (1, 2):
                for P in (3, 4, 5, 6):
                    ops, n = tutte(limite, P, toc, sotto, base)
                    print(riga(f"P {P} | toc {toc} | stop -{sotto} | tr {base}R", ops, taglio, durata, nm, n), flush=True)
            print()
    print("Lettura: 🟢 = R > +0,10 in prova, > +0,05 in verifica e positivo senza le 10 migliori; 🟡 = positivo in entrambe.\n"
          "Scegliere guardando SOLO 'R prova'; la verifica dice se regge.")

if __name__ == "__main__":
    main()
