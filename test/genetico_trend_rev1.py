#!/usr/bin/env python3
"""
ALGORITMO GENETICO "ROTTURE E TREND" - Rev 1  (perpetui Kraken, solo monete liquide)
Famiglia di regole: si entra quando il prezzo chiude oltre il massimo (long) o il minimo (short) delle
ultime N candele, con filtri facoltativi, e si esce con uno di quattro metodi.
Monete: BTC + le 12 con lo spread piu' basso oggi (niente monete illiquide: niente rimbalzi "finti").

Geni:
  ore        1, 2, 4, 6, 8, 12, 24
  verso      long / short / entrambi
  N          candele del canale d'ingresso: 10 - 200
  margine    la chiusura deve superare il massimo di almeno 0 / 0,25 / 0,5 / 1 ATR
  filtro     nessuno / BTC sopra (long) o sotto (short) la sua media 200 / moneta piu' forte (long) o piu'
             debole (short) di BTC sulle ultime N candele / entrambi i filtri
  volat.     qualsiasi / solo se la volatilita' e' bassa (ATR sotto 0,8 volte la sua media 100) / solo se alta
  stop       stop iniziale in ATR: 1 - 6
  uscita     CANALE    chiude sotto il minimo (sopra il massimo) delle ultime X candele
             TRAILING  stop che segue il prezzo a k ATR dal miglior prezzo raggiunto
             OBIETTIVO a +k R
             TEMPO     solo durata massima
  X          5 - 55 candele (per l'uscita a canale)     k  1 - 5 (trailing in ATR, obiettivo in R)
  tenuta     durata massima: 12 - 500 candele
Una posizione per moneta alla volta. Portafoglio: rischio 0,5 % per operazione, massimo 5 posizioni, leva max 3.
Costi: 0,07 % per ordine + spread di oggi della moneta + 0,05 % per il ritardo + funding 0,01 % ogni 8 ore.

Contro l'eccesso di adattamento: l'algoritmo vede solo la prova (primo 60 %); voto = costanza per GIORNO
sulle operazioni davvero prese dal portafoglio (le operazioni dello stesso giorno contano come una);
almeno 40 giorni con operazioni in prova; due semi; prova dei parametri vicini.

Uso (nella cartella dati):  python ../genetico_trend_rev1.py
Solo libreria standard Python 3.8+.
"""
import calendar, math, os, random, sys, time
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
import genetico_btc_guida_rev2 as G2
from misuratore_ritest_rev1 import COSTO, FUNDING_ORA

GENI = {
    "ore":     [1, 2, 4, 6, 8, 12, 24],
    "verso":   ["long", "short", "entrambi"],
    "N":       [10, 15, 20, 30, 40, 55, 80, 100, 150, 200],
    "margine": [0.0, 0.25, 0.5, 1.0],
    "filtro":  ["nessuno", "btc", "forza", "entrambi"],
    "volat":   ["qualsiasi", "bassa", "alta"],
    "stop":    [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0],
    "uscita":  ["canale", "trailing", "obiettivo", "tempo"],
    "X":       [5, 10, 15, 20, 30, 40, 55],
    "k":       [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],
    "tenuta":  [12, 24, 48, 100, 200, 500],
}
RITARDO = 0.0005
POP, GENERAZIONI, ELITE, SEMI = 80, 30, 6, (1, 2)
MIN_GIORNI = 40

def mobile(v, n, alto):
    """out[i] = max (alto) o min di v[i-n..i-1]."""
    out, d = [None] * len(v), deque()
    for i in range(1, len(v)):
        x = v[i - 1]
        while d and ((v[d[-1]] <= x) if alto else (v[d[-1]] >= x)): d.pop()
        d.append(i - 1)
        while d[0] < i - n: d.popleft()
        if i >= n: out[i] = v[d[0]]
    return out

class Cache:
    def __init__(self, D, monete):
        self.D, self.monete, self.c = D, monete, {}
    def get(self, ore, m, chiave):
        k = (ore, m, chiave)
        if k not in self.c:
            T, H, L, C, A, M200, idx = self.D.serie(ore)[m]
            if chiave[0] == "max": self.c[k] = mobile(C, chiave[1], True)
            elif chiave[0] == "min": self.c[k] = mobile(C, chiave[1], False)
            elif chiave[0] == "atrm":
                out, s = [None] * len(A), 0.0
                for i in range(len(A)):
                    s += A[i]
                    if i >= 100: s -= A[i - 100]
                    if i >= 99: out[i] = s / 100
                self.c[k] = out
        return self.c[k]

def operazioni(D, K, g, SP, monete):
    ore = g["ore"]; S = D.serie(ore)
    Tb, Hb, Lb, Cb, Ab, Mb, idxb = S["XBT"]
    versi = {"long": (1,), "short": (-1,), "entrambi": (1, -1)}[g["verso"]]
    N, ops = g["N"], []
    for m in monete:
        T, H, L, C, A, M200, idx = S[m]
        alto, basso = K.get(ore, m, ("max", N)), K.get(ore, m, ("min", N))
        atrm = K.get(ore, m, ("atrm", 0)) if g["volat"] != "qualsiasi" else None
        Xa = K.get(ore, m, ("max", g["X"])) if g["uscita"] == "canale" else None
        Xb = K.get(ore, m, ("min", g["X"])) if g["uscita"] == "canale" else None
        i = max(N, 210); n = len(C)
        while i < n - 1:
            d = 0
            if alto[i] is not None and A[i]:
                if 1 in versi and C[i] > alto[i] + g["margine"] * A[i]: d = 1
                elif -1 in versi and C[i] < basso[i] - g["margine"] * A[i]: d = -1
            if d and g["filtro"] in ("btc", "entrambi"):
                ib = idxb.get(T[i])
                if ib is None or Mb[ib] is None or (Cb[ib] - Mb[ib]) * d <= 0: d = 0
            if d and g["filtro"] in ("forza", "entrambi") and m != "XBT":
                ib = idxb.get(T[i]); ib0 = idxb.get(T[i - N])
                if ib is None or ib0 is None or ((C[i] / C[i - N]) - (Cb[ib] / Cb[ib0])) * d <= 0: d = 0
            if d and atrm is not None:
                if atrm[i] is None: d = 0
                elif g["volat"] == "bassa" and A[i] > 0.8 * atrm[i]: d = 0
                elif g["volat"] == "alta" and A[i] < 1.2 * atrm[i]: d = 0
            if not d: i += 1; continue
            e = C[i]; rischio = g["stop"] * A[i]; pct = rischio / e
            if pct < 0.002 or pct > 0.25: i += 1; continue
            stop = e - d * rischio; tp = e + d * g["k"] * rischio if g["uscita"] == "obiettivo" else None
            meglio = e; r = None; k = i
            while k < min(i + g["tenuta"], n - 1):
                k += 1
                if ((L[k] if d == 1 else H[k]) - stop) * d <= 0: r = (stop - e) * d / rischio; break
                if tp is not None and ((H[k] if d == 1 else L[k]) - tp) * d >= 0: r = g["k"]; break
                if g["uscita"] == "canale" and Xb[k] is not None and ((d == 1 and C[k] < Xb[k]) or (d == -1 and C[k] > Xa[k])):
                    r = (C[k] - e) * d / rischio; break
                if g["uscita"] == "trailing":
                    meglio = max(meglio, C[k]) if d == 1 else min(meglio, C[k])
                    nuovo = meglio - d * g["k"] * A[i]
                    if (nuovo - stop) * d > 0: stop = nuovo
            if r is None: r = (C[k] - e) * d / rischio
            costo = 2 * COSTO + RITARDO + SP.get(m, G2.SPREAD_DEFAULT) + FUNDING_ORA * ore * (k - i)
            ops.append((T[i] + ore * 3600, T[k] + ore * 3600, m, 0.0, pct, r - costo / pct))
            i = k + 1                                   # una posizione per moneta alla volta
    return ops

def voto(ops, D, periodo):
    giorni = {}
    for o in ops:
        if (o[0] < D.taglio) == (periodo == "prova"): giorni.setdefault(o[0] // 86400, []).append(o[5])
    v = [sum(x) / len(x) for x in giorni.values()]
    if len(v) < (MIN_GIORNI if periodo == "prova" else 10): return -9.0, len(v), 0.0
    mu = sum(v) / len(v); sd = math.sqrt(sum((x - mu) ** 2 for x in v) / len(v)) or 1e-9
    return mu / sd * math.sqrt(len(v)), len(v), mu

def chiave(g): return tuple(g[k] for k in GENI)

def evolvi(D, K, SP, monete, seme, memo):
    rng = random.Random(seme)
    def valuta(g):
        c = chiave(g)
        if c not in memo: memo[c] = voto(G1.prese(operazioni(D, K, g, SP, monete)), D, "prova")[0]
        return memo[c]
    pop = [{k: rng.choice(v) for k, v in GENI.items()} for _ in range(POP)]
    for gen in range(GENERAZIONI):
        pop.sort(key=valuta, reverse=True)
        if gen % 10 == 0 or gen == GENERAZIONI - 1:
            print(f"   seme {seme}  generazione {gen + 1:>2}: miglior voto in prova {valuta(pop[0]):+.2f}"
                  f"   (combinazioni provate {len(memo)})", flush=True)
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
    usc = {"canale": f"canale {g['X']} candele", "trailing": f"trailing {g['k']:.1f} ATR",
           "obiettivo": f"obiettivo {g['k']:.1f} R", "tempo": "solo a tempo"}[g["uscita"]]
    return (f"{g['ore']:>2}h {g['verso']} | rottura {g['N']} candele +{g['margine']:.2f} ATR | filtro {g['filtro']} | "
            f"volatilita' {g['volat']} | stop {g['stop']:.1f} ATR | uscita {usc}, max {g['tenuta']} candele").replace(".", ",")

def scheda(D, K, g, SP, monete, anni, durata):
    ops = operazioni(D, K, g, SP, monete)
    cap, calo, curva, fatte = G1.portafoglio(ops)
    vp, np_, mp = voto(fatte, D, "prova"); vv, nv, mv = voto(fatte, D, "verifica")
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
    annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
    s = "🟢" if vp > 2 and vv > 1.5 and mv > 0.05 else ("🟡" if mp > 0 and mv > 0 else "🔴")
    return s, f"{vp:>+6.1f}{vv:>+7.1f}{mp:>+8.2f}{mv:>+8.2f}{len(fatte) / durata:>8.0f}{annuo * 100:>+7.0f}%{calo * 100:>+7.0f}%{celle}"

def main():
    D = G1.Dati(); SP = G2.spread()
    monete = ["XBT"] + sorted(sorted((m for m in D.uno if m != "XBT"), key=lambda m: SP.get(m, 1))[:12])
    K = Cache(D, monete)
    anni = list(range(time.gmtime(D.t0).tm_year, time.gmtime(D.t1).tm_year + 1))
    durata = (D.t1 - D.t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nMonete: {' '.join(monete)}. Dal {d(D.t0)} al {d(D.t1)}; l'algoritmo vede solo la prova (fino al {d(D.taglio)}).\n")
    memo, finali = {}, []
    for seme in SEMI:
        finali += evolvi(D, K, SP, monete, seme, memo)
    print(f"\n   combinazioni provate in tutto: {len(memo)}\n")
    print("MIGLIORE DI OGNI CORSA")
    for seme, i in zip(SEMI, range(0, len(finali), POP)):
        print(f"   seme {seme}: {descrivi(finali[i])}")
    viste, migliori = set(), []
    for g in sorted(finali, key=lambda g: memo[chiave(g)], reverse=True):
        if chiave(g) not in viste:
            viste.add(chiave(g)); migliori.append(g)
        if len(migliori) == 10: break
    # per confronto: il bot giornaliero attuale (canale 55/20, solo long)
    attuale = {"ore": 24, "verso": "long", "N": 55, "margine": 0.0, "filtro": "nessuno", "volat": "qualsiasi",
               "stop": 6.0, "uscita": "canale", "X": 20, "k": 1.0, "tenuta": 500}
    print("\nLE 10 MIGLIORI (scelte guardando solo la prova) + il bot giornaliero attuale come confronto")
    print("Annuo, calo e anni: rischio 0,5 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.\n")
    print(f"   {'Voto prova':>8}{'verif.':>7}{'R prova':>8}{'R verif':>8}{'Oper./a':>8}{'Annuo':>8}{'Calo':>8}" + "".join(f"{a:>7}" for a in anni))
    for n, g in enumerate(migliori + [attuale], 1):
        s, riga = scheda(D, K, g, SP, monete, anni, durata)
        print(f"{n:>2}. {descrivi(g)}{'   <- BOT ATTUALE (canale 55/20)' if g is attuale else ''}")
        print(f"{s} {riga}")
    g0 = migliori[0]
    print("\nPARAMETRI VICINI ALLA MIGLIORE")
    print(f"   {'Cambio':26}{'Voto prova':>11}{'Voto verif.':>12}{'R verif':>9}")
    for k, valori in GENI.items():
        i = valori.index(g0[k])
        for j in (i - 1, i + 1):
            if not 0 <= j < len(valori): continue
            g = dict(g0); g[k] = valori[j]
            f = G1.prese(operazioni(D, K, g, SP, monete))
            vp = voto(f, D, "prova")[0]; vv, _, mv = voto(f, D, "verifica")
            print(f"   {k + ' = ' + str(valori[j]):26}{vp:>+11.1f}{vv:>+12.1f}{mv:>+9.2f}")
    print("""
Voto: costanza del risultato giorno per giorno (sopra +2 = netto, sotto +1 = probabilmente fortuna).
R: risultato medio in multipli del rischio, costi e spread inclusi.   Oper./a: operazioni prese all'anno.
🟢 netto in prova E in verifica   🟡 positivo in entrambi ma non netto   🔴 negativo in verifica""")

if __name__ == "__main__":
    main()
