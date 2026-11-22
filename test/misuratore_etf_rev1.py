#!/usr/bin/env python3
"""
MISURATORE ETF - Rev 1
La stessa regola del bot crypto (Canale ingresso/uscita, candele giornaliere, solo long) applicata
a ETF di mercati diversi: azioni di varie aree, obbligazioni, oro, materie prime, immobiliare.
Una quota fissa per ETF; un ETF nato dopo entra nel test da quando esistono i suoi dati.
Prezzi rettificati per dividendi (rendimento totale). La liquidita' ferma NON rende nulla (ipotesi prudente).
Costo: 0,10 % per ordine (ATTENZIONE: molti conti bancari hanno invece una commissione minima fissa).

Si usano ETF quotati negli USA perche' hanno la storia piu' lunga; un investitore italiano dovrebbe
usare gli equivalenti UCITS quotati in Europa, che seguono gli stessi indici.

Uso (nella cartella dati; scarica da solo i prezzi):  python ../misuratore_etf_rev1.py
Solo libreria standard Python 3.8+.
"""
import calendar, csv, io, json, os, sys, time, urllib.request

ETF = {
    "SPY": "Azioni USA", "QQQ": "Azioni USA tecnologia", "IWM": "Azioni USA piccole", "VGK": "Azioni Europa",
    "EWJ": "Azioni Giappone", "EEM": "Azioni emergenti", "TLT": "Titoli di Stato USA lunghi",
    "IEF": "Titoli di Stato USA medi", "LQD": "Obbligazioni societarie", "TIP": "Obbligazioni indicizzate",
    "GLD": "Oro", "SLV": "Argento", "DBC": "Materie prime", "USO": "Petrolio", "VNQ": "Immobiliare USA",
    "UUP": "Dollaro USA",
}
COSTO = 0.001
VARIANTI = [("Canale 20/10", 20, 10), ("Canale 55/20", 55, 20), ("Canale 100/50", 100, 50),
            ("Canale 150/75", 150, 75), ("Canale 200/100", 200, 100), ("Media 200 giorni", "media", 200)]
INIZIO = 250
UA = {"User-Agent": "Mozilla/5.0"}

# ------------------------- DATI -------------------------
def da_yahoo(t):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1=0&period2={int(time.time())}&interval=1d&events=div%2Csplit"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        js = json.load(r)
    res = js["chart"]["result"][0]
    agg = res["indicators"]["adjclose"][0]["adjclose"]
    return {ts // 86400: p for ts, p in zip(res["timestamp"], agg) if p}

def da_stooq(t):
    url = f"https://stooq.com/q/d/l/?s={t.lower()}.us&i=d"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        testo = r.read().decode()
    out = {}
    for riga in csv.DictReader(io.StringIO(testo)):
        try:
            g = calendar.timegm(time.strptime(riga["Date"], "%Y-%m-%d")) // 86400
            out[g] = float(riga["Close"])
        except (KeyError, ValueError): pass
    return out

def carica(t):
    path = f"{t}_etf.csv"
    if not os.path.exists(path):
        dati, fonte = {}, None
        for nome, f in (("Yahoo", da_yahoo), ("Stooq", da_stooq)):
            try:
                dati = f(t)
                if len(dati) > 500: fonte = nome; break
            except Exception as e:
                print(f"{t}: {nome} non disponibile ({e})")
        if not fonte: return None
        with open(path, "w", newline="") as fh:
            csv.writer(fh).writerows(sorted(dati.items()))
        print(f"{t}: {len(dati)} giorni da {fonte}")
    with open(path) as fh:
        return {int(r[0]): float(r[1]) for r in csv.reader(fh)}

# ------------------------- SIMULAZIONE -------------------------
def ok(s, t, n): return t >= n and all(x is not None for x in s[t - n:t + 1])

def simula(C, n_in, n_out):
    T = len(next(iter(C.values()))); N = len(C)
    r = [0.0] * T; dentro = [0.0] * T; ops = 0
    for c in C.values():
        pos = 0
        for t in range(1, T):
            if c[t] is None or c[t - 1] is None: continue
            g = pos * (c[t] / c[t - 1] - 1)
            nuova = pos
            if n_in == "media":
                if ok(c, t, n_out): nuova = 1 if c[t] > sum(c[t - n_out:t]) / n_out else 0
            elif ok(c, t, n_in):
                if pos == 0 and c[t] > max(c[t - n_in:t]): nuova = 1
                elif pos == 1 and c[t] < min(c[t - n_out:t]): nuova = 0
            if nuova != pos:
                g -= COSTO; ops += nuova == 0
            pos = nuova
            r[t] += g / N; dentro[t] += pos / N
    return r, dentro, ops

def valori(r):
    v = [1.0]
    for g in r[1:]: v.append(v[-1] * (1 + g))
    return v

def stat(v):
    picco, calo = v[0], 0.0
    for x in v: picco = max(picco, x); calo = min(calo, x / picco - 1)
    return (v[-1] / v[0]) ** (365.25 / (max(len(v) - 1, 1) * GIORNI_PER_RIGA)) - 1, calo

GIORNI_PER_RIGA = 1.0

def main():
    global GIORNI_PER_RIGA
    dati = {}
    for t in ETF:
        d = carica(t)
        if d: dati[t] = d
        else: print(f"{t}: escluso")
    if "SPY" not in dati: sys.exit("Mancano i dati di SPY.")
    giorni = sorted(dati["SPY"])
    C = {t: [d.get(g) for g in giorni] for t, d in dati.items()}
    T = len(giorni); GIORNI_PER_RIGA = (giorni[-1] - giorni[0]) / (T - 1)
    taglio = INIZIO + int((T - INIZIO) * 0.6)
    data = lambda i: time.strftime("%Y-%m-%d", time.gmtime(giorni[i] * 86400))
    anni = (giorni[-1] - giorni[INIZIO]) / 365.25
    print(f"\n{len(C)} ETF, dal {data(INIZIO)} al {data(T - 1)} ({anni:.0f} anni). Prova fino al {data(taglio)}, poi verifica.\n")

    tenere = [0.0] * T
    for t in range(1, T):
        g = [c[t] / c[t - 1] - 1 for c in C.values() if c[t] is not None and c[t - 1] is not None]
        tenere[t] = sum(g) / len(C)      # ETF non ancora nati = liquidita'
    spy = [0.0] + [C["SPY"][t] / C["SPY"][t - 1] - 1 for t in range(1, T)]

    fmt = lambda x: f"{x[0] * 100:+.1f} % / {x[1] * 100:.0f} %".replace(".", ",", 1)
    num = lambda x: f"x {x:.2f}".replace(".", ",")
    print(f"{'':3}{'':28}{'Prova':>17}{'Verifica':>17}{'Capitale':>10}{'A caso':>9}{'Investito':>11}{'Oper./anno':>12}")
    righe = {}
    def riga(nome, r, quota=None, ops=None, rif=None):
        v = valori(r[INIZIO:]); vp = valori(r[INIZIO:taglio + 1]); vv = valori(r[taglio:])
        p, q = stat(vp), stat(vv); cap = v[-1]
        sem, caso_txt = "  ", ""
        if quota is not None:
            qm = sum(quota[INIZIO:]) / len(quota[INIZIO:])
            caso = valori([qm * g for g in tenere[INIZIO:]])[-1]
            caso_txt = num(caso)
            if cap > caso and q[1] > rif[1] and p[1] > rif[0]: sem = "🟢"
            elif cap > caso: sem = "🟡"
            else: sem = "🔴"
            inv = f"{qm * 100:.0f} %"
        else:
            inv = "100 %"
        print(f"{sem} {nome:28}{fmt(p):>17}{fmt(q):>17}{num(cap):>10}{caso_txt:>9}{inv:>11}{(f'{ops / anni:.0f}' if ops is not None else '-'):>12}")
        righe[nome] = r
        return p[1], q[1]
    cali = riga("Tenere tutti gli ETF", tenere)
    riga("Tenere solo azioni USA (SPY)", spy)
    for nome, a, b in VARIANTI:
        r, quota, ops = simula(C, a, b)
        riga(nome, r, quota, ops, rif=cali)

    # anni di crisi
    print(f"\nANNI DIFFICILI (rendimento dell'anno)")
    anni_crisi = [2008, 2011, 2015, 2018, 2020, 2022]
    print(f"{'':31}" + "".join(f"{a:>8}" for a in anni_crisi))
    for nome in ["Tenere tutti gli ETF", "Tenere solo azioni USA (SPY)", "Canale 55/20", "Canale 100/50", "Media 200 giorni"]:
        r = righe[nome]; celle = []
        for a in anni_crisi:
            idx = [t for t in range(1, T) if time.gmtime(giorni[t] * 86400).tm_year == a]
            if not idx or idx[0] < INIZIO: celle.append("-"); continue
            e = 1.0
            for t in idx: e *= 1 + r[t]
            celle.append(f"{(e - 1) * 100:+.0f}%")
        print(f"   {nome:28}" + "".join(f"{c:>8}" for c in celle))

    print("""
Prova / Verifica: rendimento annuo / calo massimo dal picco.   Capitale: quante volte il capitale iniziale.
A caso: chi tiene sempre investita la stessa quota media, senza scegliere il momento.
🟢 batte "a caso" e ha cali piu' piccoli di "Tenere tutti gli ETF" in entrambi i periodi
🟡 batte solo "a caso"   🔴 non batte nemmeno "a caso"
La liquidita' ferma qui non rende: nella realta' renderebbe il tasso dei titoli a breve, a favore della strategia.""")

if __name__ == "__main__":
    main()
