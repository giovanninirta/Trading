#!/usr/bin/env python3
"""
MISURATORE ACCUMULO BTC - Rev 2
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

Rev 2: le stesse regole provate su tre intervalli (candele da 1 giorno, 4 ore, 1 ora).
Le regole restano espresse in candele: su candele da 4 ore "30 candele" sono 5 giorni,
su candele da 1 ora sono 30 ore. Intervallo piu' corto = molti piu' passaggi.

Uso (nella cartella con i file *_1h.csv gia' scaricati):
  python misuratore_accumulo_btc_rev2.py
  python misuratore_accumulo_btc_rev2.py --dettagli
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
    comuni = set.intersection(*[set(d) for d in dati.values()])
    alts = [s for s in syms if s != BTC]
    intervalli = [("1 giorno", 24), ("4 ore", 4), ("1 ora", 1)]
    strategie = [("A) Forza", forza), ("B) Ribasso", ribasso)]
    costi = [("senza costi", 0.0), ("perpetui", 0.0014), ("spot", 0.008)]
    ris = {}
    rif = None
    for nome_tf, ore in intervalli:
        tempi = sorted(t for t in comuni if t % (ore * 3600) == 0)
        R = {c: [dati[c][t] / dati[BTC][t] for t in tempi] for c in alts}
        taglio = int(len(tempi) * 0.6)
        periodi = [(0, taglio), (taglio, len(tempi))]
        if rif is None:
            rif = [simula({c: R[c][a:b] for c in alts}, alts, fermo_alt, 0.0014) for a, b in periodi]
            print(f"{len(alts)} monete oltre a BTC, {len(tempi) / 365:.1f} anni di dati\n")
        for nome_s, strat in strategie:
            for nome_c, costo in costi:
                ris[(nome_s, nome_tf, nome_c)] = [simula({c: R[c][a:b] for c in alts}, alts, strat(), costo) for a, b in periodi]

    def sem(v):
        if all(x[0] >= 1.05 for x in v): return "🟢"
        if all(x[0] > 1.0 for x in v):   return "🟡"
        return "🔴"
    num = lambda x: f"{x:.3f}".replace(".", ",")
    print(f"{'BTC finali partendo da 1,000 (costi perpetui)':48}{'Primi 60 %':>12}{'Ultimi 40 %':>13}")
    print(f"   {'Tenere BTC fermo':45}{num(1.0):>12}{num(1.0):>13}")
    print(f"   {'Tenere le altre monete, mai scambiare':45}{num(rif[0][0]):>12}{num(rif[1][0]):>13}")
    for nome_s, _ in strategie:
        for nome_tf, _ in intervalli:
            v = ris[(nome_s, nome_tf, "perpetui")]
            print(f"{sem(v)} {nome_s + ' - candele da ' + nome_tf:45}{num(v[0][0]):>12}{num(v[1][0]):>13}")
    if args.dettagli:
        for nome_c in ("senza costi", "spot"):
            print(f"\n{'Stesso calcolo, ' + nome_c:48}{'Primi 60 %':>12}{'Ultimi 40 %':>13}")
            for nome_s, _ in strategie:
                for nome_tf, _ in intervalli:
                    v = ris[(nome_s, nome_tf, nome_c)]
                    print(f"{sem(v)} {nome_s + ' - candele da ' + nome_tf:45}{num(v[0][0]):>12}{num(v[1][0]):>13}")
        print(f"\n{'Numero di passaggi / calo massimo in BTC':48}{'Primi 60 %':>12}{'Ultimi 40 %':>13}")
        for nome_s, _ in strategie:
            for nome_tf, _ in intervalli:
                v = ris[(nome_s, nome_tf, "perpetui")]
                print(f"   {nome_s + ' - candele da ' + nome_tf:45}{f'{v[0][2]} / {v[0][1] * 100:.0f} %':>12}{f'{v[1][2]} / {v[1][1] * 100:.0f} %':>13}")
    print("""
🟢 almeno +5 % di BTC in entrambi i periodi   🟡 piu' BTC in entrambi, ma di poco   🔴 meno BTC in almeno un periodo
"Senza costi" (con --dettagli) dice se il segnale ha un vantaggio prima delle commissioni:
se e' rosso anche li', il problema e' la regola, non il costo.""")

if __name__ == "__main__":
    main()
