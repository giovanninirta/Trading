#!/usr/bin/env python3
"""
TEST ROTTURA E RITEST - Rev 1  (perpetui Kraken, candele 1h, LONG e SHORT, uscita sui 15 min)
Idea (dai grafici dell'utente): su un livello orizzontale toccato piu' volte c'e' prima una FALSA ROTTURA (1: il prezzo
lo buca e lo riconquista), poi la ROTTURA vera (2); infine il prezzo torna sul livello rotto, che ha cambiato ruolo
(supporto -> resistenza o viceversa), viene respinto e riparte (3 = RITEST, l'ingresso).

LIVELLO   punti di svolta (pivot, 5 candele per lato, confermati) delle ultime 200 ore: un pivot minimo e' un
          SUPPORTO se almeno N pivot minimi stanno entro 0,5 ATR dal suo prezzo (lui compreso); un pivot massimo e'
          una RESISTENZA allo stesso modo. N = 2 o 3.
ROTTURA   SHORT: la candela precedente chiude sopra (o sul) supporto, questa chiude sotto di almeno 0,2 ATR.
          LONG : al contrario sulla resistenza.
INGRESSO  "rottura" = alla chiusura della candela di rottura; stop 0,5 ATR oltre il livello (dall'altra parte)
          "ritest"  = entro 24 candele il prezzo torna a toccare il livello (entro 0,3 ATR) e la candela chiude
                      dalla parte della rottura, nella meta' lontana dal livello (respinta); stop 0,3 ATR oltre
                      l'estremo della candela del ritest. Annullato se prima chiude oltre il livello di 0,5 ATR.
FILTRI    "falsa" = nelle 200 ore prima della rottura una candela ha CHIUSO oltre il livello di almeno 0,2 ATR e entro
          12 candele il prezzo ha richiuso dalla parte di prima (falsa rottura, punto 1 dei grafici)
          "struttura" = per lo short ultimi due pivot massimi e minimi decrescenti, per il long crescenti
          combinazioni: nessuno / falsa / struttura / falsa+struttura
USCITA    come Cecchino in R (R = distanza dello stop): pareggio a +1 R, trailing 1,5 R dal migliore prezzo,
          oltre +3 R + 0,10 R per ogni R; nessun limite di tempo (tetto tecnico 30 giorni). Short = specchio.
COSTI     0,07 % x2 + spread reale + 0,05 % ritardo + funding 0,01 %/8h (anche sugli short, per prudenza).
UNA POSIZIONE ALLA VOLTA PER MONETA. Portafoglio: rischio 0,75 %, max 5 posizioni, leva 3.

METODO (fissato prima):
  1) si sceglie la variante migliore guardando SOLO il netto in PROVA (primo 60 %) sulle 13 monete liquide,
     tra quelle con almeno 40 operazioni in prova
  2) la si giudica sulle 17 monete MAI usate: PROMOSSA se netto > +0,05 R, netto senza le 10 migliori > 0
     e portafoglio annuo > 0
Uso (nella cartella dati):  python ../test_rottura_ritest_rev1.py
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, MONETE, COSTO, FUNDING_ORA
from genetico_btc_guida_rev1 import portafoglio
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from test_intraday_rev1 import LIQUIDE, RITARDO, MIN_STOP, MAX_STOP
from test_pullback_15m_rev1 import Serie

PIV, STORIA, TOL, B, ATTESA = 5, 200, 0.5, 0.2, 24
RISCHIO, TETTO = 0.75, 30 * 96
NUOVE = [m for m in MONETE if m not in LIQUIDE]

class Moneta:
    def __init__(self, m, uno, q, sp):
        self.m, self.sp, self.Q = m, sp, q; self.QT = [x[0] for x in q]
        self.S = Serie(uno, 72, PIV)

def gestisci(Q, b, e, stop0, R, d):
    """Uscita Cecchino in R, direzione d (+1 long, -1 short). Ritorna (indice, R lordo)."""
    stop, best = stop0, e
    for x in range(b, min(len(Q), b + TETTO)):
        t, o, h, l, c = Q[x]
        if (d > 0 and l <= stop) or (d < 0 and h >= stop):
            px = min(stop, o) if d > 0 else max(stop, o)
            return x, (px - e) * d / R
        nuovo = h if d > 0 else l
        if (nuovo - best) * d > 0:
            best = nuovo; g = (best - e) * d / R
            if g >= 1.0:
                dist = 1.5 + (0.10 * (g - 3.0) if g >= 3.0 else 0.0)
                cand = best - d * dist * R
                stop = max(stop, e, cand) if d > 0 else min(stop, e, cand)
    x = min(len(Q), b + TETTO) - 1
    return x, (Q[x][4] - e) * d / R

def struttura(S, i, d):
    x = bisect.bisect_right(S.phi, i - PIV); y = bisect.bisect_right(S.pli, i - PIV)
    if x < 2 or y < 2: return False
    return (S.ph[x - 1][1] - S.ph[x - 2][1]) * d > 0 and (S.pl[y - 1][1] - S.pl[y - 2][1]) * d > 0

def rotture(M, d, N):
    """Eventi di rottura: (i, livello). d = -1 rottura di supporto (short), +1 di resistenza (long)."""
    S = M.S; C, A = S.C, S.A
    piv, idx = (S.pl, S.pli) if d < 0 else (S.ph, S.phi)
    out = []
    for i in range(STORIA + 20, len(C) - 1):
        a = A[i]
        if (C[i] - C[i - 1]) * d <= 0: continue
        j1 = bisect.bisect_right(idx, i - PIV); j0 = bisect.bisect_left(idx, i - STORIA)
        livello = None
        for _, s in reversed(piv[j0:j1]):
            rotto = (C[i - 1] >= s and C[i] < s - B * a) if d < 0 else (C[i - 1] <= s and C[i] > s + B * a)
            if not rotto: continue
            if sum(1 for p in piv[j0:j1] if abs(p[1] - s) <= TOL * a) >= N: livello = s; break
        if livello is not None: out.append((i, livello))
    return out

def candidati(M, d, N):
    """Per ogni rottura: operazione 'rottura' e (se c'e') operazione 'ritest', con il flag di struttura."""
    S = M.S; H, L, C, A, T = S.H, S.L, S.C, S.A, S.T
    out = []
    for i, s in rotture(M, d, N):
        fl = struttura(S, i, d)
        falsa = False
        for j in range(max(1, i - STORIA), i - 1):
            if (C[j] - s) * d > B * A[j] and (C[j - 1] - s) * d <= 0:
                if any((C[k] - s) * d <= 0 for k in range(j + 1, min(j + 13, i))): falsa = True; break
        prove = []
        e = C[i]; stop = s - d * 0.5 * A[i]; prove.append(("rottura", i, e, stop))
        for j in range(i + 1, min(i + 1 + ATTESA, len(C) - 1)):
            a = A[j]
            if (C[j] - s) * d < -0.5 * a: break                              # rientrata con decisione: annullata
            tocca = (H[j] >= s - 0.3 * a) if d < 0 else (L[j] <= s + 0.3 * a)
            meta = (H[j] + L[j]) / 2
            respinta = (C[j] < s and C[j] < meta) if d < 0 else (C[j] > s and C[j] > meta)
            if tocca and respinta:
                estremo = H[j] if d < 0 else L[j]
                prove.append(("ritest", j, C[j], estremo + d * -1 * 0.3 * a)); break
        for modo, j, e, stop in prove:
            R = (e - stop) * d
            if R <= 0 or not (MIN_STOP <= R / e <= MAX_STOP): continue
            t_in = T[j] + 3600; b = bisect.bisect_left(M.QT, t_in)
            if b >= len(M.Q) - 1: continue
            x, r = gestisci(M.Q, b, e, stop, R, d)
            pct = R / e; t_out = M.Q[x][0] + 900; ore = (t_out - t_in) / 3600
            costo = (2 * COSTO + M.sp + RITARDO + FUNDING_ORA * ore) / pct
            out.append(dict(modo=modo, filtro=fl, falsa=falsa, op=(t_in, t_out, M.m, d, pct, r - costo, r)))
    return out

def blocca(ops):
    """Una posizione alla volta per moneta."""
    fine, out = {}, []
    for o in sorted(ops):
        if o[0] >= fine.get(o[2], 0): fine[o[2]] = o[1]; out.append(o)
    return out

def media(v): return sum(v) / len(v) if v else 0.0

def misura(ops, taglio, durata):
    net = sorted(o[5] for o in ops)
    pr = [o[5] for o in ops if o[0] < taglio]; ve = [o[5] for o in ops if o[0] >= taglio]
    cap, calo, curva, _ = portafoglio([o[:6] for o in ops], RISCHIO, 5, 3.0)
    return dict(n=len(ops) / durata, npr=len(pr), lordo=media([o[6] for o in ops]), netto=media(net), prova=media(pr),
                verif=media(ve), s10=media(net[:-10]), annuo=(cap ** (1 / durata) - 1) if cap > 0 and ops else -1, calo=calo, curva=curva)

def anni(curva, a0, a1):
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    return "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+7.1f}%"
                   for a in range(a0, a1 + 1)).replace(".", ",")

def main():
    SP = spread(); gruppi = {"13": [], "17": []}
    for nome, lista in (("13", LIQUIDE), ("17", NUOVE)):
        for m in lista:
            b = carica(m, 1)
            if not b or len(b) < 5000: continue
            q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
            if len(q) >= 20000: gruppi[nome].append(Moneta(m, b, q, SP.get(m, SPREAD_DEFAULT)))
    liq = gruppi["13"]
    t0 = max(max(M.S.T[0], M.Q[0][0]) for M in liq); t1 = min(min(M.S.T[-1], M.Q[-1][0]) for M in liq)
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{len(liq)} liquide + {len(gruppi['17'])} nuove, dal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}.")
    print("Colonne: op/a, lordo e netto medi in R, netto in prova e verifica, netto senza le 10 migliori, portafoglio.\n")
    cand = {}
    for g, monete in gruppi.items():
        for dd in (-1, 1):
            for N in (2, 3):
                cand[(g, dd, N)] = [c for M in monete for c in candidati(M, dd, N) if t0 <= c["op"][0] <= t1]
    righe = []
    testa = (f"   {'direzione | tocchi | ingresso | filtro':<44}{'op/a':>6}{'lordo':>8}{'netto':>8}{'prova':>8}{'verif':>8}"
             f"{'-top10':>8}{'annuo':>8}{'calo':>7}   ||{'op/a':>6}{'netto':>8}{'-top10':>8}{'annuo':>8}{'calo':>7}")
    print(f"   {'':<44}{'---------------- 13 LIQUIDE ----------------':^61}   ||{'--------- 17 NUOVE ---------':^37}")
    print(testa)
    for dd in (-1, 1):
        for N in (2, 3):
            for modo in ("rottura", "ritest"):
                for filtro in ("nessuno", "falsa", "struttura", "falsa+strutt"):
                    ok_f = lambda c: (("falsa" not in filtro or c["falsa"]) and ("strutt" not in filtro or c["filtro"]))
                    sel = lambda g: blocca([c["op"] for c in cand[(g, dd, N)] if c["modo"] == modo and ok_f(c)])
                    a, b = misura(sel("13"), taglio, durata), misura(sel("17"), taglio, durata)
                    nome = f"{'SHORT' if dd < 0 else 'LONG'} | {N} tocchi | {modo} | {filtro}"
                    righe.append((nome, a, b))
                    print((f"   {nome:<44}{a['n']:>6.0f}{a['lordo']:>+8.3f}{a['netto']:>+8.3f}{a['prova']:>+8.3f}{a['verif']:>+8.3f}"
                           f"{a['s10']:>+8.3f}{a['annuo'] * 100:>+7.1f}%{a['calo'] * 100:>+6.0f}%   ||{b['n']:>6.0f}{b['netto']:>+8.3f}"
                           f"{b['s10']:>+8.3f}{b['annuo'] * 100:>+7.1f}%{b['calo'] * 100:>+6.0f}%").replace(".", ","), flush=True)
            print()
    valide = [r for r in righe if r[1]["npr"] >= 40]
    if not valide: print("Nessuna variante con almeno 40 operazioni in prova."); return
    nome, a, b = max(valide, key=lambda r: r[1]["prova"])
    a0, a1 = time.gmtime(t0).tm_year, time.gmtime(t1).tm_year
    print(f"=== SCELTA (miglior netto in PROVA sulle 13 liquide): {nome} ===")
    print(f"   anno per anno           " + "".join(f"{x:>8}" for x in range(a0, a1 + 1)))
    print(f"   13 liquide              {anni(a['curva'], a0, a1)}")
    print(f"   17 nuove                {anni(b['curva'], a0, a1)}")
    ok = b["netto"] > 0.05 and b["s10"] > 0 and b["annuo"] > 0
    print(f"=== VERDETTO sulle 17 nuove: netto {b['netto']:+.3f} R (serve > +0,05), senza le 10 migliori {b['s10']:+.3f} R "
          f"(serve > 0), annuo {b['annuo'] * 100:+.1f} % (serve > 0) -> {'PROMOSSA' if ok else 'BOCCIATA'} ===".replace(".", ",")
          .replace("+0,05)", "+0,05)"))

if __name__ == "__main__":
    main()
