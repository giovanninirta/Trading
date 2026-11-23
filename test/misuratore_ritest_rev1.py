#!/usr/bin/env python3
"""
MISURATORE ROTTURA E RITEST - Rev 1
30 monete, perpetui Kraken, candele da 4 ore e giornaliere.

Livelli: un massimo (minimo) locale e' un punto che domina 5 candele per lato. Una RESISTENZA (SUPPORTO)
e' un prezzo dove almeno 2 massimi (minimi) locali delle ultime 200 candele cadono vicini (entro 0,5 ATR).
Una volta chiusa oltre il livello, il livello non vale piu'.

Ingresso long con RITEST:
  1) rottura: chiusura sopra la resistenza di almeno 0,25 ATR
  2) entro 12 candele il prezzo torna a toccare il livello (minimo entro 0,5 ATR sopra il livello)
  3) la candela del ritest chiude sopra il livello ed e' verde (reazione): si entra alla chiusura
  Se prima del ritest il prezzo richiude sotto il livello di 0,5 ATR, la rottura e' fallita e si annulla.
Short: lo stesso, al contrario, sui supporti.
Confronto: stessa rottura SENZA ritest (ingresso alla chiusura della rottura) e ingresso a caso.

Stop (con e senza ritest): sotto il livello rotto di 0,5 ATR (sopra, per lo short).
Due uscite:  OBIETTIVO 2R  (2 volte il rischio, uscita a tempo dopo 60 candele)
             TREND         (esce quando chiude sotto il minimo delle ultime 20 candele, sopra per lo short)
Costi: 0,07 % per ordine + funding 0,01 % ogni 8 ore sulle posizioni aperte.
Risultato in R = multipli del rischio (R = -1 stop pieno). Con rischio 1 % per operazione, +0,10 R = +0,1 % del capitale.

Uso (nella cartella dati):  python ../misuratore_ritest_rev1.py
Solo libreria standard Python 3.8+.
"""
import csv, json, math, os, sys, time, urllib.request
from collections import defaultdict

MONETE = ("XBT ETH SOL XRP ADA DOGE LTC LINK AVAX DOT BCH ATOM UNI XLM ETC FIL AAVE ALGO TRX NEAR "
          "APE SAND MANA AXS CRV COMP OP ARB INJ XTZ").split()
API = "https://futures.kraken.com/api/charts/v1/trade/{sym}/1h?from={a}&to={b}"
K, TOL, ROTTURA, ATTESA, STORIA = 5, 0.5, 0.25, 12, 200
COSTO, FUNDING_ORA = 0.0007, 0.0001 / 8
MIN_STOP, MAX_STOP = 0.003, 0.10

def scarica(sym, path):
    fine = int(time.time()); t = fine - int(4.5 * 365 * 86400); righe = {}
    while t < fine:
        try:
            with urllib.request.urlopen(API.format(sym=sym, a=t, b=min(t + 1500 * 3600, fine)), timeout=30) as r:
                js = json.load(r)
        except Exception as e:
            print(f"{sym}: non scaricabile ({e})"); return False
        for c in js.get("candles", []):
            ts = int(c["time"]) // 1000
            righe[ts] = (ts, c["open"], c["high"], c["low"], c["close"])
        t += 1500 * 3600; time.sleep(0.3)
    if len(righe) < 24 * 200: return False
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows([righe[k] for k in sorted(righe)][:-1])
    return True

def carica(m, ore):
    sym = f"PF_{m}USD"; path = f"{sym}_1h.csv"
    if not os.path.exists(path) and not scarica(sym, path): return None
    righe = []
    with open(path) as f:
        for r in csv.reader(f):
            try: righe.append((int(float(r[0])),) + tuple(float(x) for x in r[1:5]))
            except (ValueError, IndexError): pass
    out, gruppo = [], []
    for b in righe:
        if gruppo and gruppo[0][0] // (ore * 3600) != b[0] // (ore * 3600):
            out.append((gruppo[0][0], gruppo[0][1], max(x[2] for x in gruppo), min(x[3] for x in gruppo), gruppo[-1][4]))
            gruppo = []
        gruppo.append(b)
    return out

def atr(H, L, C, n=14):
    out, a = [], None
    for i in range(len(C)):
        tr = H[i] - L[i] if i == 0 else max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1]))
        a = tr if a is None else (a * (n - 1) + tr) / n
        out.append(a)
    return out

def simula(i, d, stop, O, H, L, C, uscita, ore):
    """Risultato in R, costi inclusi, oppure None se lo stop e' fuori dai limiti."""
    e = C[i]; rischio = (e - stop) * d
    if rischio <= 0: return None
    pct = rischio / e
    if pct < MIN_STOP or pct > MAX_STOP: return None
    tp = e + d * 2 * rischio; n = len(C); j = i
    while True:
        j += 1
        if j >= n: r = (C[n - 1] - e) * d / rischio; j = n - 1; break
        if (d == 1 and L[j] <= stop) or (d == -1 and H[j] >= stop): r = -1.0; break
        if uscita == "2R":
            if (d == 1 and H[j] >= tp) or (d == -1 and L[j] <= tp): r = 2.0; break
            if j - i >= 60: r = (C[j] - e) * d / rischio; break
        else:
            if j - i >= 20:
                w = C[j - 20:j]
                if (d == 1 and C[j] < min(w)) or (d == -1 and C[j] > max(w)): r = (C[j] - e) * d / rischio; break
    costi = 2 * COSTO + FUNDING_ORA * ore * (j - i)
    return r - costi / pct

def segnali(barre):
    T = [b[0] for b in barre]; O = [b[1] for b in barre]; H = [b[2] for b in barre]
    L = [b[3] for b in barre]; C = [b[4] for b in barre]
    A = atr(H, L, C); n = len(C)
    massimi, minimi = [], []                     # pivot confermati: (indice, prezzo)
    rotti = set()                                # livelli gia' rotti (arrotondati)
    attesa = []                                  # rotture in attesa di ritest: (d, livello, indice rottura)
    out = []                                     # (nome, indice, R)
    m200 = None
    for i in range(n):
        j = i - K
        if j >= K:
            if H[j] == max(H[j - K:j + K + 1]): massimi.append((j, H[j]))
            if L[j] == min(L[j - K:j + K + 1]): minimi.append((j, L[j]))
        if i < STORIA: continue
        a = A[i]
        massimi = [p for p in massimi if p[0] >= i - STORIA]; minimi = [p for p in minimi if p[0] >= i - STORIA]
        # ingresso a caso (riferimento), nel verso della media a 200 candele
        if i % 7 == 0:
            d = 1 if C[i] > sum(C[i - 200:i]) / 200 else -1
            out.append(("Ingresso a caso", d, i, C[i] - d * 1.5 * a))
        # ritest delle rotture in attesa
        ancora = []
        for d, liv, ir in attesa:
            if i - ir > ATTESA: continue
            if (d == 1 and C[i] < liv - TOL * a) or (d == -1 and C[i] > liv + TOL * a): continue   # rottura fallita
            tocca = (d == 1 and L[i] <= liv + TOL * a) or (d == -1 and H[i] >= liv - TOL * a)
            reagisce = (d == 1 and C[i] > liv and C[i] > O[i]) or (d == -1 and C[i] < liv and C[i] < O[i])
            if i > ir and tocca and reagisce:
                out.append(("Rottura + ritest", d, i, liv - d * TOL * a))
                continue
            ancora.append((d, liv, ir))
        attesa = ancora
        # nuove rotture
        for d, piv in ((1, massimi), (-1, minimi)):
            # si considerano solo i livelli nella fascia appena attraversata dal prezzo
            if d == 1: basso, alto = C[i - 1] - TOL * a, C[i] - ROTTURA * a + TOL * a
            else:      basso, alto = C[i] + ROTTURA * a - TOL * a, C[i - 1] + TOL * a
            if alto <= basso: continue
            vecchi = [p for p in piv if p[0] <= i - 10]
            candidati = [p for p in vecchi if basso <= p[1] <= alto]
            for pj, pp in candidati:
                gruppo = [q for q in vecchi if abs(q[1] - pp) <= TOL * a]
                if len(gruppo) < 2: continue
                liv = sum(q[1] for q in gruppo) / len(gruppo)
                chiave = (d, round(liv / (TOL * a)))
                if chiave in rotti: continue
                ultimo = max(q[0] for q in gruppo)
                if not ((C[i - 1] <= liv) if d == 1 else (C[i - 1] >= liv)): continue
                intatto = all((C[k] <= liv) if d == 1 else (C[k] >= liv) for k in range(ultimo + 1, i))
                rompe = (C[i] > liv + ROTTURA * a) if d == 1 else (C[i] < liv - ROTTURA * a)
                if intatto and rompe:
                    rotti.add(chiave)
                    stop = liv - TOL * a if d == 1 else liv + TOL * a
                    out.append(("Rottura senza ritest", d, i, stop))
                    attesa.append((d, liv, i))
    return out, (O, H, L, C)

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    print()
    for etichetta, ore in (("CANDELE DA 4 ORE", 4), ("CANDELE GIORNALIERE", 24)):
        dati = {m: carica(m, ore) for m in MONETE}
        dati = {m: b for m, b in dati.items() if b and len(b) > STORIA + 100}
        tutte = {"2R": [], "TREND": []}; anni = 0
        for m, barre in dati.items():
            taglio = int(len(barre) * 0.6)
            anni = max(anni, len(barre) * ore / 24 / 365)
            ops, (O, H, L, C) = segnali(barre)
            for uscita in tutte:
                for nome, d, i, stop in ops:
                    r = simula(i, d, stop, O, H, L, C, uscita, ore)
                    if r is not None: tutte[uscita].append((nome, d, i >= taglio, r))
        print(f"{etichetta}: {len(dati)} monete, {anni:.1f} anni")
        print(f"{'':3}{'Ingresso':24}{'Uscita':8}{'Verso':7}{'N':>6}{'Vinte':>7}{'R prova':>9}{'R verifica':>12}{'Annuo con 1 %':>15}")
        for uscita, ops in tutte.items():
            gruppi = defaultdict(list)
            for nome, d, ver, r in ops: gruppi[(nome, d)].append((ver, r))
            for nome in ("Rottura + ritest", "Rottura senza ritest", "Ingresso a caso"):
                for d in (1, -1):
                    g = gruppi.get((nome, d), [])
                    if not g: continue
                    pr = [r for v, r in g if not v]; ve = [r for v, r in g if v]; tot = [r for _, r in g]
                    mt = media(tot); sd = math.sqrt(media([(x - mt) ** 2 for x in tot])) if tot else 0
                    t = mt / (sd / math.sqrt(len(tot))) if sd else 0
                    if nome == "Ingresso a caso": s = "  "
                    elif len(ve) >= 30 and media(pr) > 0.05 and media(ve) > 0.05 and t >= 3: s = "🟢"
                    elif media(pr) > 0 and media(ve) > 0: s = "🟡"
                    else: s = "🔴"
                    annuo = sum(tot) / anni / len(dati) * 30 / 100
                    print(f"{s} {nome:24}{uscita:8}{'long' if d == 1 else 'short':7}{len(g):>6}"
                          f"{sum(1 for r in tot if r > 0) / len(tot) * 100:>6.0f}%{media(pr):>+9.2f}{media(ve):>+12.2f}"
                          f"{annuo * 100:>+14.1f}%")
        print()
    print("""N: operazioni.   R: risultato medio per operazione in multipli del rischio, costi e funding inclusi.
Annuo con 1 %: rendimento annuo approssimato rischiando l'1 % del capitale a operazione su 30 monete
(somma dei risultati, senza contare le operazioni sovrapposte: e' un ordine di grandezza).
🟢 positivo in prova e in verifica, abbastanza casi e troppo netto per essere fortuna
🟡 positivo in entrambi ma non dimostrato   🔴 negativo in almeno un periodo
Il confronto che conta: "Rottura + ritest" deve battere "Rottura senza ritest" e "Ingresso a caso".""")

if __name__ == "__main__":
    main()
