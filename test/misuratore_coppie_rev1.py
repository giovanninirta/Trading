#!/usr/bin/env python3
"""
MISURATORE DI COPPIE - Rev 1
Verifica sui dati storici dei perpetui Kraken una strategia "neutrale":
quando due monete che di solito si muovono insieme si allontanano troppo,
si vende quella salita di piu' e si compra quella rimasta indietro,
e si chiude quando la distanza torna normale.
Il guadagno non dipende dalla direzione del mercato, ma dal ritorno della distanza.

Regole (fissate prima del test, nessuna ottimizzazione):
  distanza   logaritmo del rapporto tra i due prezzi, misurato in "z" (scarti dalla media
             delle ultime 336 ore = 14 giorni)
  ingresso   |z| >= 2   -> short sulla moneta "cara", long sulla "economica", stesso importo
  uscita     z torna a 0 (la distanza si e' richiusa)
  stop       |z| >= 4 (la distanza continua ad allargarsi) oppure dopo 14 giorni
  costi      commissione taker + slittamento su 4 ordini (2 monete, entrata e uscita)
Metodo: le coppie si scelgono SOLO sul primo 60 % dei dati; il verdetto si legge
sull'ultimo 40 %, che il programma non ha usato per scegliere.

Uso (nella stessa cartella dei file *_1h.csv gia' scaricati dal misuratore di figure):
  python misuratore_coppie_rev1.py
  python misuratore_coppie_rev1.py --dettagli        # tabella coppia per coppia
  python misuratore_coppie_rev1.py --finestra 168 --entra 2.5
Solo libreria standard Python 3.8+. Nessuna chiave API.
"""
import argparse, csv, glob, json, math, os, sys, time, urllib.request
from collections import defaultdict
from itertools import combinations

SIMBOLI = "PF_XBTUSD,PF_ETHUSD,PF_SOLUSD,PF_XRPUSD,PF_ADAUSD,PF_DOGEUSD,PF_LTCUSD,PF_LINKUSD,PF_AVAXUSD,PF_DOTUSD"
API = "https://futures.kraken.com/api/charts/v1/trade/{sym}/1h?from={a}&to={b}"
FEE, SLIP = 0.0005, 0.0002          # per ordine: taker 0,05 % + slittamento 0,02 %
COSTO = 4 * (FEE + SLIP)            # 4 ordini per operazione, in frazione dell'importo di una gamba

def carica(sym, anni):
    path = f"{sym}_1h.csv"
    if not os.path.exists(path):
        fine = int(time.time()); t = fine - int(anni * 365 * 86400); righe = {}
        while t < fine:
            url = API.format(sym=sym, a=t, b=min(t + 1500 * 3600, fine))
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    js = json.load(r)
            except Exception as e:
                sys.exit(f"Errore nello scaricare {sym}: {e}")
            for c in js.get("candles", []):
                ts = int(c["time"]) // 1000
                righe[ts] = (ts, c["open"], c["high"], c["low"], c["close"])
            t += 1500 * 3600
            print(f"\r{sym}: {len(righe)} candele scaricate", end="", flush=True)
            time.sleep(0.3)
        print()
        with open(path, "w", newline="") as f:
            csv.writer(f).writerows([righe[k] for k in sorted(righe)][:-1])
    out = {}
    with open(path) as f:
        for r in csv.reader(f):
            try: out[int(float(r[0]))] = float(r[4])
            except (ValueError, IndexError): pass
    return out

def operazioni_coppia(ts, pa, pb, W, z_in, z_out, z_stop, max_ore):
    """Ritorna lista di (t_ingresso, t_uscita, guadagno netto in frazione dell'importo di una gamba, motivo)."""
    s = [math.log(a / b) for a, b in zip(pa, pb)]
    n = len(s); c1 = [0.0]; c2 = [0.0]
    for v in s:
        c1.append(c1[-1] + v); c2.append(c2[-1] + v * v)
    out = []; pos = 0; s_in = 0.0; i_in = 0; blocco = False
    for i in range(W, n):
        m = (c1[i + 1] - c1[i + 1 - W]) / W
        var = (c2[i + 1] - c2[i + 1 - W]) / W - m * m
        if var <= 1e-12:
            continue
        z = (s[i] - m) / math.sqrt(var)
        if pos == 0:
            if blocco:                       # dopo uno stop si aspetta che la distanza si calmi
                if abs(z) < 1: blocco = False
                continue
            if abs(z) >= z_in and abs(z) < z_stop:
                pos = -1 if z > 0 else 1     # z alto: short sul rapporto; z basso: long
                s_in, i_in = s[i], i
        else:
            motivo = None
            if (pos == -1 and z <= z_out) or (pos == 1 and z >= -z_out): motivo = "ok"
            elif abs(z) >= z_stop:                                         motivo = "stop"
            elif i - i_in >= max_ore:                                      motivo = "tempo"
            if motivo:
                out.append((ts[i_in], ts[i], pos * (s[i] - s_in) - COSTO, motivo))
                blocco = motivo != "ok"
                pos = 0
    return out

def portafoglio(ops, max_aperte, max_per_moneta):
    """ops: (t_in, t_out, pnl, motivo, a, b). Accetta in ordine di tempo rispettando i limiti."""
    ops = sorted(ops); aperte = []; presi = []
    for o in ops:
        aperte = [x for x in aperte if x[1] > o[0]]
        if len(aperte) >= max_aperte: continue
        conta = defaultdict(int)
        for x in aperte: conta[x[4]] += 1; conta[x[5]] += 1
        if conta[o[4]] >= max_per_moneta or conta[o[5]] >= max_per_moneta: continue
        aperte.append(o); presi.append(o)
    return presi

def riassunto(ops, quota, anni):
    if not ops:
        return None
    p = [o[2] for o in ops]; n = len(p); m = sum(p) / n
    sd = (sum((x - m) ** 2 for x in p) / n) ** 0.5
    t = m / (sd / n ** 0.5) if sd > 0 else 0
    mesi = defaultdict(float)
    for o in ops:
        g = time.gmtime(o[1]); mesi[(g.tm_year, g.tm_mon)] += o[2] * quota
    vm = list(mesi.values())
    return dict(n=n, vinte=sum(1 for x in p if x > 0) / n, medio=m, peggiore=min(p), t=t,
                mesi_pos=sum(1 for x in vm if x > 0) / len(vm), mese_peggiore=min(vm),
                annuo=sum(p) * quota / anni, stop=sum(1 for o in ops if o[3] != "ok") / n)

def riga(nome, a, b, fmt):
    va = fmt(a) if a else "-"; vb = fmt(b) if b else "-"
    print(f"{nome:34}{va:>12}{vb:>12}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simboli", default=SIMBOLI)
    ap.add_argument("--anni", type=float, default=4.5)
    ap.add_argument("--finestra", type=int, default=336, help="ore per media e scarto (336 = 14 giorni)")
    ap.add_argument("--entra", type=float, default=2.0)
    ap.add_argument("--esci", type=float, default=0.0)
    ap.add_argument("--stop", type=float, default=4.0)
    ap.add_argument("--quota", type=float, default=0.10, help="capitale per gamba di ogni operazione (0.10 = 10 %%)")
    ap.add_argument("--max-aperte", type=int, default=5)
    ap.add_argument("--dettagli", action="store_true")
    args = ap.parse_args()

    syms = args.simboli.split(",")
    dati = {s: carica(s, args.anni) for s in syms}
    comuni = sorted(set.intersection(*[set(d) for d in dati.values()]))
    if len(comuni) < args.finestra * 10:
        sys.exit("Troppi pochi dati in comune tra le monete.")
    taglio_t = comuni[int(len(comuni) * 0.6)]
    anni_pr = (taglio_t - comuni[0]) / (365 * 86400); anni_ve = (comuni[-1] - taglio_t) / (365 * 86400)
    print(f"{len(syms)} monete, {len(comuni)} ore in comune, {len(syms) * (len(syms) - 1) // 2} coppie")

    per_coppia = {}
    for a, b in combinations(syms, 2):
        ops = operazioni_coppia(comuni, [dati[a][t] for t in comuni], [dati[b][t] for t in comuni],
                                args.finestra, args.entra, args.esci, args.stop, args.finestra)
        per_coppia[(a, b)] = [o + (a, b) for o in ops]

    # selezione delle coppie SOLO sul periodo di prova
    scelte = []
    for k, ops in per_coppia.items():
        pr = [o[2] for o in ops if o[1] < taglio_t]
        if len(pr) >= 10 and sum(pr) / len(pr) > 0.0015:
            scelte.append(k)

    def blocco(coppie):
        tutte = [o for k in coppie for o in per_coppia[k]]
        pr = portafoglio([o for o in tutte if o[1] < taglio_t], args.max_aperte, 2)
        ve = portafoglio([o for o in tutte if o[0] >= taglio_t], args.max_aperte, 2)
        return riassunto(pr, args.quota, anni_pr), riassunto(ve, args.quota, anni_ve)

    pr, ve = blocco(scelte)
    tp, tv = blocco(list(per_coppia))

    if not ve:                                                      s = "🔴 NESSUNA COPPIA SUPERA LA PROVA"
    elif ve["medio"] > 0.001 and ve["t"] >= 3 and ve["mesi_pos"] >= 0.65: s = "🟢 REGGE NELLA VERIFICA"
    elif ve["medio"] > 0:                                           s = "🟡 POSITIVA MA NON DIMOSTRATA"
    else:                                                           s = "🔴 NON REGGE NELLA VERIFICA"
    print(f"\nVERDETTO: {s}")
    print(f"Coppie scelte nel periodo di prova: {len(scelte)} su {len(per_coppia)}\n")
    print(f"{'COPPIE SCELTE':34}{'Prova':>12}{'Verifica':>12}")
    pc = lambda k, d=1: (lambda r: f"{r[k] * 100:+.{d}f} %")
    riga("Operazioni", pr, ve, lambda r: str(r["n"]))
    riga("Operazioni in guadagno", pr, ve, lambda r: f"{r['vinte'] * 100:.0f} %")
    riga("Chiuse per stop o tempo", pr, ve, lambda r: f"{r['stop'] * 100:.0f} %")
    riga("Guadagno medio per operazione", pr, ve, pc("medio", 2))
    riga("Operazione peggiore", pr, ve, pc("peggiore"))
    riga("Mesi in guadagno", pr, ve, lambda r: f"{r['mesi_pos'] * 100:.0f} %")
    riga("Mese peggiore (sul capitale)", pr, ve, pc("mese_peggiore"))
    riga("Rendimento annuo (sul capitale)", pr, ve, pc("annuo"))
    print(f"\n{'TUTTE LE COPPIE (riferimento)':34}{'Prova':>12}{'Verifica':>12}")
    riga("Guadagno medio per operazione", tp, tv, pc("medio", 2))
    riga("Rendimento annuo (sul capitale)", tp, tv, pc("annuo"))

    if args.dettagli:
        print(f"\n{'Coppia':26}{'n pr':>6}{'medio pr':>10}{'n ve':>6}{'medio ve':>10}  scelta")
        righe = []
        for k, ops in per_coppia.items():
            a = [o[2] for o in ops if o[1] < taglio_t]; b = [o[2] for o in ops if o[0] >= taglio_t]
            righe.append((sum(b) / len(b) if b else 0, k, a, b))
        for mv, k, a, b in sorted(righe, reverse=True):
            nome = k[0].replace("PF_", "").replace("USD", "") + "/" + k[1].replace("PF_", "").replace("USD", "")
            ma = sum(a) / len(a) * 100 if a else 0
            print(f"{nome:26}{len(a):>6}{ma:>+9.2f}%{len(b):>6}{mv * 100:>+9.2f}%  {'✔' if k in scelte else ''}")

    print(f"""
Guadagni per operazione: in % dell'importo di una gamba, costi inclusi ({COSTO * 100:.2f} % a operazione).
Rendimenti sul capitale: {args.quota * 100:.0f} % del capitale per gamba, massimo {args.max_aperte} operazioni aperte insieme.
Non inclusi: funding (di solito piccolo, le due gambe si compensano in parte) e perdite latenti
durante l'operazione. Guarda "operazione peggiore" e "mese peggiore": e' li' che questa strategia fa male.""")

if __name__ == "__main__":
    main()
