#!/usr/bin/env python3
"""
MISURATORE TREND - Rev 4
Due modi per migliorare il Canale 55/20 (candele giornaliere, solo long, costi spot):
  1) PIU' MONETE: alle 10 di partenza si aggiungono circa 20 monete quotate sui perpetui Kraken.
     Le monete nate dopo entrano nel test solo da quando esistono i loro dati.
  2) CAPITALE CONDIVISO: invece di una quota fissa per moneta (che resta ferma quando la moneta
     e' fuori), il capitale e' un'unica cassa divisa in K posizioni. Se arrivano piu' segnali
     dei posti liberi, entrano le monete salite di piu' negli ultimi 55 giorni.
Simulazione a livello di portafoglio, giorno per giorno, con cassa reale (niente leva).

Uso (nella cartella con i file *_1h.csv; le monete nuove le scarica da solo la prima volta):
  python misuratore_trend_rev4.py
  python misuratore_trend_rev4.py --canale 30,11      # canale piu' corto: piu' operazioni
  python misuratore_trend_rev4.py --dettagli          # da quando e' disponibile ogni moneta
Solo libreria standard Python 3.8+. Nessuna chiave API.
"""
import argparse, csv, json, os, sys, time, urllib.request

BASE = "PF_XBTUSD,PF_ETHUSD,PF_SOLUSD,PF_XRPUSD,PF_ADAUSD,PF_DOGEUSD,PF_LTCUSD,PF_LINKUSD,PF_AVAXUSD,PF_DOTUSD"
EXTRA = ("PF_BCHUSD,PF_ATOMUSD,PF_UNIUSD,PF_XLMUSD,PF_ETCUSD,PF_FILUSD,PF_AAVEUSD,PF_ALGOUSD,PF_TRXUSD,"
         "PF_NEARUSD,PF_APEUSD,PF_SANDUSD,PF_MANAUSD,PF_AXSUSD,PF_CRVUSD,PF_COMPUSD,PF_OPUSD,PF_ARBUSD,PF_INJUSD,PF_XTZUSD")
API = "https://futures.kraken.com/api/charts/v1/trade/{sym}/1h?from={a}&to={b}"
COSTO = 0.004
INIZIO = 100            # i primi 100 giorni servono solo a preparare i canali

# ------------------------- DATI -------------------------
def scarica(sym, anni, path):
    fine = int(time.time()); t = fine - int(anni * 365 * 86400); righe = {}
    while t < fine:
        url = API.format(sym=sym, a=t, b=min(t + 1500 * 3600, fine))
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                js = json.load(r)
        except Exception as e:
            print(f"\n{sym}: non scaricabile ({e})"); return False
        for c in js.get("candles", []):
            ts = int(c["time"]) // 1000
            righe[ts] = (ts, c["open"], c["high"], c["low"], c["close"])
        t += 1500 * 3600
        print(f"\r{sym}: {len(righe)} candele scaricate", end="", flush=True)
        time.sleep(0.3)
    print()
    if len(righe) < 24 * 200:
        print(f"{sym}: storia troppo corta, esclusa"); return False
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows([righe[k] for k in sorted(righe)][:-1])
    return True

def carica(sym, anni):
    path = f"{sym}_1h.csv"
    if not os.path.exists(path) and not scarica(sym, anni, path):
        return None
    out = {}
    with open(path) as f:
        for r in csv.reader(f):
            try:
                ts = int(float(r[0]))
                if ts % 86400 == 0: out[ts] = float(r[4])     # chiusura giornaliera
            except (ValueError, IndexError):
                pass
    return out or None

# ------------------------- SIMULAZIONE -------------------------
def finestra(serie, t, n):
    if t < n: return None
    w = serie[t - n:t]
    return None if any(x is None for x in w) else w

def simula(C, monete, K, n_in, n_out):
    """Portafoglio unico con cassa. Ritorna valore giornaliero, quota investita giornaliera, risultati delle operazioni."""
    T = len(next(iter(C.values())))
    cassa = 1.0; qty = {}; costo_in = {}; ultimo = {m: None for m in monete}
    valore, quota, ops = [], [], []
    for t in range(T):
        for m in monete:
            if C[m][t] is not None: ultimo[m] = C[m][t]
        # uscite
        for m in list(qty):
            c = C[m][t]; w = finestra(C[m], t, n_out)
            if c is not None and w and c < min(w):
                incasso = qty[m] * c * (1 - COSTO); cassa += incasso
                ops.append(incasso / costo_in[m] - 1); del qty[m]
        # ingressi, dal piu' forte
        tot = cassa + sum(q * ultimo[m] for m, q in qty.items())
        cand = []
        for m in monete:
            if m in qty: continue
            c = C[m][t]; w = finestra(C[m], t, n_in)
            if c is not None and w and c > max(w):
                cand.append((c / w[0], m))
        for _, m in sorted(cand, reverse=True):
            if len(qty) >= K: break
            importo = min(tot / K, cassa)
            if importo < 0.25 * tot / K: break
            qty[m] = importo * (1 - COSTO) / C[m][t]; costo_in[m] = importo; cassa -= importo
        investito = sum(q * ultimo[m] for m, q in qty.items())
        valore.append(cassa + investito); quota.append(investito / (cassa + investito))
    return valore, quota, ops

def tenere(C, monete):
    """Tenere tutte le monete disponibili in parti uguali (ribilanciato ogni giorno, senza costi)."""
    T = len(next(iter(C.values()))); r = [0.0] * T
    for t in range(1, T):
        g = [C[m][t] / C[m][t - 1] - 1 for m in monete if C[m][t] is not None and C[m][t - 1] is not None]
        r[t] = sum(g) / len(g) if g else 0.0
    return r

def da_rendimenti(r):
    v = [1.0]
    for g in r[1:]: v.append(v[-1] * (1 + g))
    return v

def stat(v):
    picco, calo = v[0], 0.0
    for x in v:
        picco = max(picco, x); calo = min(calo, x / picco - 1)
    tot = v[-1] / v[0]
    annuo = tot ** (365 / max(len(v) - 1, 1)) - 1 if tot > 0 else -1.0
    return annuo, calo

# ------------------------- MAIN -------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", default=EXTRA)
    ap.add_argument("--canale", default="55,20")
    ap.add_argument("--anni", type=float, default=4.5)
    ap.add_argument("--dettagli", action="store_true")
    args = ap.parse_args()
    n_in, n_out = (int(x) for x in args.canale.split(","))

    base = BASE.split(",")
    dati = {}
    for s in base:
        d = carica(s, args.anni)
        if d is None: sys.exit(f"Manca {s}: serve per il confronto di base.")
        dati[s] = d
    nuove, escluse = [], []
    for s in args.extra.split(","):
        d = carica(s, args.anni)
        if d is None: escluse.append(s)
        else: dati[s] = d; nuove.append(s)
    tutte = base + nuove

    giorni = sorted(set(dati["PF_XBTUSD"]))
    C = {s: [dati[s].get(t) for t in giorni] for s in tutte}
    T = len(giorni); taglio = INIZIO + int((T - INIZIO) * 0.6)
    nome = lambda s: s.replace("PF_", "").replace("USD", "").replace("XBT", "BTC")
    print(f"\n{len(base)} monete di base + {len(nuove)} aggiunte" +
          (f" ({len(escluse)} non disponibili: {', '.join(nome(s) for s in escluse)})" if escluse else "") +
          f". {T} giorni. Canale {n_in}/{n_out}, solo long, costo 0,40 % per ordine.\n")

    def periodi(v):
        return stat(v[INIZIO:taglio + 1]), stat(v[taglio:])

    fmt = lambda x: f"{x[0] * 100:+.0f} % / {x[1] * 100:.0f} %"
    num = lambda x: f"x {x:.2f}".replace(".", ",")
    print(f"{'':3}{'':46}{'Primi 60 %':>16}{'Ultimi 40 %':>16}{'Capitale':>10}{'A caso':>9}{'Investito':>11}{'Operaz.':>9}{'Vinte':>7}")
    verdi = 0; righe_tot = 0
    for gruppo, monete, kk in (("Le 10 monete", base, [len(base), 5, 4, 3]),
                               (f"Tutte le {len(tutte)} monete", tutte, [len(tutte), 10, 5, 4])):
        r_h = tenere(C, monete); v_h = da_rendimenti(r_h)
        cap_h = v_h[-1] / v_h[INIZIO]
        ph = periodi(v_h)
        print(f"   {'Tenere ' + gruppo.lower():46}{fmt(ph[0]):>16}{fmt(ph[1]):>16}{num(cap_h):>10}{'':>9}{'100 %':>11}{'-':>9}{'':>7}")
        for K in kk:
            v, q, ops = simula(C, monete, K, n_in, n_out)
            cap = v[-1] / v[INIZIO]
            qm = sum(q[INIZIO:]) / len(q[INIZIO:])
            caso = 1.0
            for g in r_h[INIZIO + 1:]: caso *= 1 + qm * g
            p = periodi(v)
            vinte = sum(1 for o in ops if o > 0) / len(ops) if ops else 0
            if cap > caso and cap > cap_h: s = "🟢"; verdi += 1
            elif cap > caso:               s = "🟡"
            else:                          s = "🔴"
            righe_tot += 1
            etich = f"quota fissa {100 / K:.1f} %".replace(".", ",") if K == len(monete) else f"max {K} posizioni da {100 / K:.0f} %"
            print(f"{s} {gruppo + ' - ' + etich:46}{fmt(p[0]):>16}{fmt(p[1]):>16}{num(cap):>10}{num(caso):>9}{qm * 100:>9.0f} %{len(ops):>9}{vinte * 100:>6.0f}%")
        print()

    if args.dettagli:
        print("Monete aggiunte e data dei primi dati disponibili:")
        for s in nuove:
            primo = next(giorni[i] for i, x in enumerate(C[s]) if x is not None)
            print(f"   {nome(s):8}{time.strftime('%Y-%m-%d', time.gmtime(primo))}")
        print()

    print(f"""RISULTATO: {verdi} configurazioni su {righe_tot} battono sia il tenere fermo sia l'investimento "a caso".
Caselle dei periodi: rendimento annuo / calo massimo.   Capitale: quante volte il capitale iniziale, su tutto il periodo.
Investito: quota media del capitale dentro il mercato.   Operaz.: operazioni chiuse in {f"{(T - INIZIO) / 365:.1f}".replace(".", ",")} anni.
A caso: chi tiene sempre investita quella stessa quota, senza scegliere il momento.
🟢 batte tenere fermo e "a caso"   🟡 batte solo "a caso"   🔴 nemmeno "a caso"
"max K posizioni": cassa unica; ogni nuova posizione vale 1/K del conto. Meno posizioni = piu' concentrazione = cali piu' grandi.
Attenzione: le monete aggiunte sono quelle quotate OGGI. Quelle fallite e tolte dal listino non ci sono,
quindi i risultati con piu' monete sono un po' ottimisti.""")

if __name__ == "__main__":
    main()
