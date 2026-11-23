#!/usr/bin/env python3
"""
VERIFICA FORTUNA - Rev 1
Il bot trend (Canale 55/20, 30 monete, solo long, 0,40 % per ordine) guadagna per abilita' o per fortuna?

1) Confronto con 1.000 bot "a caso": ognuno fa, su ogni moneta, lo STESSO numero di operazioni del bot
   vero e della STESSA durata, ma in date scelte a caso. Hanno quindi la stessa esposizione e gli stessi
   costi: l'unica differenza e' il momento in cui entrano. Se il bot vero batte quasi tutti, sceglie
   davvero bene i momenti; se sta a meta' classifica, il risultato e' fortuna del mercato.
2) Quanto il risultato dipende dalle poche operazioni migliori.
3) Risultato anno per anno e moneta per moneta.

Uso (nella cartella dati):  python ../verifica_fortuna_rev1.py
Solo libreria standard Python 3.8+.
"""
import csv, json, os, random, sys, time, urllib.request
from collections import defaultdict

MONETE = ("XBT ETH SOL XRP ADA DOGE LTC LINK AVAX DOT BCH ATOM UNI XLM ETC FIL AAVE ALGO TRX NEAR "
          "APE SAND MANA AXS CRV COMP OP ARB INJ XTZ").split()
API = "https://futures.kraken.com/api/charts/v1/trade/{sym}/1h?from={a}&to={b}"
N_IN, N_OUT, COSTO, SIMULAZIONI = 55, 20, 0.004, 1000
INIZIO = 100

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

def carica(m):
    sym = f"PF_{m}USD"; path = f"{sym}_1h.csv"
    if not os.path.exists(path) and not scarica(sym, path): return None
    out = {}
    with open(path) as f:
        for r in csv.reader(f):
            try:
                ts = int(float(r[0]))
                if ts % 86400 == 0: out[ts] = float(r[4])
            except (ValueError, IndexError): pass
    return out

def ok(s, t, n): return t >= n and all(x is not None for x in s[t - n:t + 1])

def operazioni_vere(c):
    """Operazioni (giorno ingresso, giorno uscita) del canale su una moneta; l'ultima aperta si chiude a fine dati."""
    ops, dentro = [], None
    for t in range(len(c)):
        if not ok(c, t, N_IN): continue
        if dentro is None and c[t] > max(c[t - N_IN:t]): dentro = t
        elif dentro is not None and c[t] < min(c[t - N_OUT:t]): ops.append((dentro, t)); dentro = None
    if dentro is not None: ops.append((dentro, len(c) - 1))
    return ops

def portafoglio(R, ops_per_moneta, T, N, escluse=frozenset()):
    """Rendimenti giornalieri: ogni moneta ha 1/N del capitale; dentro solo durante le sue operazioni."""
    r = [0.0] * T
    for m, ops in ops_per_moneta.items():
        rm = R[m]
        for k, (a, b) in enumerate(ops):
            if (m, k) in escluse: continue
            r[a] -= COSTO / N
            for t in range(a + 1, b + 1): r[t] += rm[t] / N
            r[b] -= COSTO / N
    return r

def capitale(r, a, b):
    e = 1.0
    for g in r[a:b]: e *= 1 + g
    return e

def a_caso(validi, durate, rng):
    """Piazza a caso operazioni di durata data, senza sovrapposizioni, dentro i giorni validi [inizio, fine]."""
    inizio, fine = validi
    libero = (fine - inizio) - sum(durate) - len(durate)
    if libero < 0: return []
    tagli = sorted(rng.randint(0, libero) for _ in durate)
    d = durate[:]; rng.shuffle(d)
    ops, pos, prec = [], inizio, 0
    for taglio, durata in zip(tagli, d):
        pos += taglio - prec; prec = taglio
        ops.append((pos, pos + durata)); pos += durata + 1
    return ops

def main():
    dati = {}
    for m in MONETE:
        d = carica(m)
        if d: dati[m] = d
    if "XBT" not in dati: sys.exit("Mancano i dati di BTC.")
    giorni = sorted(dati["XBT"])
    C = {m: [d.get(t) for t in giorni] for m, d in dati.items()}
    T, N = len(giorni), len(C)
    R = {m: [0.0] + [(c[t] / c[t - 1] - 1) if c[t] and c[t - 1] else 0.0 for t in range(1, T)] for m, c in C.items()}
    taglio = INIZIO + int((T - INIZIO) * 0.6)
    anno = lambda t: time.gmtime(giorni[t]).tm_year

    vere = {m: operazioni_vere(c) for m, c in C.items()}
    r_vero = portafoglio(R, vere, T, N)
    periodi = [("Tutto", 1, T), ("Prova", 1, taglio + 1), ("Verifica", taglio + 1, T)]
    cap_vero = [capitale(r_vero, a, b) for _, a, b in periodi]

    # 1) bot a caso
    validi = {}
    for m, c in C.items():
        idx = [t for t in range(T) if ok(c, t, N_IN)]
        validi[m] = (idx[0], T - 1) if idx else (T - 1, T - 1)
    durate = {m: [b - a for a, b in ops] for m, ops in vere.items()}
    rng = random.Random(42)
    caso = [[] for _ in periodi]
    for _ in range(SIMULAZIONI):
        ops = {m: a_caso(validi[m], durate[m], rng) for m in C}
        r = portafoglio(R, ops, T, N)
        for i, (_, a, b) in enumerate(periodi): caso[i].append(capitale(r, a, b))

    print(f"\n{N} monete, {T} giorni ({T / 365:.1f} anni), {sum(len(o) for o in vere.values())} operazioni del bot vero\n")
    print("1) BOT VERO CONTRO 1.000 BOT A CASO (stesse operazioni, stesse durate, date a caso)")
    print(f"{'':3}{'Periodo':10}{'Bot vero':>10}{'Bot a caso: mediana':>21}{'peggiore 5 %':>14}{'migliore 5 %':>14}{'Battuti':>10}")
    for i, (nome, _, _) in enumerate(periodi):
        s = sorted(caso[i]); quota = sum(1 for x in s if x < cap_vero[i]) / len(s)
        sem = "🟢" if quota >= 0.95 else "🟡" if quota >= 0.80 else "🔴"
        f = lambda x: f"x {x:.2f}".replace(".", ",")
        print(f"{sem} {nome:10}{f(cap_vero[i]):>10}{f(s[len(s) // 2]):>21}{f(s[len(s) // 20]):>14}{f(s[-len(s) // 20]):>14}{quota * 100:>9.0f}%")

    # 2) dipendenza dalle operazioni migliori
    print("\n2) QUANTO DIPENDE DALLE OPERAZIONI MIGLIORI (capitale finale togliendo le migliori)")
    risultati = []
    for m, ops in vere.items():
        for k, (a, b) in enumerate(ops):
            risultati.append(((C[m][b] / C[m][a]) * (1 - COSTO) ** 2 - 1, m, k, a, b))
    risultati.sort(reverse=True)
    for n in (0, 1, 3, 5, 10, 20):
        esc = frozenset((m, k) for _, m, k, _, _ in risultati[:n])
        cap = capitale(portafoglio(R, vere, T, N, esc), 1, T)
        print(f"   {'Senza nessuna esclusione' if n == 0 else f'Senza le {n} migliori':28}x {cap:.2f}".replace(".", ","))
    print("   Le 5 migliori: " + "; ".join(
        f"{m} {time.strftime('%Y-%m', time.gmtime(giorni[a]))} {g * 100:+.0f} %" for g, m, _, a, _ in risultati[:5]))

    # 3) anno per anno e moneta per moneta
    print("\n3) ANNO PER ANNO")
    tenere = [0.0] + [sum(R[m][t] for m in C if C[m][t] and C[m][t - 1]) / N for t in range(1, T)]
    print(f"{'':3}{'Anno':8}{'Bot':>8}{'Tenere':>9}")
    for y in sorted({anno(t) for t in range(1, T)}):
        idx = [t for t in range(1, T) if anno(t) == y]
        b = capitale(r_vero, idx[0], idx[-1] + 1) - 1; h = capitale(tenere, idx[0], idx[-1] + 1) - 1
        print(f"{'▲' if b > 0 else '▼'}  {y:<8}{b * 100:>+7.0f}%{h * 100:>+8.0f}%")
    contributo = defaultdict(float)
    for g, m, _, _, _ in risultati: contributo[m] += g / N
    positive = sum(1 for v in contributo.values() if v > 0)
    ordinate = sorted(contributo.items(), key=lambda kv: -kv[1])
    nome = lambda m: m.replace("XBT", "BTC")
    print(f"\nMONETE: {positive} su {N} in guadagno. Migliori: " +
          ", ".join(f"{nome(m)} {v * 100:+.1f} %" for m, v in ordinate[:5]) +
          ". Peggiori: " + ", ".join(f"{nome(m)} {v * 100:+.1f} %" for m, v in ordinate[-5:]))
    print(f"""
Battuti: quota dei 1.000 bot a caso che il bot vero supera.
🟢 batte almeno il 95 %: sceglie davvero bene i momenti   🟡 tra 80 % e 95 %: indizio, non prova
🔴 sotto l'80 %: il risultato e' compatibile con la fortuna
Contributo delle monete: in % del capitale totale (ogni moneta ha 1/{N} del capitale).""")

if __name__ == "__main__":
    main()
