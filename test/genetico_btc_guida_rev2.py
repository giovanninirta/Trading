#!/usr/bin/env python3
"""
ALGORITMO GENETICO "BTC GUIDA" - Rev 2  (perpetui Kraken, 30 monete)
Rev 2: ricerca piu' ampia, sei metodi di uscita, long E short, spread reale nei costi.

Segnale: BTC fa una candela forte (su -> long sulle monete, giu' -> short) e si scelgono le monete in base
a come si sono mosse nella stessa candela. Al massimo 5 monete per scatto, portafoglio con 5 posti.

Geni:
  ore        1, 2, 3, 4, 6, 8, 12, 24
  verso      solo long (BTC su) / solo short (BTC giu') / entrambi
  btc        forza minima della candela di BTC, in ATR (0,5 - 4,0)
  tipo       "partite" (moneta mossa almeno quanto la soglia nel verso di BTC), "ritardo" (al massimo la soglia),
             "tutte" (nessuna condizione sulla moneta)
  soglia     movimento della moneta, in ATR, nel verso di BTC (-2,0 - 3,0)
  universo   tutte le monete / solo le 12 piu' liquide (spread piu' basso)
  filtro     nessuno / solo se BTC sopra la media 200 / solo se BTC sotto la media 200
  stop       stop iniziale in ATR (0,5 - 4,0)
  pareggio   dopo +1 R lo stop si sposta al prezzo d'ingresso (si/no)
  uscita     TEMPO     dopo "tenuta" candele
             TRAILING  stop che segue il prezzo a "k" ATR dal miglior prezzo raggiunto
             OBIETTIVO a +"k" R
             RITORNO   quando il prezzo torna al livello di prima del segnale (pensata per "ritardo")
             CANALE    quando chiude oltre il minimo (massimo per lo short) delle ultime "k" candele
             BTC GIRA  quando BTC chiude sotto l'apertura della candela del segnale (sopra per lo short)
  k          parametro dell'uscita (0,5 - 4,0 per trailing e obiettivo; 2 - 20 candele per il canale)
  tenuta     durata massima in candele, per tutte le uscite (1 - 24)
Costi: 0,07 % per ordine + funding + spread di oggi della moneta (pagato intero) + 0,05 % per il ritardo.

Contro l'eccesso di adattamento (come Rev 1): l'algoritmo vede solo la prova (primo 60 %), voto = costanza per
scatto sulle operazioni davvero prese dal portafoglio, almeno 40 scatti in prova, tre semi diversi,
prova dei parametri vicini. Piu' combinazioni si provano, piu' e' facile trovarne una fortunata: per questo
conta solo cio' che regge in VERIFICA.

Uso (nella cartella dati):  python ../genetico_btc_guida_rev2.py
Solo libreria standard Python 3.8+.
"""
import json, math, os, random, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
from misuratore_ritest_rev1 import COSTO, FUNDING_ORA

GENI = {
    "ore":      [1, 2, 3, 4, 6, 8, 12, 24],
    "verso":    ["long", "short", "entrambi"],
    "btc":      [0.5 + 0.25 * k for k in range(15)],
    "tipo":     ["partite", "ritardo", "tutte"],
    "soglia":   [-2.0 + 0.25 * k for k in range(21)],
    "universo": ["tutte", "liquide"],
    "filtro":   ["nessuno", "sopra", "sotto"],
    "stop":     [0.5 + 0.25 * k for k in range(15)],
    "pareggio": [False, True],
    "uscita":   ["tempo", "trailing", "obiettivo", "ritorno", "canale", "btc"],
    "k":        [0.5 + 0.25 * k for k in range(15)],
    "tenuta":   [1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24],
}
RITARDO = 0.0005
MAX_POS = 5
POP, GENERAZIONI, ELITE, SEMI = 100, 40, 6, (1, 2, 3)
SPREAD_DEFAULT = 0.0015

def spread():
    if os.path.exists("SPREAD.json"):
        return json.load(open("SPREAD.json"))
    out = {}
    try:
        with urllib.request.urlopen("https://futures.kraken.com/derivatives/api/v3/tickers", timeout=30) as r:
            for t in json.load(r).get("tickers", []):
                s = t.get("symbol", "")
                if s.startswith("PF_") and s.endswith("USD") and t.get("bid") and t.get("ask"):
                    b, a = float(t["bid"]), float(t["ask"])
                    if a > b > 0: out[s[3:-3]] = (a - b) / ((a + b) / 2)
        json.dump(out, open("SPREAD.json", "w"))
    except Exception as e:
        print(f"spread non disponibile ({e}): uso {SPREAD_DEFAULT * 100:.2f} % per tutte")
    return out

def operazioni(D, g, SP, liquide):
    S = D.serie(g["ore"]); ore = g["ore"]
    Tb, Hb, Lb, Cb, Ab, Mb, idxb = S["XBT"]
    Ob = [None] + Cb[:-1]                          # apertura ~ chiusura precedente
    versi = {"long": (1,), "short": (-1,), "entrambi": (1, -1)}[g["verso"]]
    ops = []
    for i in range(200, len(Cb) - 1):
        if not Ab[i - 1]: continue
        zb = (Cb[i] - Cb[i - 1]) / Ab[i - 1]
        d = 1 if zb > g["btc"] else (-1 if zb < -g["btc"] else 0)
        if d == 0 or d not in versi: continue
        if g["filtro"] == "sopra" and not (Mb[i] and Cb[i] > Mb[i]): continue
        if g["filtro"] == "sotto" and not (Mb[i] and Cb[i] < Mb[i]): continue
        t = Tb[i]; scatto = []
        for m, (T, H, L, C, A, _, idx) in S.items():
            if m == "XBT" or (g["universo"] == "liquide" and m not in liquide): continue
            j = idx.get(t)
            if j is None or j < 30 or j >= len(C) - 1 or not A[j - 1] or H[j] == L[j]: continue
            z = (C[j] - C[j - 1]) / A[j - 1] * d
            if g["tipo"] == "partite" and z < g["soglia"]: continue
            if g["tipo"] == "ritardo" and z > g["soglia"]: continue
            e = C[j]; rischio = g["stop"] * A[j]; pct = rischio / e
            if pct < 0.002 or pct > 0.15: continue
            stop = e - d * rischio
            tp = e + d * g["k"] * rischio if g["uscita"] == "obiettivo" else None
            if g["uscita"] == "ritorno":
                tp = C[j - 1] if (C[j - 1] - e) * d > 0 else e + d * rischio
            meglio = e; r = None; k = j
            kc = max(2, int(round(g["k"] * 5)))     # canale: da 2 a 20 candele
            while k < min(j + g["tenuta"], len(C) - 1):
                k += 1
                peggio_k = L[k] if d == 1 else H[k]; meglio_k = H[k] if d == 1 else L[k]
                if (peggio_k - stop) * d <= 0: r = (stop - e) * d / rischio; break
                if tp is not None and (meglio_k - tp) * d >= 0: r = (tp - e) * d / rischio; break
                meglio = max(meglio, C[k]) if d == 1 else min(meglio, C[k])
                if g["pareggio"] and (meglio - e) * d >= rischio and (e - stop) * d > 0: stop = e
                if g["uscita"] == "trailing":
                    nuovo = meglio - d * g["k"] * A[j]
                    if (nuovo - stop) * d > 0: stop = nuovo
                if g["uscita"] == "canale" and k - j >= 1:
                    w = C[max(j, k - kc):k]
                    if w and ((d == 1 and C[k] < min(w)) or (d == -1 and C[k] > max(w))):
                        r = (C[k] - e) * d / rischio; break
                if g["uscita"] == "btc":
                    ib = idxb.get(T[k])
                    if ib is not None and (Cb[ib] - Ob[i]) * d < 0: r = (C[k] - e) * d / rischio; break
            if r is None: r = (C[k] - e) * d / rischio
            costo = 2 * COSTO + RITARDO + SP.get(m, SPREAD_DEFAULT) + FUNDING_ORA * ore * (k - j)
            r -= costo / pct
            scatto.append((T[j] + ore * 3600, T[k] + ore * 3600, m, z, pct, r))
        scatto.sort(key=lambda o: o[3] if g["tipo"] == "ritardo" else -o[3])
        ops += scatto[:MAX_POS]
    return ops

def chiave(g): return tuple(g[k] for k in GENI)
def casuale(rng): return {k: rng.choice(v) for k, v in GENI.items()}

def evolvi(D, SP, liquide, seme, memo):
    rng = random.Random(seme)
    def valuta(g):
        c = chiave(g)
        if c not in memo: memo[c] = G1.voto(G1.prese(operazioni(D, g, SP, liquide)), D, "prova")[0]
        return memo[c]
    pop = [casuale(rng) for _ in range(POP)]
    for gen in range(GENERAZIONI):
        pop.sort(key=valuta, reverse=True)
        if gen % 10 == 0 or gen == GENERAZIONI - 1:
            print(f"   seme {seme}  generazione {gen + 1:>2}: miglior voto in prova {valuta(pop[0]):+.2f}"
                  f"   (combinazioni provate finora {len(memo)})", flush=True)
        nuova = [dict(x) for x in pop[:ELITE]]
        while len(nuova) < POP:
            a = max(rng.sample(pop, 3), key=valuta); b = max(rng.sample(pop, 3), key=valuta)
            f = {k: (a[k] if rng.random() < 0.5 else b[k]) for k in GENI}
            for k, valori in GENI.items():
                if rng.random() < 0.15:
                    i = valori.index(f[k])
                    f[k] = valori[max(0, min(len(valori) - 1, i + rng.choice((-2, -1, 1, 2))))] if rng.random() < 0.7 else rng.choice(valori)
            nuova.append(f)
        pop = nuova
    return sorted(pop, key=valuta, reverse=True)

def descrivi(g):
    usc = {"tempo": "a tempo", "trailing": f"trailing {g['k']:.2f} ATR", "obiettivo": f"obiettivo {g['k']:.2f} R",
           "ritorno": "ritorno al livello di prima", "canale": f"canale {max(2, int(round(g['k'] * 5)))} candele",
           "btc": "quando BTC si gira"}[g["uscita"]]
    tipo = {"partite": f"moneta >= {g['soglia']:+.2f} ATR", "ritardo": f"moneta <= {g['soglia']:+.2f} ATR", "tutte": "tutte le monete"}[g["tipo"]]
    return (f"{g['ore']:>2}h {g['verso']} | BTC > {g['btc']:.2f} ATR | {tipo} | {g['universo']} | filtro {g['filtro']} | "
            f"stop {g['stop']:.2f} ATR{' + pareggio' if g['pareggio'] else ''} | uscita {usc}, max {g['tenuta']} candele").replace(".", ",")

def scheda(D, g, SP, liquide, anni, durata):
    ops = operazioni(D, g, SP, liquide)
    cap, calo, curva, fatte = G1.portafoglio(ops)
    vp, np_, mp = G1.voto(fatte, D, "prova"); vv, nv, mv = G1.voto(fatte, D, "verifica")
    import calendar
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
    annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
    s = "🟢" if vp > 2 and vv > 1.5 and mv > 0.05 else ("🟡" if mp > 0 and mv > 0 else "🔴")
    return s, f"{vp:>+6.1f}{vv:>+7.1f}{mp:>+8.2f}{mv:>+8.2f}{(np_ + nv) / durata:>8.0f}{annuo * 100:>+7.0f}%{calo * 100:>+7.0f}%{celle}"

def main():
    D = G1.Dati(); SP = spread()
    liquide = set(sorted((m for m in D.uno if m != "XBT"), key=lambda m: SP.get(m, 1))[:12])
    anni = list(range(time.gmtime(D.t0).tm_year, time.gmtime(D.t1).tm_year + 1))
    durata = (D.t1 - D.t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{len(D.uno)} monete, dal {d(D.t0)} al {d(D.t1)}. L'algoritmo vede solo la prova (fino al {d(D.taglio)}).")
    print(f"Monete liquide: {' '.join(sorted(liquide))}\n")
    memo, finali = {}, []
    for seme in SEMI:
        finali += evolvi(D, SP, liquide, seme, memo)
    print(f"\n   combinazioni provate in tutto: {len(memo)}\n")
    viste, migliori = set(), []
    for g in sorted(finali, key=lambda g: memo[chiave(g)], reverse=True):
        if chiave(g) in viste: continue
        viste.add(chiave(g)); migliori.append(g)
        if len(migliori) == 12: break
    # la migliore di ogni seme, per vedere se convergono
    print("MIGLIORE DI OGNI CORSA (semi diversi: se si somigliano, la regola e' piu' credibile)")
    for seme, i in zip(SEMI, range(0, len(finali), POP)):
        print(f"   seme {seme}: {descrivi(finali[i])}")
    print("\nLE 12 MIGLIORI COMBINAZIONI (scelte guardando solo la prova)")
    print("Annuo, calo e anni: rischio 0,5 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.\n")
    print(f"   {'Voto prova':>8}{'verif.':>7}{'R prova':>8}{'R verif':>8}{'Scatti/a':>8}{'Annuo':>8}{'Calo':>8}" + "".join(f"{a:>7}" for a in anni))
    for n, g in enumerate(migliori, 1):
        s, riga = scheda(D, g, SP, liquide, anni, durata)
        print(f"{n:>2}. {descrivi(g)}")
        print(f"{s} {riga}")
    g0 = migliori[0]
    print("\nPARAMETRI VICINI ALLA MIGLIORE (ogni gene un passo in piu' e in meno)")
    print(f"   {'Cambio':30}{'Voto prova':>11}{'Voto verif.':>12}{'R verif':>9}")
    for k, valori in GENI.items():
        i = valori.index(g0[k])
        for j in (i - 1, i + 1):
            if not 0 <= j < len(valori): continue
            g = dict(g0); g[k] = valori[j]
            f = G1.prese(operazioni(D, g, SP, liquide))
            vp = G1.voto(f, D, "prova")[0]; vv, _, mv = G1.voto(f, D, "verifica")
            print(f"   {k + ' = ' + str(valori[j]):30}{vp:>+11.1f}{vv:>+12.1f}{mv:>+9.2f}")
    print("""
Voto: costanza del risultato per scatto di BTC (sopra +2 = netto, sotto +1 = probabilmente fortuna).
R: risultato medio per scatto in multipli del rischio, costi e spread inclusi.   Scatti/a: scatti di BTC all'anno.
🟢 voto netto in prova E in verifica   🟡 positivo in entrambi ma non netto   🔴 negativo in verifica""")

if __name__ == "__main__":
    main()
