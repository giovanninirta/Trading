#!/usr/bin/env python3
"""
MISURATORE SUPPORTI E RESISTENZE ORIZZONTALI E OBLIQUI - Rev 1
Candele da 1 ora, 30 monete, perpetui Kraken.

Massimo/minimo locale: domina 10 candele per lato (confermato 10 ore dopo, nessuna sbirciata nel futuro).
Livelli ORIZZONTALI: almeno 2 massimi (minimi) locali delle ultime 300 candele entro 0,5 ATR l'uno dall'altro.
Livelli OBLIQUI (trendline): retta per gli ultimi 2 massimi (minimi) locali distanti almeno 20 candele;
  valida finche' nessuna chiusura l'ha superata; scade 300 candele dopo il secondo punto.

Segnali (alla chiusura della candela):
  ROTTURA    chiusura oltre il livello di almeno 0,25 ATR (la candela prima era dall'altra parte)
             long sulle resistenze, short sui supporti. Stop: dall'altra parte del livello di 0,5 ATR.
  RIMBALZO   la candela tocca il livello (entro 0,25 ATR) e chiude respinta: verde sopra il supporto (long),
             rossa sotto la resistenza (short). Stop: oltre il livello e oltre la candela di 0,5 ATR.
Uscite: 2R (obiettivo 2 volte il rischio, massimo 48 candele) e TREND (esce quando chiude oltre il
  minimo/massimo delle ultime 20 candele). Costi 0,07 % per ordine + funding 0,01 % ogni 8 ore.

Uso (nella cartella dati):  python ../misuratore_trendline_rev1.py
Usa carica() e simula() di misuratore_ritest_rev1.py.
"""
import math, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import MONETE, carica, simula, atr

K, TOL, ROTTURA, TOCCO, STORIA, MIN_DIST = 10, 0.5, 0.25, 0.25, 300, 20

def segnali(barre):
    O = [b[1] for b in barre]; H = [b[2] for b in barre]; L = [b[3] for b in barre]; C = [b[4] for b in barre]
    A = atr(H, L, C); n = len(C)
    mass, mini = [], []
    linee = {1: None, -1: None}           # trendline attive: resistenza (1) e supporto (-1): (i1, p1, i2, p2)
    rotti = set(); out = []
    def val(lin, i): i1, p1, i2, p2 = lin; return p1 + (p2 - p1) * (i - i1) / (i2 - i1)
    for i in range(n):
        j = i - K
        if j >= K:
            for d, piv, serie, est in ((1, mass, H, max), (-1, mini, L, min)):
                if serie[j] == est(serie[j - K:j + K + 1]):
                    piv.append((j, serie[j]))
                    # nuova trendline con il pivot precedente abbastanza lontano
                    prec = [p for p in piv[:-1] if j - p[0] >= MIN_DIST]
                    if prec:
                        lin = (prec[-1][0], prec[-1][1], j, serie[j])
                        ok = all((C[k] <= val(lin, k)) if d == 1 else (C[k] >= val(lin, k)) for k in range(lin[0], i))
                        linee[d] = lin if ok else linee[d]
        if i < STORIA: continue
        a = A[i]
        if i % 300 == 0:
            mass[:] = [p for p in mass if p[0] >= i - STORIA]; mini[:] = [p for p in mini if p[0] >= i - STORIA]
        if i % 7 == 0:
            d = 1 if C[i] > sum(C[i - 200:i]) / 200 else -1
            out.append(("Ingresso a caso", d, i, C[i] - d * 1.5 * a))
        verde, rossa = C[i] > O[i], C[i] < O[i]

        # --- trendline
        for d in (1, -1):
            lin = linee[d]
            if not lin: continue
            if i - lin[2] > STORIA: linee[d] = None; continue
            v, vp = val(lin, i), val(lin, i - 1)
            if d == 1:      # resistenza obliqua
                if C[i] > v + ROTTURA * a and C[i - 1] <= vp:
                    out.append(("Rottura obliqua", 1, i, v - TOL * a)); linee[d] = None; continue
                if C[i] > v: linee[d] = None; continue
                if H[i] >= v - TOCCO * a and rossa and H[i - 1] < vp - TOCCO * a:
                    out.append(("Rimbalzo obliquo", -1, i, max(v, H[i]) + TOL * a))
            else:           # supporto obliquo
                if C[i] < v - ROTTURA * a and C[i - 1] >= vp:
                    out.append(("Rottura obliqua", -1, i, v + TOL * a)); linee[d] = None; continue
                if C[i] < v: linee[d] = None; continue
                if L[i] <= v + TOCCO * a and verde and L[i - 1] > vp + TOCCO * a:
                    out.append(("Rimbalzo obliquo", 1, i, min(v, L[i]) - TOL * a))

        # --- livelli orizzontali (si guardano solo quelli vicini al prezzo di questa candela)
        for d, piv in ((1, mass), (-1, mini)):
            basso, alto = min(L[i], C[i - 1]) - TOL * a, max(H[i], C[i - 1]) + TOL * a
            vecchi = [p for p in piv if i - STORIA <= p[0] <= i - 2 * K]
            for pj, pp in [p for p in vecchi if basso <= p[1] <= alto]:
                gruppo = [q for q in vecchi if abs(q[1] - pp) <= TOL * a]
                if len(gruppo) < 2: continue
                liv = sum(q[1] for q in gruppo) / len(gruppo)
                chiave = (d, round(liv / (TOL * a)))
                if chiave in rotti: continue
                if d == 1:
                    if C[i] > liv + ROTTURA * a and C[i - 1] <= liv:
                        rotti.add(chiave); out.append(("Rottura orizzontale", 1, i, liv - TOL * a)); break
                    if H[i] >= liv - TOCCO * a and C[i] < liv and rossa and H[i - 1] < liv - TOCCO * a:
                        out.append(("Rimbalzo orizzontale", -1, i, max(liv, H[i]) + TOL * a)); break
                else:
                    if C[i] < liv - ROTTURA * a and C[i - 1] >= liv:
                        rotti.add(chiave); out.append(("Rottura orizzontale", -1, i, liv + TOL * a)); break
                    if L[i] <= liv + TOCCO * a and C[i] > liv and verde and L[i - 1] > liv + TOCCO * a:
                        out.append(("Rimbalzo orizzontale", 1, i, min(liv, L[i]) - TOL * a)); break
    return out, (O, H, L, C)

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    tutte = {"2R": defaultdict(list), "TREND": defaultdict(list)}; anni = 0; monete = 0
    for m in MONETE:
        barre = carica(m, 1)
        if not barre or len(barre) < STORIA + 500: continue
        monete += 1; anni = max(anni, len(barre) / 24 / 365); taglio = int(len(barre) * 0.6)
        ops, (O, H, L, C) = segnali(barre)
        for uscita in tutte:
            for nome, d, i, stop in ops:
                r = simula(i, d, stop, O, H, L, C, uscita, 1)
                if r is not None: tutte[uscita][(nome, d)].append((i >= taglio, r))
        print(f"{m}: {len(ops)} segnali", flush=True)
    print(f"\nCANDELE DA 1 ORA: {monete} monete, {anni:.1f} anni")
    print(f"{'':3}{'Segnale':22}{'Uscita':8}{'Verso':7}{'N':>7}{'Vinte':>7}{'R prova':>9}{'R verifica':>12}")
    for uscita, gruppi in tutte.items():
        for nome in ("Rottura orizzontale", "Rottura obliqua", "Rimbalzo orizzontale", "Rimbalzo obliquo", "Ingresso a caso"):
            for d in (1, -1):
                g = gruppi.get((nome, d), [])
                if not g: continue
                pr = [r for v, r in g if not v]; ve = [r for v, r in g if v]; tot = [r for _, r in g]
                mt = media(tot); sd = math.sqrt(media([(x - mt) ** 2 for x in tot]))
                t = mt / (sd / math.sqrt(len(tot))) if sd else 0
                if nome == "Ingresso a caso": s = "  "
                elif len(ve) >= 30 and media(pr) > 0.05 and media(ve) > 0.05 and t >= 3: s = "🟢"
                elif media(pr) > 0 and media(ve) > 0: s = "🟡"
                else: s = "🔴"
                print(f"{s} {nome:22}{uscita:8}{'long' if d == 1 else 'short':7}{len(g):>7}"
                      f"{sum(1 for r in tot if r > 0) / len(tot) * 100:>6.0f}%{media(pr):>+9.2f}{media(ve):>+12.2f}")
    print("""
N: operazioni.   R: risultato medio per operazione in multipli del rischio, costi e funding inclusi
(+0,10 con rischio 1 % = +0,1 % del capitale per operazione).   Prova: primo 60 % dei dati, verifica: ultimo 40 %.
🟢 positivo in prova e in verifica, abbastanza casi e troppo netto per essere fortuna
🟡 positivo in entrambi ma non dimostrato   🔴 negativo in almeno un periodo
Ogni segnale deve battere "Ingresso a caso" nello stesso verso e con la stessa uscita.""")

if __name__ == "__main__":
    main()
