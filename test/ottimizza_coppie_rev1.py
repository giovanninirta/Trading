#!/usr/bin/env python3
"""
OTTIMIZZAZIONE COPPIE - Rev 1
Prova tutte le combinazioni di parametri della strategia a coppie e risponde a due domande:
  1) quali parametri sono andati meglio nel periodo di PROVA (primo 60 % dei dati)?
  2) quei parametri restano buoni nel periodo di VERIFICA (ultimo 40 %), che non e' stato usato per sceglierli?
La seconda e' quella che conta: se i migliori in prova non restano tra i migliori in verifica,
l'ottimizzazione sta solo imparando a memoria il passato.

Parametri esplorati:
  candele      1 ora, 4 ore
  finestra     3, 7, 14, 21, 30 giorni   (media e scarto della distanza)
  ingresso     1,5 - 2 - 2,5 - 3 scarti
  uscita       0 (ritorno alla media) - 0,5 - 1 scarto (esce prima, a meta' strada)
  stop perdita nessuno, oppure -10 % sull'operazione
Fissi: stop a 4 scarti, uscita a tempo pari alla finestra, costi 0,28 % a operazione,
       10 % del capitale per gamba, massimo 5 operazioni aperte.

Uso (nella cartella con i file *_1h.csv):
  python ottimizza_coppie_rev1.py
Usa tutti i processori del PC; richiede qualche minuto. Salva la griglia completa in ottimizzazione_coppie.csv
Solo libreria standard Python 3.8+.
"""
import argparse, csv, math, os, sys, time
from collections import defaultdict
from itertools import combinations, product
from multiprocessing import Pool

SIMBOLI = "PF_XBTUSD,PF_ETHUSD,PF_SOLUSD,PF_XRPUSD,PF_ADAUSD,PF_DOGEUSD,PF_LTCUSD,PF_LINKUSD,PF_AVAXUSD,PF_DOTUSD"
COSTO = 4 * (0.0005 + 0.0002)
QUOTA, MAX_APERTE, Z_STOP = 0.10, 5, 4.0
CANDELE = [1, 4]
FINESTRE = [72, 168, 336, 504, 720]           # ore
ENTRA = [1.5, 2.0, 2.5, 3.0]
ESCI = [0.0, 0.5, 1.0]
PERDITA = [None, -0.10]

def carica(sym):
    path = f"{sym}_1h.csv"
    if not os.path.exists(path):
        sys.exit(f"Manca il file {path}: lancia prima misuratore_coppie con questa moneta.")
    out = {}
    with open(path) as f:
        for r in csv.reader(f):
            try: out[int(float(r[0]))] = float(r[4])
            except (ValueError, IndexError): pass
    return out

def serie_z(s, W):
    n = len(s); z = [None] * n; c1 = c2 = 0.0
    for i in range(n):
        v = s[i]; c1 += v; c2 += v * v
        if i >= W:
            u = s[i - W]; c1 -= u; c2 -= u * u
        if i >= W - 1 and i >= W:
            m = c1 / W; var = c2 / W - m * m
            if var > 1e-12: z[i] = (v - m) / math.sqrt(var)
    return z

def simula(ts, s, z, W, z_in, z_out, perdita):
    out = []; pos = 0; s_in = 0.0; i_in = 0; blocco = False
    for i in range(W, len(s)):
        zi = z[i]
        if zi is None: continue
        if pos == 0:
            if blocco:
                if -1 < zi < 1: blocco = False
                continue
            if zi >= z_in:
                if zi < Z_STOP: pos = -1; s_in = s[i]; i_in = i
            elif zi <= -z_in:
                if zi > -Z_STOP: pos = 1; s_in = s[i]; i_in = i
        else:
            g = pos * (s[i] - s_in)
            if (pos == -1 and zi <= z_out) or (pos == 1 and zi >= -z_out): ok = True
            elif zi >= Z_STOP or zi <= -Z_STOP or i - i_in >= W or (perdita is not None and g <= perdita): ok = False
            else: continue
            out.append((ts[i_in], ts[i], g - COSTO))
            blocco = not ok; pos = 0
    return out

def portafoglio(ops):
    ops = sorted(ops); aperte = []; presi = []
    for o in ops:
        aperte = [x for x in aperte if x[1] > o[0]]
        if len(aperte) >= MAX_APERTE: continue
        conta = defaultdict(int)
        for x in aperte: conta[x[3]] += 1; conta[x[4]] += 1
        if conta[o[3]] >= 2 or conta[o[4]] >= 2: continue
        aperte.append(o); presi.append(o)
    return presi

def riassunto(ops, anni):
    if not ops: return None
    p = [o[2] for o in ops]; n = len(p)
    mesi = defaultdict(float)
    for o in ops:
        g = time.gmtime(o[1]); mesi[(g.tm_year, g.tm_mon)] += o[2] * QUOTA
    return dict(n=n, medio=sum(p) / n, annuo=sum(p) * QUOTA / anni, mese_peggiore=min(mesi.values()))

_D = {}
def _init(syms, dati, comuni, taglio_t, anni_pr, anni_ve):
    _D.update(syms=syms, dati=dati, comuni=comuni, taglio_t=taglio_t, anni_pr=anni_pr, anni_ve=anni_ve)

def lavoro(arg):
    ore, W_ore = arg
    syms, dati, taglio_t = _D["syms"], _D["dati"], _D["taglio_t"]
    ts = [t for t in _D["comuni"] if t % (ore * 3600) == 0]
    W = W_ore // ore
    logp = {s: [math.log(dati[s][t]) for t in ts] for s in syms}
    combo = list(product(ENTRA, ESCI, PERDITA))
    per = {c: {} for c in combo}
    for a, b in combinations(syms, 2):
        s = [x - y for x, y in zip(logp[a], logp[b])]
        z = serie_z(s, W)
        for c in combo:
            per[c][(a, b)] = [o + (a, b) for o in simula(ts, s, z, W, c[0], c[1], c[2])]
    righe = []
    for c in combo:
        scelte = []
        for k, ops in per[c].items():
            pr = [o[2] for o in ops if o[1] < taglio_t]
            if len(pr) >= 10 and sum(pr) / len(pr) > 0.0015: scelte.append(k)
        tutte = [o for k in scelte for o in per[c][k]]
        pr = riassunto(portafoglio([o for o in tutte if o[1] < taglio_t]), _D["anni_pr"])
        ve = riassunto(portafoglio([o for o in tutte if o[0] >= taglio_t]), _D["anni_ve"])
        righe.append(dict(candele=ore, finestra=W_ore, entra=c[0], esci=c[1], perdita=c[2], coppie=len(scelte),
                          annuo_pr=pr["annuo"] if pr else None, annuo_ve=ve["annuo"] if ve else None,
                          medio_ve=ve["medio"] if ve else None, n_ve=ve["n"] if ve else 0,
                          mese_ve=ve["mese_peggiore"] if ve else None))
    return righe

def ranghi(v):
    ordine = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
    for pos, i in enumerate(ordine): r[i] = pos
    return r

def correlazione(a, b):
    ra, rb = ranghi(a), ranghi(b); n = len(a); ma = (n - 1) / 2
    num = sum((x - ma) * (y - ma) for x, y in zip(ra, rb)); den = sum((x - ma) ** 2 for x in ra)
    return num / den if den else 0

def descr(r):
    f = r["finestra"]; fin = f"{f // 24} g"
    per = "-10 %" if r["perdita"] else "no"
    return f"{str(r['candele']) + ' h':>8}{fin:>9}{r['entra']:>8.1f}{r['esci']:>7.1f}{per:>8}{r['coppie']:>8}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simboli", default=SIMBOLI)
    ap.add_argument("--processi", type=int, default=None)
    args = ap.parse_args()
    syms = args.simboli.split(",")
    dati = {s: carica(s) for s in syms}
    comuni = sorted(set.intersection(*[set(d) for d in dati.values()]))
    taglio_t = comuni[int(len(comuni) * 0.6)]
    anni_pr = (taglio_t - comuni[0]) / (365 * 86400); anni_ve = (comuni[-1] - taglio_t) / (365 * 86400)
    compiti = list(product(CANDELE, FINESTRE))
    n_combo = len(compiti) * len(ENTRA) * len(ESCI) * len(PERDITA)
    print(f"{len(syms)} monete, {len(comuni)} ore, {n_combo} combinazioni di parametri. Calcolo in corso...")
    t0 = time.time()
    with Pool(args.processi, initializer=_init, initargs=(syms, dati, comuni, taglio_t, anni_pr, anni_ve)) as pool:
        righe = [r for blocco in pool.map(lavoro, compiti) for r in blocco]
    print(f"Fatto in {time.time() - t0:.0f} secondi.\n")

    with open("ottimizzazione_coppie.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(righe[0])); w.writeheader(); w.writerows(righe)

    valide = [r for r in righe if r["annuo_pr"] is not None and r["annuo_ve"] is not None]
    if len(valide) < 10:
        sys.exit("Troppe poche combinazioni con coppie valide.")
    valide.sort(key=lambda r: -r["annuo_pr"])
    top = valide[:10]
    media = lambda v: sum(v) / len(v)
    m_top, m_tutte = media([r["annuo_ve"] for r in top]), media([r["annuo_ve"] for r in valide])
    corr = correlazione([r["annuo_pr"] for r in valide], [r["annuo_ve"] for r in valide])
    positive = sum(1 for r in valide if r["annuo_ve"] > 0) / len(valide)
    migliore = top[0]

    if corr >= 0.3 and m_top > m_tutte + 0.02 and m_top > 0.05: s = "🟢 I PARAMETRI MIGLIORI IN PROVA RESTANO MIGLIORI IN VERIFICA"
    elif m_top > 0 and corr > 0:                                s = "🟡 OTTIMIZZARE AIUTA POCO"
    else:                                                       s = "🔴 OTTIMIZZARE NON AIUTA: i migliori in prova non restano migliori in verifica"
    pc = lambda x: f"{x * 100:+.1f} %"
    print(f"VERDETTO: {s}\n")
    print(f"{'Migliore combinazione in prova':46}{pc(migliore['annuo_pr']):>10} in prova  ->{pc(migliore['annuo_ve']):>9} in verifica")
    print(f"{'Media delle 10 migliori in prova':46}{pc(media([r['annuo_pr'] for r in top])):>10} in prova  ->{pc(m_top):>9} in verifica")
    print(f"{'Media di tutte le ' + str(len(valide)) + ' combinazioni':46}{pc(media([r['annuo_pr'] for r in valide])):>10} in prova  ->{pc(m_tutte):>9} in verifica")
    print(f"{'Combinazioni positive in verifica':46}{positive * 100:>9.0f} %")
    print(f"{'Legame tra classifica in prova e in verifica':46}{corr:>+10.2f}   (+1 = stessa classifica, 0 = nessun legame)")

    testa = f"{'Candele':>8}{'Finestra':>9}{'Entra':>8}{'Esci':>7}{'Stop':>8}{'Coppie':>8}{'Prova':>10}{'Verifica':>10}{'Mese pegg.':>12}"
    print(f"\nLE 10 MIGLIORI IN PROVA (rendimento annuo sul capitale)\n{testa}")
    for r in top:
        print(f"{descr(r)}{pc(r['annuo_pr']):>10}{pc(r['annuo_ve']):>10}{pc(r['mese_ve']):>12}")
    print(f"\nLE 10 MIGLIORI IN VERIFICA (col senno di poi: NON sono sceglibili in anticipo)\n{testa}")
    for r in sorted(valide, key=lambda r: -r["annuo_ve"])[:10]:
        print(f"{descr(r)}{pc(r['annuo_pr']):>10}{pc(r['annuo_ve']):>10}{pc(r['mese_ve']):>12}")

    print("\nMEDIA IN VERIFICA PER VALORE DI OGNI PARAMETRO (mostra se un valore e' migliore in modo stabile)")
    for nome, chiave, fmt in (("Candele", "candele", lambda v: f"{v} h"), ("Finestra", "finestra", lambda v: f"{v // 24} g"),
                              ("Entra", "entra", lambda v: f"{v:.1f}"), ("Esci", "esci", lambda v: f"{v:.1f}"),
                              ("Stop perdita", "perdita", lambda v: "-10 %" if v else "no")):
        gruppi = defaultdict(list)
        for r in valide: gruppi[r[chiave]].append(r)
        pezzi = [f"{fmt(k)}: {pc(media([x['annuo_pr'] for x in g]))} -> {pc(media([x['annuo_ve'] for x in g]))}"
                 for k, g in sorted(gruppi.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))]
        print(f"  {nome:13}" + "   |   ".join(pezzi))
    print("\n(prova -> verifica)   Griglia completa salvata in ottimizzazione_coppie.csv")

if __name__ == "__main__":
    main()
