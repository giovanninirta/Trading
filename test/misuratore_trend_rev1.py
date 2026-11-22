#!/usr/bin/env python3
"""
MISURATORE TREND - Rev 1
Verifica sui dati storici il "trend following": stare dentro una moneta solo mentre sale
(e, nella versione long/short, venderla allo scoperto mentre scende).
Tutto in dollari, candele giornaliere, 10 monete con lo stesso peso (10 % del capitale ciascuna, niente leva).

Tre regole classiche, fissate prima del test (nessuna ottimizzazione):
  Canale 55/20    entra quando il prezzo supera il massimo degli ultimi 55 giorni,
                  esce quando scende sotto il minimo degli ultimi 20
  Media 100       dentro quando il prezzo e' sopra la media degli ultimi 100 giorni
  Momentum 90     dentro quando il prezzo e' piu' alto di 90 giorni fa
Ognuna in due versioni: "solo long" (fuori = soldi fermi) e "long/short" (fuori = vendita allo scoperto).
Riferimenti: tenere le 10 monete senza fare nulla, tenere solo BTC.
Costi: 0,07 % per ordine (perpetui). Non incluso il funding.

Per ogni periodo due numeri:  rendimento annuo / calo massimo dal picco.
Il trend following non promette di guadagnare piu' di chi tiene: promette cali molto piu' piccoli.

Uso (nella cartella con i file *_1h.csv):
  python misuratore_trend_rev1.py
  python misuratore_trend_rev1.py --dettagli
Solo libreria standard Python 3.8+.
"""
import argparse, csv, os, sys

SIMBOLI = "PF_XBTUSD,PF_ETHUSD,PF_SOLUSD,PF_XRPUSD,PF_ADAUSD,PF_DOGEUSD,PF_LTCUSD,PF_LINKUSD,PF_AVAXUSD,PF_DOTUSD"
BTC = "PF_XBTUSD"
COSTO = 0.0007

def carica(sym):
    path = f"{sym}_1h.csv"
    if not os.path.exists(path):
        sys.exit(f"Manca il file {path}.")
    out = {}
    with open(path) as f:
        for r in csv.reader(f):
            try: out[int(float(r[0]))] = float(r[4])
            except (ValueError, IndexError): pass
    return out

# ---- regole: ritornano la posizione desiderata (+1 long, 0 fuori, -1 short) alla chiusura del giorno t
def canale(c, t, pos, short):
    if t < 55: return 0
    hi, lo = max(c[t - 55:t]), min(c[t - 55:t])
    xhi, xlo = max(c[t - 20:t]), min(c[t - 20:t])
    if c[t] > hi: return 1
    if c[t] < lo: return -1 if short else 0
    if pos == 1 and c[t] < xlo: return 0
    if pos == -1 and c[t] > xhi: return 0
    return pos

def media100(c, t, pos, short):
    if t < 100: return 0
    return 1 if c[t] > sum(c[t - 99:t + 1]) / 100 else (-1 if short else 0)

def momentum90(c, t, pos, short):
    if t < 90: return 0
    return 1 if c[t] > c[t - 90] else (-1 if short else 0)

def tieni(c, t, pos, short):
    return 1

def rendimenti(c, regola, short):
    """Rendimenti giornalieri della strategia su una moneta + elenco operazioni chiuse (guadagno)."""
    n = len(c); r = [0.0] * n; pos = 0; ops = []; e_in = 1.0; e = 1.0
    for t in range(1, n):
        g = pos * (c[t] / c[t - 1] - 1)
        nuova = regola(c, t, pos, short)
        if nuova != pos:
            g -= COSTO * abs(nuova - pos)
        r[t] = g; e *= 1 + g
        if nuova != pos:
            if pos != 0: ops.append(e / e_in - 1)
            e_in = e; pos = nuova
    return r, ops

def statistiche(r):
    e, picco, calo = 1.0, 1.0, 0.0
    for g in r:
        e *= 1 + g; picco = max(picco, e); calo = min(calo, e / picco - 1)
    annuo = e ** (365 / max(len(r), 1)) - 1 if e > 0 else -1.0
    return annuo, calo

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simboli", default=SIMBOLI)
    ap.add_argument("--dettagli", action="store_true")
    args = ap.parse_args()
    syms = args.simboli.split(",")
    dati = {s: carica(s) for s in syms}
    giorni = sorted(t for t in set.intersection(*[set(d) for d in dati.values()]) if t % 86400 == 0)
    C = {s: [dati[s][t] for t in giorni] for s in syms}
    n = len(giorni); inizio = 100; taglio = inizio + int((n - inizio) * 0.6)
    periodi = [(inizio, taglio), (taglio, n)]
    print(f"{len(syms)} monete, {n} giorni ({n / 365:.1f} anni). I primi 100 giorni servono solo a calcolare le medie.\n")

    def paniere(regola, short, monete):
        tutte = {s: rendimenti(C[s], regola, short) for s in monete}
        r = [sum(tutte[s][0][t] for s in monete) / len(monete) for t in range(n)]
        ops = [o for s in monete for o in tutte[s][1]]
        return r, ops, tutte

    righe = [("Tenere le 10 monete", tieni, False, syms, None),
             ("Tenere solo BTC", tieni, False, [BTC], None)]
    for nome, reg in (("Canale 55/20", canale), ("Media 100", media100), ("Momentum 90", momentum90)):
        righe.append((f"{nome} - solo long", reg, False, syms, 0))
        righe.append((f"{nome} - long/short", reg, True, syms, 0))
    for nome, reg in (("Canale 55/20", canale), ("Media 100", media100), ("Momentum 90", momentum90)):
        righe.append((f"Solo BTC: {nome} - solo long", reg, False, [BTC], 1))

    ris = {}
    for nome, reg, short, monete, rif in righe:
        r, ops, tutte = paniere(reg, short, monete)
        ris[nome] = ([statistiche(r[a:b]) for a, b in periodi], ops, tutte)

    def semaforo(nome, rif):
        if rif is None: return "  "
        base = ris[righe[rif][0]][0]; v = ris[nome][0]
        rapporto = lambda x: x[0] / abs(x[1]) if x[1] < 0 else 0
        if all(x[0] > 0 for x in v) and all(abs(x[1]) < abs(b[1]) for x, b in zip(v, base)): return "🟢"
        if all(rapporto(x) > rapporto(b) for x, b in zip(v, base)): return "🟡"
        return "🔴"

    fmt = lambda x: f"{x[0] * 100:+.0f} % / {x[1] * 100:.0f} %"
    print(f"{'Rendimento annuo / calo massimo':40}{'Primi 60 %':>18}{'Ultimi 40 %':>18}")
    for nome, reg, short, monete, rif in righe:
        v = ris[nome][0]
        print(f"{semaforo(nome, rif)} {nome:37}{fmt(v[0]):>18}{fmt(v[1]):>18}")

    if args.dettagli:
        print(f"\n{'Operazioni (tutto il periodo)':40}{'Numero':>10}{'In guadagno':>14}{'Media vinte':>14}{'Media perse':>14}")
        for nome, reg, short, monete, rif in righe:
            ops = ris[nome][1]
            if rif is None or not ops: continue
            v = [o for o in ops if o > 0]; p = [o for o in ops if o <= 0]
            mv = sum(v) / len(v) * 100 if v else 0; mp = sum(p) / len(p) * 100 if p else 0
            print(f"   {nome:37}{len(ops):>10}{len(v) / len(ops) * 100:>13.0f}%{mv:>+13.1f}%{mp:>+13.1f}%")
        print(f"\n{'Canale 55/20 solo long, moneta per moneta':40}{'Primi 60 %':>18}{'Ultimi 40 %':>18}   (tra parentesi: tenere la moneta)")
        tutte = ris["Canale 55/20 - solo long"][2]; ferme = ris["Tenere le 10 monete"][2]
        for s in syms:
            a = [statistiche(tutte[s][0][x:y]) for x, y in periodi]; b = [statistiche(ferme[s][0][x:y]) for x, y in periodi]
            nome = s.replace("PF_", "").replace("USD", "")
            print(f"   {nome:37}{f'{a[0][0] * 100:+.0f} % ({b[0][0] * 100:+.0f} %)':>18}{f'{a[1][0] * 100:+.0f} % ({b[1][0] * 100:+.0f} %)':>18}")

    print("""
Ogni casella: rendimento annuo / calo massimo dal picco (quanto avresti visto scendere il conto nel momento peggiore).
🟢 guadagna in entrambi i periodi e con cali piu' piccoli di chi tiene fermo
🟡 non sempre in guadagno, ma con un rapporto guadagno/calo migliore di chi tiene fermo in entrambi i periodi
🔴 nessuno dei due
Il confronto e' con "Tenere le 10 monete" (per le righe Solo BTC: con "Tenere solo BTC").""")

if __name__ == "__main__":
    main()
