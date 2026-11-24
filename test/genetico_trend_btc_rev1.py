#!/usr/bin/env python3
"""
ALGORITMO GENETICO "TREND CONTRO BTC" - Rev 1  (spot, coppie moneta/BTC, tutto misurato in BTC)
Il capitale sta in BTC. Per ogni moneta si guarda il grafico moneta/BTC (quanto vale la moneta in BTC):
quando quel grafico e' in trend al rialzo si cambia una quota dei BTC nella moneta, quando il trend finisce
si torna in BTC. Obiettivo: finire con piu' BTC che tenendoli fermi.
Monete: le 12 liquide (AAVE ADA DOGE DOT ETH LINK LTC NEAR SOL TRX UNI XRP).

Geni:
  ore       durata della candela: 4, 8, 12, 24, 48 ore
  N         ingresso: la chiusura moneta/BTC supera il massimo delle ultime N candele (10 - 200)
  uscita    CANALE   chiude sotto il minimo delle ultime X candele (5 - 60)
            TRAILING chiude sotto il massimo raggiunto meno k volte l'oscillazione media (1 - 6)
  media     filtro: solo se moneta/BTC sta sopra la sua media di M candele (0 = nessun filtro; 50 - 300)
  regime    sempre / solo se BTC (in dollari) e' sopra la sua media 200 / solo se e' sotto
  quote     numero di posizioni possibili: ogni moneta in trend riceve 1/K del capitale (2 - 8); senza leva
Oscillazione media = media delle variazioni assolute delle ultime 14 chiusure (moneta/BTC).
Costi: 0,25 % per ordine (spot, ordine limite) + 0,10 % di spread a ogni andata e ritorno.

Voto (solo sulla PROVA, primo 60 %): rapporto rendimento/oscillazione (Sharpe) dei rendimenti in BTC del
portafoglio, candela per candela. La VERIFICA (ultimo 40 %) si guarda solo alla fine.
Poi: prova a passo fine di ogni parametro intorno alla migliore, e confronto con costi 0,40 %.
Uso (nella cartella dati):  python ../genetico_trend_btc_rev1.py
Solo libreria standard Python 3.8+.
"""
import calendar, math, os, random, sys, time
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1

MONETE = ["AAVE", "ADA", "DOGE", "DOT", "ETH", "LINK", "LTC", "NEAR", "SOL", "TRX", "UNI", "XRP"]
GENI = {
    "ore":    [4, 8, 12, 24, 48],
    "N":      [10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 100, 120, 150, 200],
    "uscita": ["canale", "trailing"],
    "X":      [5, 10, 15, 20, 25, 30, 40, 50, 60],
    "k":      [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0],
    "media":  [0, 50, 100, 150, 200, 300],
    "regime": ["sempre", "btc sopra", "btc sotto"],
    "quote":  [2, 3, 4, 5, 6, 8],
}
COSTO, SPREAD = 0.0025, 0.001
POP, GENERAZIONI, ELITE, SEMI = 60, 30, 4, (1, 2)

def mobile(v, n, alto):
    out, d = [None] * len(v), deque()
    for i in range(1, len(v)):
        x = v[i - 1]
        if x is not None:
            while d and ((v[d[-1]] <= x) if alto else (v[d[-1]] >= x)): d.pop()
            d.append(i - 1)
        while d and d[0] < i - n: d.popleft()
        if i >= n and d and v[i - n] is not None: out[i] = v[d[0]]
    return out

class Dati:
    def __init__(self):
        self.D = G1.Dati(); self.c = {}
        self.taglio = self.D.taglio
    def serie(self, ore):
        if ore not in self.c:
            if ore <= 12: S = self.D.serie(ore)
            else:
                S = {}
                for m, b in self.D.uno.items():
                    bb = G1.aggrega(b, ore)
                    S[m] = ([x[0] for x in bb], None, None, [x[4] for x in bb], None, None, {x[0]: i for i, x in enumerate(bb)})
            Tb, Cb = S["XBT"][0], S["XBT"][3]
            mb = [None] * len(Cb); acc = 0.0
            for i in range(len(Cb)):
                acc += Cb[i]
                if i >= 200: acc -= Cb[i - 200]
                if i >= 199: mb[i] = acc / 200
            R = {}
            for m in MONETE:
                T, C, idx = S[m][0], S[m][3], S[m][6]
                v = []
                for t, cb in zip(Tb, Cb):
                    j = idx.get(t); v.append(C[j] / cb if j is not None else None)
                osc = [None] * len(v); s = deque()
                for i in range(1, len(v)):
                    if v[i] is not None and v[i - 1] is not None: s.append(abs(v[i] - v[i - 1]))
                    if len(s) > 14: s.popleft()
                    if len(s) == 14: osc[i] = sum(s) / 14
                R[m] = (v, osc)
            self.c[ore] = {"T": Tb, "btc": Cb, "mb": mb, "R": R, "mob": {}}
        return self.c[ore]
    def mob(self, ore, m, n, alto):
        S = self.serie(ore); k = (m, n, alto)
        if k not in S["mob"]:
            v = S["R"][m][0]
            if alto == "media":
                out, acc, cnt = [None] * len(v), deque(), 0.0
                for i, x in enumerate(v):
                    if x is None: acc.clear(); cnt = 0.0; continue
                    acc.append(x); cnt += x
                    if len(acc) > n: cnt -= acc.popleft()
                    if len(acc) == n: out[i] = cnt / n
                S["mob"][k] = out
            else: S["mob"][k] = mobile(v, n, alto)
        return S["mob"][k]

def simula(X, g, costo=COSTO):
    """Ritorna (tempi, rendimento del portafoglio in BTC per candela, operazioni)."""
    ore = g["ore"]; S = X.serie(ore); T, Cb, mb = S["T"], S["btc"], S["mb"]; n = len(T)
    stati = {}
    for m in MONETE:
        v, osc = S["R"][m]
        alto = X.mob(ore, m, g["N"], True)
        basso = X.mob(ore, m, g["X"], False) if g["uscita"] == "canale" else None
        med = X.mob(ore, m, g["media"], "media") if g["media"] else None
        st = [0] * n; dentro, massimo = 0, 0.0
        for i in range(n):
            x = v[i]
            if x is None: dentro = 0; continue
            if not dentro:
                ok = alto[i] is not None and x > alto[i]
                if ok and med is not None: ok = med[i] is not None and x > med[i]
                if ok and g["regime"] != "sempre":
                    ok = mb[i] is not None and ((Cb[i] > mb[i]) == (g["regime"] == "btc sopra"))
                if ok: dentro, massimo = 1, x
            else:
                massimo = max(massimo, x)
                if g["uscita"] == "canale":
                    if basso[i] is not None and x < basso[i]: dentro = 0
                elif osc[i] is not None and x < massimo - g["k"] * osc[i]: dentro = 0
            st[i] = dentro
        stati[m] = st
    K = g["quote"]; tenute = []; rend = [0.0] * n; ops = []; aperte = {}
    for i in range(1, n):
        r = 0.0
        for m in tenute:
            v = S["R"][m][0]
            if v[i] is not None and v[i - 1] is not None: r += (v[i] / v[i - 1] - 1) / K
        # uscite e ingressi alla chiusura della candela i (pagano il costo)
        costi = 0.0
        for m in list(tenute):
            if stati[m][i] == 0:
                tenute.remove(m); costi += (costo + SPREAD / 2) / K
                e_i, e_v = aperte.pop(m); v = S["R"][m][0]
                ops.append((T[e_i], T[i], m, (v[i] / e_v - 1) - 2 * (costo + SPREAD / 2)))
        for m in MONETE:
            if len(tenute) >= K: break
            if m not in tenute and stati[m][i] == 1 and stati[m][i - 1] == 0:
                tenute.append(m); costi += (costo + SPREAD / 2) / K; aperte[m] = (i, S["R"][m][0][i])
        rend[i] = r - costi
    return T, rend, ops

def statistiche(T, rend, ore, a, b):
    seg = rend[a:b]
    if len(seg) < 50: return -9, 0, 0
    mu = sum(seg) / len(seg); sd = math.sqrt(sum((x - mu) ** 2 for x in seg) / len(seg)) or 1e-9
    per_anno = 365 * 24 / ore
    sharpe = mu / sd * math.sqrt(per_anno)
    eq, picco, calo = 1.0, 1.0, 0.0
    for x in seg:
        eq *= 1 + x; picco = max(picco, eq); calo = min(calo, eq / picco - 1)
    anni = len(seg) / per_anno
    return sharpe, eq ** (1 / anni) - 1, calo

def chiave(g): return tuple(g[k] for k in GENI)

def valuta(X, g, memo):
    c = chiave(g)
    if c not in memo:
        T, rend, _ = simula(X, g)
        i_t = next(i for i, t in enumerate(T) if t >= X.taglio)
        memo[c] = statistiche(T, rend, g["ore"], 210, i_t)[0]
    return memo[c]

def evolvi(X, seme, memo):
    rng = random.Random(seme)
    pop = [{k: rng.choice(v) for k, v in GENI.items()} for _ in range(POP)]
    for gen in range(GENERAZIONI):
        pop.sort(key=lambda g: valuta(X, g, memo), reverse=True)
        if gen % 10 == 0 or gen == GENERAZIONI - 1:
            print(f"   seme {seme}  generazione {gen + 1:>2}: miglior voto in prova {valuta(X, pop[0], memo):+.2f}"
                  f"   (combinazioni provate {len(memo)})", flush=True)
        nuova = [dict(x) for x in pop[:ELITE]]
        while len(nuova) < POP:
            a = max(rng.sample(pop, 3), key=lambda g: valuta(X, g, memo)); b = max(rng.sample(pop, 3), key=lambda g: valuta(X, g, memo))
            f = {k: (a[k] if rng.random() < 0.5 else b[k]) for k in GENI}
            for k, valori in GENI.items():
                if rng.random() < 0.15:
                    i = valori.index(f[k])
                    f[k] = valori[max(0, min(len(valori) - 1, i + rng.choice((-2, -1, 1, 2))))] if rng.random() < 0.7 else rng.choice(valori)
            nuova.append(f)
        pop = nuova
    return sorted(pop, key=lambda g: valuta(X, g, memo), reverse=True)

def descrivi(g):
    usc = f"canale {g['X']}" if g["uscita"] == "canale" else f"trailing {g['k']}"
    return (f"{g['ore']:>2}h | ingresso {g['N']} candele | uscita {usc} | media {g['media'] or '-'} | "
            f"{g['regime']} | {g['quote']} quote").replace(".", ",")

def scheda(X, g, costo=COSTO):
    T, rend, ops = simula(X, g, costo)
    i_t = next(i for i, t in enumerate(T) if t >= X.taglio)
    sp, ap, cp = statistiche(T, rend, g["ore"], 210, i_t)
    sv, av, cv = statistiche(T, rend, g["ore"], i_t, len(T))
    st, at, ct = statistiche(T, rend, g["ore"], 210, len(T))
    rr = sorted(o[3] for o in ops)
    senza = sum(rr[:-10]) if len(rr) > 10 else 0
    eq, anni = 1.0, {}
    for t, x in zip(T, rend):
        a = time.gmtime(t).tm_year; anni.setdefault(a, 1.0); anni[a] *= 1 + x
    celle = "".join(f"{(anni[a] - 1) * 100:>+6.0f}%" for a in sorted(anni))
    durata = (T[-1] - T[210]) / (365 * 86400)
    s = "🟢" if ap > 0 and av > 0 and senza > 0 else ("🟡" if ap > 0 and av > 0 else "🔴")
    return s, f"{sp:>+6.2f}{sv:>+7.2f}{ap * 100:>+8.1f}%{av * 100:>+8.1f}%{at * 100:>+8.1f}%{ct * 100:>+7.0f}%{len(ops) / durata:>7.0f}{senza * 100 / g['quote']:>+9.0f}%{celle}", sorted(anni)

def main():
    X = Dati()
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nTutto in BTC (0 % = come tenere BTC). Monete: {' '.join(MONETE)}.")
    print(f"Prova fino al {d(X.taglio)}, poi verifica. Costi 0,25 % per ordine + 0,10 % di spread.\n")
    memo, finali = {}, []
    for seme in SEMI: finali += evolvi(X, seme, memo)
    print(f"\n   combinazioni provate in tutto: {len(memo)}\n")
    print("MIGLIORE DI OGNI CORSA")
    for seme, i in zip(SEMI, range(0, len(finali), POP)): print(f"   seme {seme}: {descrivi(finali[i])}")
    viste, migliori = set(), []
    for g in sorted(finali, key=lambda g: memo[chiave(g)], reverse=True):
        if chiave(g) not in viste: viste.add(chiave(g)); migliori.append(g)
        if len(migliori) == 8: break
    rif = {"ore": 24, "N": 55, "uscita": "canale", "X": 20, "k": 2.0, "media": 0, "regime": "sempre", "quote": 5}
    testa = None
    print("\nLE 8 MIGLIORI (scelte guardando solo la prova) + un trend classico 55/20 giornaliero come confronto\n")
    for n, g in enumerate(migliori + [rif], 1):
        s, riga, anni = scheda(X, g)
        if testa is None:
            testa = f"   {'Sharpe P':>8}{'Sh. V':>7}{'BTC/a P':>9}{'BTC/a V':>9}{'BTC/a':>9}{'Calo':>7}{'Op./a':>7}{'senza10':>9}" + "".join(f"{a:>7}" for a in anni)
            print(testa)
        print(f"{n:>2}. {descrivi(g)}{'   <- trend classico 55/20' if g is rif else ''}")
        print(f"{s} {riga}")
    g0 = migliori[0]
    print("\nCOSTI PIU' ALTI (0,40 % per ordine, ordine a mercato) sulla migliore")
    print(testa); s, riga, _ = scheda(X, g0, 0.004); print(f"{s} {riga}")
    print("\nPASSO FINE INTORNO ALLA MIGLIORE (un parametro alla volta)")
    fini = {"N": range(max(5, g0["N"] - 20), g0["N"] + 21, 2), "X": range(max(3, g0["X"] - 10), g0["X"] + 11, 1),
            "k": [round(max(0.5, g0["k"] - 1.5) + 0.25 * i, 2) for i in range(13)],
            "media": [0] + list(range(max(10, g0["media"] - 60), g0["media"] + 61, 10)) if g0["media"] else [0, 50, 100, 150, 200],
            "quote": range(2, 10), "ore": [4, 6, 8, 12, 16, 24, 36, 48]}
    for k, valori in fini.items():
        if k == "X" and g0["uscita"] != "canale": continue
        if k == "k" and g0["uscita"] != "trailing": continue
        print(f"\n   {k}\n{testa}")
        for v in valori:
            g = dict(g0); g[k] = v
            if k == "ore" and v not in X.c and v not in (4, 8, 12, 24, 48):
                if v > 12: pass
            try:
                s, riga, _ = scheda(X, g)
            except Exception as e:
                print(f"   {v}: non calcolabile ({e})"); continue
            print(f"{s} {str(v):>6}{riga[3:] if False else riga}{'   <-' if v == g0[k] else ''}")
    print("""
Sharpe P / V: rapporto rendimento/oscillazione in prova e in verifica (sopra 1 = buono, sotto 0,5 = debole).
BTC/a: BTC guadagnati all'anno rispetto a tenerli fermi (P prova, V verifica, poi tutto il periodo). Calo: peggior discesa in BTC.
Op./a: operazioni all'anno.  senza10: risultato totale togliendo le 10 operazioni migliori (in % del capitale, circa).
🟢 guadagna BTC in prova e verifica e anche senza le 10 migliori   🟡 guadagna ma dipende da pochi colpi   🔴 perde BTC""")

if __name__ == "__main__":
    main()
