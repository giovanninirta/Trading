#!/usr/bin/env python3
"""
MISURATORE FUNDING - Rev 1 (adattato all'anno di funding disponibile)
Il funding dei perpetui Kraken dice qualcosa sui movimenti successivi?

Dati: storico pubblico dei tassi di funding (Kraken Futures, nessuna chiave) + candele gia' scaricate.
Funding giornaliero = somma dei tassi del giorno; mostrato in % annuo.
ATTENZIONE: l'API pubblica di Kraken fornisce solo circa l'ultimo anno di funding. Prova e verifica sono
quindi il primo 60 % e l'ultimo 40 % di QUELL'anno: un test breve, da leggere come indizio.

1) SEGNALE: per ogni moneta e giorno, funding medio degli ultimi 3 giorni. Le soglie "molto alto"
   (10 % dei giorni piu' alti) e "molto basso" (10 % piu' bassi) si calcolano sul PRIMO 60 % dei dati.
   Si confronta il rendimento della moneta nei 1, 3, 7 giorni successivi nei tre gruppi.
2) FILTRO: bot giornaliero attuale (Canale 55/20, 30 monete, spot, 0,40 % per ordine) con e senza
   il divieto di comprare quando il funding della moneta e' nel gruppo "molto alto" (o nel 20 % piu' alto).

Uso (nella cartella dati):  python ../misuratore_funding_rev1.py
Solo libreria standard Python 3.8+.
"""
import csv, json, os, sys, time, urllib.request
from collections import defaultdict
from datetime import datetime

MONETE = ("XBT ETH SOL XRP ADA DOGE LTC LINK AVAX DOT BCH ATOM UNI XLM ETC FIL AAVE ALGO TRX NEAR "
          "APE SAND MANA AXS CRV COMP OP ARB INJ XTZ").split()
URL = "https://futures.kraken.com/derivatives/api/v4/historicalfundingrates?symbol={}"
COSTO = 0.004

def funding(m):
    """Ritorna {giorno (timestamp 00:00 UTC): funding del giorno come frazione} oppure None."""
    sym = f"PF_{m}USD"; path = f"FUNDING_{sym}.csv"
    if not os.path.exists(path):
        try:
            with urllib.request.urlopen(URL.format(sym), timeout=60) as r:
                js = json.load(r)
        except Exception as e:
            print(f"{m}: funding non disponibile ({e})"); return None
        righe = []
        for x in js.get("rates", []):
            try:
                ts = int(datetime.fromisoformat(x["timestamp"].replace("Z", "+00:00")).timestamp())
                righe.append((ts, float(x["relativeFundingRate"])))
            except (KeyError, ValueError, TypeError): pass
        if not righe:
            print(f"{m}: funding vuoto"); return None
        with open(path, "w", newline="") as f:
            csv.writer(f).writerows(righe)
        time.sleep(0.3)
    giorni = defaultdict(float)
    with open(path) as f:
        for ts, r in csv.reader(f):
            giorni[int(ts) // 86400 * 86400] += float(r)
    return dict(giorni)

def chiusure(m):
    path = f"PF_{m}USD_1h.csv"
    if not os.path.exists(path): return None
    out = {}
    with open(path) as f:
        for r in csv.reader(f):
            try:
                ts = int(float(r[0]))
                if ts % 86400 == 0: out[ts] = float(r[4])
            except (ValueError, IndexError): pass
    return out

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    dati = {}
    for m in MONETE:
        c, f = chiusure(m), funding(m)
        if c and f: dati[m] = (c, f)
    if "XBT" not in dati: sys.exit("Mancano prezzi o funding di BTC.")
    giorni = sorted(dati["XBT"][0])
    f_btc = dati["XBT"][1]
    con_funding = [t for t in giorni if t in f_btc]
    inizio_f = giorni.index(con_funding[0])
    taglio_t = con_funding[int(len(con_funding) * 0.6)]
    data = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{len(dati)} monete con prezzi e funding. Funding BTC dal {data(min(f_btc))} al {data(max(f_btc))}.")
    v = sorted(f_btc.values())
    print(f"Funding giornaliero BTC in % annuo: mediana {v[len(v) // 2] * 36500:+.1f} %, "
          f"10 % piu' basso sotto {v[len(v) // 10] * 36500:+.1f} %, 10 % piu' alto sopra {v[-len(v) // 10] * 36500:+.1f} %\n")

    # serie allineate
    C = {m: [c.get(t) for t in giorni] for m, (c, _) in dati.items()}
    F3 = {}
    for m, (_, f) in dati.items():
        s = [f.get(t) for t in giorni]
        F3[m] = [media([x for x in s[i - 2:i + 1] if x is not None]) if i >= 2 and any(x is not None for x in s[i - 2:i + 1]) else None
                 for i in range(len(giorni))]
    taglio = giorni.index(taglio_t)
    soglie = {}
    for m in dati:
        p = sorted(x for x in F3[m][inizio_f:taglio] if x is not None)
        if len(p) > 50: soglie[m] = (p[len(p) // 10], p[len(p) * 8 // 10], p[len(p) * 9 // 10])

    # 1) segnale
    print("1) COSA SUCCEDE DOPO UN FUNDING ESTREMO (rendimento medio della moneta, tutte le monete insieme)")
    print(f"{'':3}{'Funding ultimi 3 giorni':26}{'Casi':>7}{'1 giorno':>10}{'3 giorni':>10}{'7 giorni':>10}      {'Casi':>6}{'1 giorno':>10}{'3 giorni':>10}{'7 giorni':>10}")
    print(f"{'':29}{'------------- PROVA -------------':>37}      {'----------- VERIFICA -----------':>36}")
    gruppi = defaultdict(lambda: defaultdict(list))
    for m, (b, _, a) in soglie.items():
        c = C[m]
        for i in range(inizio_f, len(giorni) - 7):
            f = F3[m][i]
            if f is None or c[i] is None: continue
            g = "Molto basso (10 %)" if f <= b else "Molto alto (10 %)" if f >= a else "Normale"
            per = "p" if i < taglio else "v"
            for h in (1, 3, 7):
                if c[i + h] is not None: gruppi[(g, per)][h].append(c[i + h] / c[i] - 1)
    for g in ("Molto basso (10 %)", "Normale", "Molto alto (10 %)"):
        celle = []
        for per in ("p", "v"):
            x = gruppi[(g, per)]
            celle.append(f"{len(x[1]):>7}" + "".join(f"{media(x[h]) * 100:>+9.2f}%" for h in (1, 3, 7)))
        print(f"   {g:26}{celle[0]}      {celle[1]}")

    # 2) filtro sul bot giornaliero
    def bot(soglia_idx):
        T = len(giorni); somma = [0.0] * T
        for m, c in C.items():
            pos = 0
            for t in range(1, T):
                if c[t] is None or c[t - 1] is None: continue
                g = pos * (c[t] / c[t - 1] - 1)
                if t >= 55 and all(x is not None for x in c[t - 55:t + 1]):
                    if not pos and c[t] > max(c[t - 55:t]):
                        blocca = soglia_idx is not None and m in soglie and F3[m][t] is not None and F3[m][t] >= soglie[m][soglia_idx]
                        if not blocca: pos = 1; g -= COSTO
                    elif pos and c[t] < min(c[t - 20:t]): pos = 0; g -= COSTO
                somma[t] += g
        r = [x / len(C) for x in somma]
        v = [1.0]
        for x in r[1:]: v.append(v[-1] * (1 + x))
        return v
    def stat(v, a, b):
        picco, calo = v[a], 0.0
        for x in v[a:b]: picco = max(picco, x); calo = min(calo, x / picco - 1)
        return v[b - 1] / v[a] - 1, calo
    print("\n2) FILTRO SUL BOT GIORNALIERO (spot): non comprare quando il funding della moneta e' troppo alto")
    a0 = max(55, inizio_f)
    mesi = sorted({(time.gmtime(t).tm_year, time.gmtime(t).tm_mon) for t in giorni[a0:]})[::2]
    print(f"   Periodo con funding: dal {data(giorni[a0])}. Rendimento a bimestri sotto.")
    print(f"{'':3}{'':30}{'Prova':>15}{'Verifica':>15}{'Capitale':>10}" + "".join(f"{f'{a % 100:02d}/{m:02d}':>8}" for a, m in mesi))
    base = None
    for nome, idx in (("Bot attuale (nessun filtro)", None), ("Filtro: funding nel 20 % alto", 1), ("Filtro: funding nel 10 % alto", 2)):
        v = bot(idx)
        p, q = stat(v, a0, taglio + 1), stat(v, taglio, len(v))
        cap = v[-1] / v[a0]
        celle = ""
        for k, (a, m) in enumerate(mesi):
            inizio_b = next(i for i in range(a0, len(giorni)) if (time.gmtime(giorni[i]).tm_year, time.gmtime(giorni[i]).tm_mon) == (a, m))
            fine_b = next((i for i in range(a0, len(giorni)) if (time.gmtime(giorni[i]).tm_year, time.gmtime(giorni[i]).tm_mon) == mesi[k + 1]), len(giorni)) if k + 1 < len(mesi) else len(giorni)
            g = v[fine_b - 1] / v[max(inizio_b - 1, a0)] - 1
            celle += f"{g * 100:>+7.0f}%"
        sem = "  " if base is None else ("🟢" if p[0] > base[0][0] and q[0] > base[1][0] else "🔴")
        if base is None: base = (p, q)
        print(f"{sem} {nome:30}{f'{p[0] * 100:+.0f}%/{p[1] * 100:.0f}%':>15}{f'{q[0] * 100:+.0f}%/{q[1] * 100:.0f}%':>15}{f'x{cap:.2f}'.replace('.', ','):>10}{celle}")
    print("""
Prova / Verifica (parte 2): rendimento totale del periodo / calo massimo.   Colonne: rendimento di ogni bimestre.
🟢 il filtro migliora il bot sia in prova sia in verifica   🔴 no
Parte 1: se dopo il funding "molto alto" i rendimenti sono piu' bassi del "normale" in entrambi i periodi,
il funding estremo segnala un mercato fragile.""")

if __name__ == "__main__":
    main()
