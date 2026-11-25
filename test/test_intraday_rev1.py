#!/usr/bin/env python3
"""
TEST INTRADAY - Rev 1  (perpetui Kraken, 13 monete liquide, candele 1h)
Prima scrematura di due idee di ingresso "giornaliere". Nessuna ottimizzazione: poche varianti fisse.
Si guarda soprattutto il RISULTATO MEDIO PER OPERAZIONE (in R, costi inclusi) nella PROVA (primo 60 %);
la VERIFICA (ultimo 40 %) serve solo a vedere se regge.

IDEA A - PULLBACK DENTRO IL TREND GIORNALIERO
  Trend giornaliero (canale 55/20, come Rev 2): acceso quando la chiusura giornaliera supera il massimo delle
  55 giornate precedenti, spento quando scende sotto il minimo delle 20 precedenti. Si usa solo il giorno chiuso.
  Ritracciamento: dal massimo delle ultime 48 ore il prezzo scende di almeno P ATR orari (minimo dopo il massimo).
  Ripartenza: la candela oraria chiude sopra il massimo della candela precedente (e sotto il massimo delle 48 ore).
  Ingresso alla chiusura; stop sotto il minimo del ritracciamento di 0,3 ATR orari.
  Uscite:  2R    = obiettivo 2R, al massimo 48 ore
           trail = trailing 3 ATR orari dal massimo raggiunto, al massimo 120 ore
           24h   = chiusura dopo 24 ore (o allo stop)
  Controllo: lo stesso ingresso SENZA filtro di trend (se va uguale, il trend non serve).

IDEA B - MOMENTO INTRADAY PER FASCIA ORARIA
  Alle ore H UTC si misura la salita dall'apertura della giornata (00:00 UTC) in ATR giornalieri (14 giorni).
  Long se oltre +X, short se sotto -X. Stop a 0,5 ATR giornalieri, chiusura a fine giornata (24:00 UTC).
  Controllo: X = 0 ("sempre", nella direzione del movimento) e ingresso a caso nella stessa ora (base).

Costi: 0,07 % per ordine x2 + spread reale (SPREAD.json) + 0,05 % di ritardo + funding 0,01 %/8h.
Se nella stessa candela si toccano stop e obiettivo, si conta lo stop (prudente).
Portafoglio: rischio 0,75 % per operazione, max 5 posizioni, leva max 3 (come Cecchino/Segugio).

Uso (nella cartella dati):  python ../test_intraday_rev1.py
Solo libreria standard Python 3.8+.
"""
import math, os, sys, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, atr, COSTO, FUNDING_ORA
from genetico_btc_guida_rev1 import portafoglio
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT

LIQUIDE = "XBT AAVE ADA DOGE DOT ETH LINK LTC NEAR SOL TRX UNI XRP".split()
RITARDO = 0.0005
MIN_STOP, MAX_STOP = 0.003, 0.10
RISCHIO = 0.75

# ---------------------------------------------------------------- dati
class Moneta:
    def __init__(self, m, barre, sp):
        self.m, self.sp = m, sp
        self.T = [b[0] for b in barre]; self.O = [b[1] for b in barre]
        self.H = [b[2] for b in barre]; self.L = [b[3] for b in barre]; self.C = [b[4] for b in barre]
        self.A = atr(self.H, self.L, self.C)
        # giornate UTC
        giorni = {}
        for i, t in enumerate(self.T):
            giorni.setdefault(t // 86400, []).append(i)
        self.giorni = sorted(giorni)
        self.ore_giorno = giorni
        dH = [max(self.H[i] for i in giorni[g]) for g in self.giorni]
        dL = [min(self.L[i] for i in giorni[g]) for g in self.giorni]
        dC = [self.C[giorni[g][-1]] for g in self.giorni]
        dA = atr(dH, dL, dC)
        # trend 55/20 e ATR giornaliero validi PER IL GIORNO SUCCESSIVO
        self.trend, self.atr_g = {}, {}
        acceso = False
        for k, g in enumerate(self.giorni):
            if k >= 55:
                if not acceso and dC[k] > max(dH[k - 55:k]): acceso = True
                elif acceso and dC[k] < min(dL[k - 20:k]): acceso = False
            self.trend[g + 1] = acceso
            if k >= 14: self.atr_g[g + 1] = dA[k]

    def massimo48(self):
        """Per ogni candela, indice del massimo delle ultime 48 (calcolato una volta)."""
        if not hasattr(self, "_m48"):
            from collections import deque
            q, out = deque(), []
            for i, h in enumerate(self.H):
                while q and self.H[q[-1]] <= h: q.pop()
                q.append(i)
                if q[0] <= i - 48: q.popleft()
                out.append(q[0])
            self._m48 = out
        return self._m48

    def costo(self, pct, ore):
        return (2 * COSTO + self.sp + RITARDO + FUNDING_ORA * ore) / pct

def esci(M, i, d, e, stop, uscita, rischio):
    """Uscita dalla candela i+1 in poi. Ritorna (indice uscita, R lordo)."""
    H, L, C, A = M.H, M.L, M.C, M.A; n = len(C)
    if uscita == "2R":   limite, tp = 48, e + d * 2 * rischio
    elif uscita == "trail": limite, tp = 120, None
    else:                limite, tp = 24, None
    estremo = e; j = i
    while j < min(i + limite, n - 1):
        j += 1
        if (d > 0 and L[j] <= stop) or (d < 0 and H[j] >= stop): return j, (stop - e) * d / rischio
        if tp is not None and ((d > 0 and H[j] >= tp) or (d < 0 and L[j] <= tp)): return j, 2.0
        if uscita == "trail":
            estremo = max(estremo, H[j]) if d > 0 else min(estremo, L[j])
            stop = max(stop, estremo - 3 * A[j]) if d > 0 else min(stop, estremo + 3 * A[j])
    return j, (C[j] - e) * d / rischio

def op(M, i, j, d, e, rischio, r_lordo):
    pct = rischio / e
    r = r_lordo - M.costo(pct, j - i)
    return (M.T[i] + 3600, M.T[j] + 3600, M.m, d, pct, r)

# ---------------------------------------------------------------- idea A
def pullback(M, P, uscita, filtro):
    H, L, C, A, T = M.H, M.L, M.C, M.A, M.T
    ops, i = [], 60
    while i < len(C) - 1:
        g = T[i] // 86400
        if filtro and not M.trend.get(g, False): i += 1; continue
        k = M.massimo48()[i]; hh = H[k]
        if k >= i - 1: i += 1; continue
        ll = min(L[k:i + 1])
        if (hh - ll) / A[i] < P or not (C[i] > H[i - 1] and C[i] < hh): i += 1; continue
        e = C[i]; stop = ll - 0.3 * A[i]; rischio = e - stop
        if not (MIN_STOP <= rischio / e <= MAX_STOP): i += 1; continue
        j, r = esci(M, i, 1, e, stop, uscita, rischio)
        ops.append(op(M, i, j, 1, e, rischio, r))
        i = j + 1
    return ops

# ---------------------------------------------------------------- idea B
def momento(M, ora, X, lato, caso=None):
    ops = []
    for g in M.giorni:
        idx = M.ore_giorno[g]
        if len(idx) < 24 or g not in M.atr_g: continue
        apertura = M.O[idx[0]]; i = idx[ora - 1]; fine = idx[-1]
        ad = M.atr_g[g]; mov = (M.C[i] - apertura) / ad
        if caso is not None:
            d = caso.choice((1, -1)) if lato == "entrambi" else (1 if lato == "long" else -1)
        else:
            d = 1 if mov > X else (-1 if mov < -X else 0)
            if (lato == "long" and d < 0) or (lato == "short" and d > 0): d = 0
        if d == 0: continue
        e = M.C[i]; rischio = 0.5 * ad; stop = e - d * rischio
        if not (MIN_STOP <= rischio / e <= MAX_STOP): continue
        j, r = i, None
        while j < fine:
            j += 1
            if (d > 0 and M.L[j] <= stop) or (d < 0 and M.H[j] >= stop): r = -1.0; break
        if r is None: r = (M.C[j] - e) * d / rischio
        ops.append(op(M, i, j, d, e, rischio, r))
    return ops

# ---------------------------------------------------------------- statistiche
def riga(nome, ops, taglio, durata):
    def media(x): return sum(x) / len(x) if x else 0.0
    pr = [o[5] for o in ops if o[0] < taglio]; ve = [o[5] for o in ops if o[0] >= taglio]
    tutte = sorted(o[5] for o in ops)
    senza10 = media(tutte[:-10]) if len(tutte) > 20 else 0.0
    costo_medio = media([(2 * COSTO + 0.0015 + RITARDO) / o[4] for o in ops])
    vinte = media([1.0 if o[5] > 0 else 0.0 for o in ops]) * 100
    cap, calo, _, fatte = portafoglio(ops, RISCHIO, 5, 3.0)
    annuo = (cap ** (1 / durata) - 1) * 100 if cap > 0 else -100
    segno = "🟢" if media(pr) > 0.10 and media(ve) > 0.05 and senza10 > 0 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
    s = (f"{segno} {nome:<34}{len(ops) / durata:>6.0f}{len(fatte) / durata:>6.0f}{media(pr):>+8.3f}{media(ve):>+8.3f}"
         f"{senza10:>+8.3f}{vinte:>6.0f}%{costo_medio:>7.2f}{annuo:>+7.1f}%{calo * 100:>+6.0f}%")
    return s.replace(".", ",")

INTESTA = (f"   {'variante':<34}{'op/a':>6}{'prese':>6}{'R prova':>8}{'R verif':>8}{'-top10':>8}{'vinte':>7}"
           f"{'costoR':>7}{'annuo':>8}{'calo':>7}")

def main():
    SP = spread()
    monete = []
    for m in LIQUIDE:
        b = carica(m, 1)
        if b and len(b) > 5000: monete.append(Moneta(m, b, SP.get(m, SPREAD_DEFAULT)))
    t0 = max(M.T[0] for M in monete); t1 = min(M.T[-1] for M in monete)
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{len(monete)} monete liquide ({' '.join(M.m for M in monete)}), dal {d(t0)} al {d(t1)}; "
          f"prova fino al {d(taglio)}.")
    print("op/a = operazioni/anno (tutte le monete), prese = quelle che il portafoglio riesce a prendere;")
    print("R = risultato medio per operazione costi inclusi; -top10 = media senza le 10 migliori;")
    print("costoR = costo medio di un'operazione in R; annuo e calo = portafoglio con rischio 0,75 %.\n")

    def tutte(f):
        ops = []
        for M in monete: ops += [o for o in f(M) if t0 <= o[0] <= t1]
        return ops

    print("=== IDEA A: pullback dentro il trend giornaliero ===")
    print(INTESTA)
    for uscita in ("2R", "trail", "24h"):
        for P in (2, 3, 4, 6):
            print(riga(f"trend | ritracc {P} ATR | {uscita}", tutte(lambda M: pullback(M, P, uscita, True)), taglio, durata), flush=True)
    print("   -- controllo senza filtro di trend --")
    for uscita in ("2R", "trail"):
        for P in (3, 4):
            print(riga(f"NO trend | ritracc {P} ATR | {uscita}", tutte(lambda M: pullback(M, P, uscita, False)), taglio, durata), flush=True)

    print("\n=== IDEA B: momento intraday (chiusura a fine giornata UTC) ===")
    print(INTESTA)
    for ora in (8, 12, 14, 16, 20):
        for lato in ("long", "short"):
            for X in (0.0, 0.3, 0.5, 0.8):
                print(riga(f"ore {ora:>2} UTC | {lato:<5} | oltre {X:.1f} ATRg", tutte(lambda M: momento(M, ora, X, lato)), taglio, durata), flush=True)
        caso = random.Random(ora)
        print(riga(f"ore {ora:>2} UTC | base a caso", tutte(lambda M: momento(M, ora, 0, "entrambi", caso)), taglio, durata), flush=True)
    print("\nLettura: 🟢 = R medio > +0,10 in prova, > +0,05 in verifica e positivo senza le 10 migliori; "
          "🟡 = positivo in entrambe; 🔴 = no.")

if __name__ == "__main__":
    main()
