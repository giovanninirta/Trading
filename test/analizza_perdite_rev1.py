#!/usr/bin/env python3
"""
ANALISI PERDITE - Rev 1
Strategia: Canale 55/20, candele giornaliere, solo long, 30 monete, costo 0,40 % per ordine.
Per ogni operazione registra il CONTESTO AL MOMENTO DELL'INGRESSO (solo dati gia' noti quel giorno)
e confronta operazioni vinte e perse, per capire se le perdite hanno un contesto comune.

Contesti misurati all'ingresso:
  BTC vs media 200 g     BTC sopra o sotto la sua media a 200 giorni (mercato in fase rialzista o no)
  BTC vs media 50 g      lo stesso sulla media a 50 giorni
  Ampiezza               quota delle 30 monete sopra la propria media a 50 giorni
  Ondata                 quante monete hanno rotto al rialzo negli ultimi 5 giorni
  Corsa precedente       rendimento della moneta negli ultimi 55 giorni
  Estensione             distanza del prezzo dalla sua media a 20 giorni
  Volatilita'            oscillazione giornaliera media della moneta negli ultimi 20 giorni
  Forza vs BTC           rendimento 55 g della moneta meno quello di BTC

Metodo: le soglie dei gruppi si calcolano sul primo 60 % dei dati (PROVA). Un filtro e' credibile solo se
il gruppo peggiore scelto in prova resta dannoso anche nell'ultimo 40 % (VERIFICA).

Uso (nella cartella dati, i file mancanti li scarica):  python ../analizza_perdite_rev1.py
Solo libreria standard Python 3.8+.
"""
import csv, json, math, os, sys, time, urllib.request
from collections import defaultdict

MONETE = ("XBT ETH SOL XRP ADA DOGE LTC LINK AVAX DOT BCH ATOM UNI XLM ETC FIL AAVE ALGO TRX NEAR "
          "APE SAND MANA AXS CRV COMP OP ARB INJ XTZ").split()
API = "https://futures.kraken.com/api/charts/v1/trade/{sym}/1h?from={a}&to={b}"
N_IN, N_OUT, COSTO = 55, 20, 0.004
ANNI = 4.5

# ------------------------- DATI -------------------------
def scarica(sym, path):
    fine = int(time.time()); t = fine - int(ANNI * 365 * 86400); righe = {}
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
    print(f"{sym}: {len(righe)} candele scaricate")
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

# ------------------------- AIUTI -------------------------
def media(v): return sum(v) / len(v) if v else 0.0
def ok(serie, t, n): return t >= n and all(x is not None for x in serie[t - n:t + 1])

# ------------------------- OPERAZIONI CON CONTESTO -------------------------
def operazioni(C, giorni):
    T = len(giorni); btc = C["XBT"]
    # monete sopra la propria media 50 e rotture al rialzo, giorno per giorno
    sopra = [0.0] * T; rotture = [0] * T
    for t in range(T):
        n = s = 0
        for m, c in C.items():
            if ok(c, t, 50):
                n += 1; s += c[t] > media(c[t - 50:t])
            if ok(c, t, N_IN) and c[t] > max(c[t - N_IN:t]): rotture[t] += 1
        sopra[t] = s / n if n else 0.0
    ops = []
    for m, c in C.items():
        dentro = None
        for t in range(T):
            if not ok(c, t, N_IN):
                continue
            if dentro is None and c[t] > max(c[t - N_IN:t]):
                rend = [c[k] / c[k - 1] - 1 for k in range(t - 19, t + 1)]
                ctx = {
                    "BTC vs media 200 g": ("sopra" if btc[t] > media(btc[t - 200:t]) else "sotto") if ok(btc, t, 200) else None,
                    "BTC vs media 50 g": ("sopra" if btc[t] > media(btc[t - 50:t]) else "sotto") if ok(btc, t, 50) else None,
                    "Ampiezza": sopra[t],
                    "Ondata": sum(rotture[max(0, t - 4):t + 1]),
                    "Corsa precedente": c[t] / c[t - N_IN] - 1,
                    "Estensione": c[t] / media(c[t - 20:t]) - 1,
                    "Volatilita'": math.sqrt(media([x * x for x in rend])),
                    "Forza vs BTC": (c[t] / c[t - N_IN]) - (btc[t] / btc[t - N_IN]) if ok(btc, t, N_IN) else None,
                }
                dentro = (t, c[t], ctx)
            elif dentro is not None and c[t] < min(c[t - N_OUT:t]):
                t0, p0, ctx = dentro
                r = c[t] / p0 * (1 - COSTO) ** 2 - 1
                ops.append(dict(moneta=m, t0=t0, t1=t, r=r, giorni=t - t0, ctx=ctx))
                dentro = None
    return ops

# ------------------------- REPORT -------------------------
def riga(nome, gruppo):
    n = len(gruppo)
    if n == 0: return f"{nome:22}{'-':>6}"
    vinte = sum(1 for o in gruppo if o["r"] > 0) / n
    return f"{nome:22}{n:>6}{vinte * 100:>7.0f}%{media([o['r'] for o in gruppo]) * 100:>+9.1f}%{sum(o['r'] for o in gruppo) * 100:>+10.0f}%"

def main():
    dati = {}
    for m in MONETE:
        d = carica(m)
        if d: dati[m] = d
        else: print(f"{m}: esclusa")
    if "XBT" not in dati: sys.exit("Mancano i dati di BTC.")
    giorni = sorted(dati["XBT"])
    C = {m: [d.get(t) for t in giorni] for m, d in dati.items()}
    ops = operazioni(C, giorni)
    taglio = int(len(giorni) * 0.6)
    prova = [o for o in ops if o["t0"] < taglio]; verifica = [o for o in ops if o["t0"] >= taglio]
    vinte = [o for o in ops if o["r"] > 0]; perse = [o for o in ops if o["r"] <= 0]
    data = lambda t: time.strftime("%Y-%m-%d", time.gmtime(giorni[t]))

    print(f"\n{len(dati)} monete, {len(giorni)} giorni, {len(ops)} operazioni chiuse "
          f"({len(prova)} in prova fino al {data(taglio)}, {len(verifica)} in verifica)\n")

    # 1) com'e' fatta una perdita
    print("1) COME SONO FATTE VINCITE E PERDITE")
    print(f"{'':22}{'Numero':>8}{'Risultato medio':>17}{'Durata media':>15}{'Durata mediana':>16}")
    for nome, g in (("Vinte", vinte), ("Perse", perse)):
        d = sorted(o["giorni"] for o in g)
        print(f"{nome:22}{len(g):>8}{media([o['r'] for o in g]) * 100:>+16.1f}%{media(d):>13.0f} g{d[len(d) // 2] if d else 0:>14} g")
    rapide = [o for o in perse if o["giorni"] <= 10]
    print(f"Perdite chiuse entro 10 giorni: {len(rapide)} su {len(perse)} "
          f"({len(rapide) / max(len(perse), 1) * 100:.0f} %), costo medio {media([o['r'] for o in rapide]) * 100:+.1f} %")
    tot_v = sum(o["r"] for o in vinte); tot_p = sum(o["r"] for o in perse)
    print(f"Somma vincite {tot_v * 100:+.0f} %, somma perdite {tot_p * 100:+.0f} % (in % della quota di una moneta)")
    top = sorted(vinte, key=lambda o: -o["r"])[:max(1, len(vinte) // 10)]
    print(f"Il 10 % migliore delle vincite ({len(top)} operazioni) vale {sum(o['r'] for o in top) / max(tot_v + tot_p, 1e-9) * 100:.0f} % del guadagno netto totale\n")

    # 2) contesti
    print("2) CONTESTO ALL'INGRESSO")
    print(f"{'Gruppo':22}{'Oper.':>6}{'Vinte':>8}{'Medio':>10}{'Totale':>11}      "
          f"{'Oper.':>6}{'Vinte':>8}{'Medio':>10}{'Totale':>11}")
    print(f"{'':22}{'------------- PROVA -------------':>35}      {'----------- VERIFICA -----------':>35}")
    sintesi = []
    for chiave in ops[0]["ctx"]:
        valori = [o["ctx"][chiave] for o in prova if o["ctx"][chiave] is not None]
        if not valori: continue
        if isinstance(valori[0], str):
            gruppi = sorted(set(valori))
            etichetta = lambda v: v
            assegna = lambda v: v
        else:
            s = sorted(valori); q1, q2 = s[len(s) // 3], s[2 * len(s) // 3]
            if chiave in ("Ampiezza",):
                fmt = lambda x: f"{x * 100:.0f}%"
            elif chiave == "Ondata":
                fmt = lambda x: f"{x:.0f}"
            elif chiave == "Volatilita'":
                fmt = lambda x: f"{x * 100:.1f}%"
            else:
                fmt = lambda x: f"{x * 100:+.0f}%"
            gruppi = [f"bassa (<{fmt(q1)})", f"media", f"alta (>{fmt(q2)})"]
            assegna = lambda v, q1=q1, q2=q2, g=gruppi: g[0] if v < q1 else g[2] if v > q2 else g[1]
        print(f"\n{chiave}")
        risultati = {}
        for g in gruppi:
            a = [o for o in prova if o["ctx"][chiave] is not None and assegna(o["ctx"][chiave]) == g]
            b = [o for o in verifica if o["ctx"][chiave] is not None and assegna(o["ctx"][chiave]) == g]
            risultati[g] = (a, b)
            print(f"  {riga(g, a)}      {riga('', b)[22:]}")
        # filtro candidato: escludere il gruppo peggiore IN PROVA
        peggiore = min(risultati, key=lambda g: media([o["r"] for o in risultati[g][0]]) if risultati[g][0] else 9)
        a, b = risultati[peggiore]
        if len(a) >= 15 and len(b) >= 10:
            sintesi.append((chiave, peggiore, -sum(o["r"] for o in a), -sum(o["r"] for o in b), len(a) + len(b)))

    # 3) filtri
    print("\n3) FILTRI POSSIBILI: cosa succede escludendo il gruppo peggiore (scelto solo sulla prova)")
    print(f"{'':3}{'Contesto':22}{'Gruppo escluso':22}{'Effetto prova':>15}{'Effetto verifica':>18}{'Operaz. tolte':>15}")
    base_p = sum(o["r"] for o in prova); base_v = sum(o["r"] for o in verifica)
    for chiave, g, ep, ev, n in sorted(sintesi, key=lambda x: -x[3]):
        sem = "🟢" if ep > 0.1 * abs(base_p) and ev > 0.1 * abs(base_v) else "🟡" if ep > 0 and ev > 0 else "🔴"
        print(f"{sem} {chiave:22}{g:22}{ep * 100:>+14.0f}%{ev * 100:>+17.0f}%{n:>15}")
    print(f"\nTotale senza filtri: prova {base_p * 100:+.0f} %, verifica {base_v * 100:+.0f} % (somma dei risultati, in % della quota di una moneta)")

    # 4) peggiori operazioni
    print("\n4) LE 10 PERDITE PEGGIORI")
    for o in sorted(ops, key=lambda o: o["r"])[:10]:
        x = o["ctx"]
        print(f"  {data(o['t0'])} {o['moneta']:5}{o['r'] * 100:+7.1f}% in {o['giorni']:3} g · BTC {x['BTC vs media 200 g'] or '-'} media 200 · "
              f"ampiezza {x['Ampiezza'] * 100:.0f}% · corsa {x['Corsa precedente'] * 100:+.0f}% · ondata {x['Ondata']}")

    print("""
Medio: risultato medio per operazione. Totale: somma dei risultati (in % della quota di una moneta).
🟢 escludere quel gruppo avrebbe migliorato in modo netto (oltre il 10 %) sia la prova sia la verifica
🟡 migliora in entrambi ma poco   🔴 in verifica peggiora: il filtro e' solo adattamento al passato
Attenzione: con 8 contesti provati, uno o due "verdi" possono uscire per caso. Un filtro serio deve avere
anche una spiegazione sensata, non solo un numero buono.""")

if __name__ == "__main__":
    main()
