#!/usr/bin/env python3
"""
MISURATORE TREND - Rev 3
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

Rev 2: aggiunta la prova di robustezza del Canale (--robustezza): 21 varianti di ingresso/uscita,
solo long, con i costi dello spot (0,40 % per ordine), per vedere se 55/20 e' un caso isolato.

Rev 3: la prova di robustezza si puo' fare anche su candele da 4 ore o da 1 ora (--candele 4, --candele 1)
e con costi diversi (--costo 0.0007 = perpetui). I numeri del canale diventano candele, non giorni:
su candele da 1 ora "55 / 20" significa 55 ore e 20 ore.

Uso (nella cartella con i file *_1h.csv):
  python misuratore_trend_rev3.py --robustezza
  python misuratore_trend_rev3.py --robustezza --candele 4
  python misuratore_trend_rev3.py --robustezza --candele 1
  python misuratore_trend_rev3.py
  python misuratore_trend_rev3.py --dettagli
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

def canale_n(N, X):
    def f(c, t, pos, short):
        if t < N: return 0
        if c[t] > max(c[t - N:t]): return 1
        if pos == 1 and c[t] < min(c[t - X:t]): return 0
        return pos
    return f

def rendimenti(c, regola, short, costo=COSTO):
    """Rendimenti giornalieri della strategia su una moneta + elenco operazioni chiuse (guadagno)."""
    n = len(c); r = [0.0] * n; pos = 0; ops = []; e_in = 1.0; e = 1.0; dentro = [0] * n
    for t in range(1, n):
        dentro[t] = 1 if pos else 0
        g = pos * (c[t] / c[t - 1] - 1)
        nuova = regola(c, t, pos, short)
        if nuova != pos:
            g -= costo * abs(nuova - pos)
        r[t] = g; e *= 1 + g
        if nuova != pos:
            if pos != 0: ops.append(e / e_in - 1)
            e_in = e; pos = nuova
    return r, ops, dentro

PER_ANNO = 365
def statistiche(r):
    e, picco, calo = 1.0, 1.0, 0.0
    for g in r:
        e *= 1 + g; picco = max(picco, e); calo = min(calo, e / picco - 1)
    annuo = e ** (PER_ANNO / max(len(r), 1)) - 1 if e > 0 else -1.0
    return annuo, calo

def robustezza(C, syms, n, inizio, periodi, SPOT, ore):
    unita = {24: "giorni", 4: "candele 4h", 1: "ore"}[ore]
    def paniere(regola):
        tutte = [rendimenti(C[s], regola, False, SPOT) for s in syms]
        r = [sum(x[0][t] for x in tutte) / len(syms) for t in range(n)]
        quota = sum(sum(x[2][inizio:]) for x in tutte) / (len(syms) * (n - inizio))
        return r, sum(len(x[1]) for x in tutte), quota
    def totale(r):
        e = 1.0
        for g in r: e *= 1 + g
        return e
    fermo, _, _ = paniere(tieni)
    sf = [statistiche(fermo[a:b]) for a, b in periodi]; tf = totale(fermo[inizio:])
    fmt = lambda x: f"{x[0] * 100:+.0f} % / {x[1] * 100:.0f} %"
    num = lambda x: f"x {x:.2f}".replace(".", ",")
    print(f"{len(syms)} monete, {n} candele da {ore} h. Solo long, costo " + f"{SPOT * 100:.2f}".replace(".", ",") + " % per ordine.\n")
    print(f"{'Canale ingresso/uscita':24}{'Primi 60 %':>16}{'Ultimi 40 %':>16}{'Capitale':>10}{'A caso':>9}{'Investito':>11}{'Operaz.':>9}")
    print(f"   {'Tenere le 10 monete':21}{fmt(sf[0]):>16}{fmt(sf[1]):>16}{num(tf):>10}{'':>9}{'100 %':>11}{'-':>9}")
    verdi = gialli = tot = 0
    for N in (20, 30, 40, 55, 70, 100, 150):
        for X in sorted({max(5, N // 4), max(7, round(N / 2.75)), N // 2}):
            r, nops, quota = paniere(canale_n(N, X))
            v = [statistiche(r[a:b]) for a, b in periodi]; t = totale(r[inizio:])
            caso = totale([quota * g for g in fermo[inizio:]])     # stessa quota investita, ma senza scegliere il momento
            if t > caso and t > tf: sem = "🟢"; verdi += 1
            elif t > caso:          sem = "🟡"; gialli += 1
            else:                   sem = "🔴"
            tot += 1
            print(f"{sem} {f'{N} / {X} {unita}':21}{fmt(v[0]):>16}{fmt(v[1]):>16}{num(t):>10}{num(caso):>9}{quota * 100:>9.0f} %{nops:>9}")
    print(f"""
RISULTATO: {verdi} varianti su {tot} verdi, {gialli} gialle, {tot - verdi - gialli} rosse.
Caselle dei periodi: rendimento annuo / calo massimo.   Capitale: quante volte il capitale iniziale, su tutto il periodo.
Investito: per quanta parte del tempo la strategia e' dentro il mercato.
A caso: il capitale di chi tiene sempre investita quella stessa quota, senza scegliere il momento.
        E' il confronto onesto: stare fuori meta' del tempo riduce i cali comunque, anche senza alcuna abilita'.
🟢 batte sia il tenere tutto fermo sia l'investimento "a caso"   🟡 batte solo "a caso" (sceglie bene i momenti)
🔴 non batte nemmeno "a caso": nessuna capacita' di scegliere il momento
Se verde e giallo coprono una zona ampia di varianti vicine, il risultato e' solido. Se e' una riga sola, e' un caso.""")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simboli", default=SIMBOLI)
    ap.add_argument("--dettagli", action="store_true")
    ap.add_argument("--robustezza", action="store_true")
    ap.add_argument("--candele", type=int, default=24, choices=[1, 4, 24], help="ore per candela (solo con --robustezza)")
    ap.add_argument("--costo", type=float, default=0.004, help="costo per ordine nella prova di robustezza")
    args = ap.parse_args()
    global PER_ANNO
    ore = args.candele if args.robustezza else 24
    PER_ANNO = 365 * 24 // ore
    syms = args.simboli.split(",")
    dati = {s: carica(s) for s in syms}
    giorni = sorted(t for t in set.intersection(*[set(d) for d in dati.values()]) if t % (ore * 3600) == 0)
    C = {s: [dati[s][t] for t in giorni] for s in syms}
    n = len(giorni); inizio = 150 if args.robustezza else 100; taglio = inizio + int((n - inizio) * 0.6)
    periodi = [(inizio, taglio), (taglio, n)]
    if args.robustezza:
        robustezza(C, syms, n, inizio, periodi, args.costo, ore); return
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
