#!/usr/bin/env python3
"""
MISURATORE ACCUMULO BTC - Rev 1
Domanda: partendo da 1 BTC, passando a tratti su altre monete e tornando in BTC,
alla fine ho piu' BTC o meno BTC di chi e' rimasto fermo?
Tutto e' misurato in BTC: 1,000 = pari, 1,100 = +10 % di bitcoin, 0,900 = -10 %.

Strategie messe a confronto (regole fissate prima, nessuna ottimizzazione):
  A) FORZA      una volta a settimana passa sulle 2 monete che negli ultimi 30 giorni
                sono salite di piu' rispetto a BTC (e sono sopra la loro media);
                se nessuna e' piu' forte di BTC, resta in BTC.
  B) RIBASSO    passa su una moneta quando e' scesa troppo rispetto a BTC (2 scarti sotto
                la media a 20 giorni) e torna in BTC quando recupera la media.
                Stop: -15 % sulla quota, 4 scarti, oppure 20 giorni. Massimo 3 quote.
  Riferimenti   tenere BTC fermo (= 1,000) e tenere le altre monete senza mai scambiare.
Costi di ogni passaggio BTC <-> moneta, in due ipotesi:
  perpetui  0,14 %  (BTC resta come garanzia, lo scambio si fa con due ordini sui perpetui)
  spot      0,80 %  (due ordini limite su Kraken Pro a 0,40 %: BTC -> EUR -> moneta)

Uso (nella cartella con i file *_1h.csv gia' scaricati):
  python misuratore_accumulo_btc_rev1.py
  python misuratore_accumulo_btc_rev1.py --dettagli
Solo libreria standard Python 3.8+.
"""
import argparse, csv, math, os, sys

SIMBOLI = "PF_XBTUSD,PF_ETHUSD,PF_SOLUSD,PF_XRPUSD,PF_ADAUSD,PF_DOGEUSD,PF_LTCUSD,PF_LINKUSD,PF_AVAXUSD,PF_DOTUSD"
BTC = "PF_XBTUSD"

def carica(sym):
    path = f"{sym}_1h.csv"
    if not os.path.exists(path):
        sys.exit(f"Manca il file {path}: lancia prima il misuratore di figure o di coppie con questa moneta.")
    out = {}
    with open(path) as f:
        for r in csv.reader(f):
            try: out[int(float(r[0]))] = float(r[4])
            except (ValueError, IndexError): pass
    return out

def simula(R, alts, strategia, costo):
    """R[c] = serie giornaliera del rapporto moneta/BTC. Ritorna (valore finale in BTC, calo massimo, n. passaggi)."""
    n = len(next(iter(R.values())))
    V, picco, calo, passaggi = 1.0, 1.0, 0.0, 0
    w = {c: 0.0 for c in alts}                # quota del portafoglio su ogni moneta; il resto e' BTC
    stato = {}
    for t in range(1, n):
        # 1) il mercato si muove
        rp = sum(w[c] * (R[c][t] / R[c][t - 1] - 1) for c in alts)
        for c in alts:
            if w[c]: w[c] = w[c] * (R[c][t] / R[c][t - 1]) / (1 + rp)
        V *= 1 + rp
        # 2) la strategia decide le nuove quote
        nuovo = strategia(t, R, alts, dict(w), stato)
        if nuovo is not None:
            giro = sum(abs(nuovo[c] - w[c]) for c in alts)
            if giro > 1e-9:
                V *= 1 - giro * costo
                passaggi += sum(1 for c in alts if abs(nuovo[c] - w[c]) > 1e-9)
                w = nuovo
        picco = max(picco, V); calo = min(calo, V / picco - 1)
    return V, calo, passaggi

def forza(L=30, ogni=7, K=2):
    def f(t, R, alts, w, stato):
        if t < L or t % ogni: return None
        cand = []
        for c in alts:
            media = sum(R[c][t - L + 1:t + 1]) / L
            mom = R[c][t] / R[c][t - L] - 1
            if mom > 0 and R[c][t] > media: cand.append((mom, c))
        scelti = [c for _, c in sorted(cand, reverse=True)[:K]]
        return {c: (1.0 / K if c in scelti else 0.0) for c in alts}
    return f

def ribasso(W=20, z_in=-2.0, z_stop=-4.0, K=3, perdita=-0.15):
    def f(t, R, alts, w, stato):
        if t < W: return None
        nuovo, cambiato = dict(w), False
        for c in alts:
            s = [math.log(x) for x in R[c][t - W + 1:t + 1]]
            m = sum(s) / W; sd = (sum((x - m) ** 2 for x in s) / W) ** 0.5
            if sd < 1e-9: continue
            z = (s[-1] - m) / sd
            if c in stato:
                r_in, t_in = stato[c]
                if z >= 0 or z <= z_stop or t - t_in >= W or R[c][t] / r_in - 1 <= perdita:
                    nuovo[c] = 0.0; del stato[c]; cambiato = True
            elif z <= z_in and z > z_stop and len(stato) < K:
                nuovo[c] = 1.0 / K; stato[c] = (R[c][t], t); cambiato = True
        return nuovo if cambiato else None
    return f

def fermo_alt(t, R, alts, w, stato):
    if t == 1: return {c: 1.0 / len(alts) for c in alts}
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simboli", default=SIMBOLI)
    ap.add_argument("--dettagli", action="store_true")
    args = ap.parse_args()
    syms = args.simboli.split(",")
    if BTC not in syms: sys.exit("Serve PF_XBTUSD tra i simboli.")
    dati = {s: carica(s) for s in syms}
    giorni = sorted(t for t in set.intersection(*[set(d) for d in dati.values()]) if t % 86400 == 0)
    alts = [s for s in syms if s != BTC]
    R = {c: [dati[c][t] / dati[BTC][t] for t in giorni] for c in alts}
    taglio = int(len(giorni) * 0.6)
    periodi = {"Primi 60 %": (0, taglio), "Ultimi 40 %": (taglio, len(giorni))}
    print(f"{len(alts)} monete oltre a BTC, {len(giorni)} giorni ({len(giorni) / 365:.1f} anni)\n")

    righe = [("Tenere BTC fermo", None, 0),
             ("Tenere le altre monete, mai scambiare", lambda: fermo_alt, 0.0014),
             ("A) Forza  - con perpetui", forza, 0.0014),
             ("A) Forza  - con spot", forza, 0.008),
             ("B) Ribasso - con perpetui", ribasso, 0.0014),
             ("B) Ribasso - con spot", ribasso, 0.008)]
    ris = {}
    for nome, strat, costo in righe:
        ris[nome] = []
        for a, b in periodi.values():
            if strat is None: ris[nome].append((1.0, 0.0, 0)); continue
            ris[nome].append(simula({c: R[c][a:b] for c in alts}, alts, strat(), costo))

    def semaforo(v):
        if all(x[0] >= 1.05 for x in v): return "🟢"
        if all(x[0] > 1.0 for x in v):   return "🟡"
        return "🔴"
    print(f"{'BTC finali partendo da 1,000':42}{'Primi 60 %':>12}{'Ultimi 40 %':>13}")
    for nome, _, _ in righe:
        v = ris[nome]
        s = "  " if nome.startswith("Tenere") else semaforo(v)
        print(f"{s} {nome:39}{v[0][0]:>12.3f}{v[1][0]:>13.3f}".replace(".", ","))
    if args.dettagli:
        print(f"\n{'Calo massimo in BTC / n. passaggi':42}{'Primi 60 %':>12}{'Ultimi 40 %':>13}")
        for nome, strat, _ in righe:
            if strat is None: continue
            v = ris[nome]
            print(f"   {nome:39}{f'{v[0][1] * 100:.0f} % / {v[0][2]}':>12}{f'{v[1][1] * 100:.0f} % / {v[1][2]}':>13}")
        print(f"\n{'Ogni moneta contro BTC (senza scambi)':42}{'Primi 60 %':>12}{'Ultimi 40 %':>13}")
        for c in alts:
            a = R[c][taglio - 1] / R[c][0]; b = R[c][-1] / R[c][taglio]
            print(f"   {c.replace('PF_', '').replace('USD', ''):39}{a:>12.3f}{b:>13.3f}".replace(".", ","))
    print("""
🟢 almeno +5 % di BTC in entrambi i periodi   🟡 piu' BTC in entrambi, ma di poco   🔴 meno BTC in almeno un periodo
Ogni periodo riparte da 1,000 BTC. Il valore in euro non conta qui: conta solo quanti BTC restano.""")

if __name__ == "__main__":
    main()
