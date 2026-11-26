#!/usr/bin/env python3
"""
ALGORITMO GENETICO "CECCHINO" - Rev 1  (perpetui Kraken, solo long, uscita sui 15 min)
Ottimizza INSIEME tutti i parametri della regola BTC guida (richiesta dell'utente).

GENI (intervallo e passo)                                   Cecchino attuale
  tipo      soglia BTC in ATR o in %                         atr
  btc_atr   1,0 - 3,0 passo 0,25                             2,0
  btc_pct   0,75 - 2,5 % passo 0,25                          (Segugio 1,25)
  ore       durata candela 4 / 6 / 8 ore                     4
  atr_p     periodo ATR 10 - 20 passo 2                      14
  moneta    soglia moneta 1,0 - 2,5 ATR passo 0,1            1,7
  maxpos    monete per scatto / posizioni max 3 - 8          5
  salta     quali prendere: dalla 1a / 2a / 3a piu' forte    dalla 1a
  rsi       filtro anti-estensione: nessuno, RSI max 70-90 passo 5      nessuno
  stop      stop iniziale 0,6 - 1,6 ATR passo 0,1            1,0
  pari      pareggio a +0,5 - 2,0 ATR passo 0,25             1,0
  trail     distanza trailing 1,0 - 2,5 ATR passo 0,25       1,5
  f1        ore massime in fase 1: 8 - 32 passo 4            16
  s2        soglia fase 2: 2,0 - 5,0 ATR passo 0,5           3,0
  allarga   allargamento in fase 2: 0 - 0,30 passo 0,05      0,10
  regime    filtro BTC sopra la media: si / no               no
  sma       periodo media (candele) 20 - 200 passo 10        -
  toll      tolleranza sotto la media 0 - 5 % passo 1        -
FISSI: rischio 0,75 %, leva 3, ingresso alla chiusura della candela (+0,05 % ritardo), costi 0,07 % x2 + spread reale
       + funding; universo di ottimizzazione = 12 liquide.

CONTRO L'ECCESSO DI ADATTAMENTO (fissato prima):
  - l'algoritmo vede SOLO la prova (primo 60 %) sulle 12 liquide
  - voto = R netto medio SENZA le 10 migliori / sua deviazione x radice del numero (operazioni prese dal portafoglio);
    servono almeno 60 operazioni in prova; calo in prova peggiore di -20 % = scartata
  - 3 corse con semi diversi; prova dei parametri vicini (ogni gene di un passo in piu' e in meno)
  - VERDETTO: la migliore deve battere Cecchino attuale (stessa simulazione) nella VERIFICA delle 12 liquide (netto)
    e sulle 17 NUOVE (annuo), con calo sulle 17 nuove >= -20 % e netto senza le 10 migliori > 0 sulle 17 nuove.
Uso (nella cartella dati):  python ../genetico_cecchino_rev1.py
"""
import bisect, math, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, atr, COSTO, FUNDING_ORA
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from verifica_monete_nuove_btc_guida_rev1 import LIQUIDE12, NUOVE

def passi(a, b, p): return [round(a + p * k, 4) for k in range(int(round((b - a) / p)) + 1)]
GENI = {
    "tipo": ["atr", "pct"], "btc_atr": passi(1.0, 3.0, 0.25), "btc_pct": passi(0.75, 2.5, 0.25), "ore": [4, 6, 8],
    "atr_p": passi(10, 20, 2), "moneta": passi(1.0, 2.5, 0.1), "maxpos": [3, 4, 5, 6, 7, 8], "salta": [0, 1, 2],
    "rsi": [None, 70, 75, 80, 85, 90], "stop": passi(0.6, 1.6, 0.1), "pari": passi(0.5, 2.0, 0.25),
    "trail": passi(1.0, 2.5, 0.25), "f1": passi(8, 32, 4), "s2": passi(2.0, 5.0, 0.5), "allarga": passi(0.0, 0.30, 0.05),
    "regime": [False, True], "sma": passi(20, 200, 10), "toll": passi(0.0, 0.05, 0.01),
}
CECCHINO = dict(tipo="atr", btc_atr=2.0, btc_pct=1.25, ore=4, atr_p=14, moneta=1.7, maxpos=5, salta=0, rsi=None, stop=1.0,
                pari=1.0, trail=1.5, f1=16, s2=3.0, allarga=0.10, regime=False, sma=50, toll=0.0)
RISCHIO, LEVA, RITARDO, TETTO = 0.0075, 3.0, 0.0005, 60 * 96
POP, GEN, ELITE, SEMI, MIN_OP = 60, 35, 4, (1, 2, 3), 60

def aggrega(barre, ore):
    out, g, L = [], [], ore * 3600
    for b in barre:
        if g and g[0][0] // L != b[0] // L:
            if len(g) == ore: out.append((g[0][0] // L * L, max(x[2] for x in g), min(x[3] for x in g), g[-1][4]))
            g = []
        g.append(b)
    return out

def rsi(C, n=14):
    out, ag, al = [None] * len(C), None, None
    for i in range(1, len(C)):
        d = C[i] - C[i - 1]; g, l = max(d, 0), max(-d, 0)
        if ag is None: ag, al = g, l
        else: ag = (ag * (n - 1) + g) / n; al = (al * (n - 1) + l) / n
        if i >= n: out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out

class Moneta:
    def __init__(self, m, uno, q, sp):
        self.m, self.uno, self.Q, self.sp = m, uno, q, sp
        self.QT = [x[0] for x in q]; self.cache = {}
    def serie(self, ore, atr_p):
        k = (ore, atr_p)
        if k not in self.cache:
            b = self.cache.get(("b", ore)) or aggrega(self.uno, ore); self.cache[("b", ore)] = b
            T = [x[0] for x in b]; H = [x[1] for x in b]; L = [x[2] for x in b]; C = [x[3] for x in b]
            if ("r", ore) not in self.cache: self.cache[("r", ore)] = rsi(C)
            self.cache[k] = (T, H, L, C, atr(H, L, C, atr_p), {t: i for i, t in enumerate(T)}, self.cache[("r", ore)])
        return self.cache[k]

USCITE = {}
def esci(M, k, e, a, chiusura, g):
    chiave = (M.m, k, a, g["stop"], g["pari"], g["trail"], g["f1"], g["s2"], g["allarga"])
    if chiave in USCITE: return USCITE[chiave]
    stop, mx, fase2, ultima = e - g["stop"] * a, e, False, e; Q = M.Q; res = None
    for x in range(k, min(len(Q), k + TETTO)):
        t, o, h, l, c = Q[x]
        if not fase2 and t >= chiusura + g["f1"] * 3600: res = (t, ultima); break
        if l <= stop: res = (t + 900, min(stop, o)); break
        if h > mx:
            mx = h; gg = (h - e) / a
            if not fase2 and gg >= g["s2"]: fase2 = True
            if gg >= g["pari"]:
                stop = max(stop, e, h - (g["trail"] + (g["allarga"] * (gg - g["s2"]) if fase2 else 0.0)) * a)
        ultima = c
    if res is None:
        x = min(len(Q), k + TETTO) - 1; res = (Q[x][0] + 900, Q[x][4])
    USCITE[chiave] = res
    return res

def simula(g, btc, monete, t_da, t_a):
    T, H, L, C, A, _, _ = btc.serie(g["ore"], g["atr_p"]); D = g["ore"] * 3600
    sma = None
    if g["regime"]:
        n = g["sma"]; sma = [None] * len(C); acc = 0.0
        for i, x in enumerate(C):
            acc += x
            if i >= n: acc -= C[i - n]
            if i >= n - 1: sma[i] = acc / n
    cap, picco, calo, aperte, ops, curva = 1.0, 1.0, 0.0, [], [], []
    i0 = bisect.bisect_left(T, t_da)
    for i in range(max(i0, 30), len(C)):
        t = T[i]
        if t > t_a: break
        if not A[i - 1]: continue
        if g["tipo"] == "atr":
            if (C[i] - C[i - 1]) / A[i - 1] <= g["btc_atr"]: continue
        elif C[i] / C[i - 1] - 1 <= g["btc_pct"] / 100: continue
        if g["regime"] and not (sma[i] and C[i] > sma[i] * (1 - g["toll"])): continue
        chiusura = t + D
        for p in sorted(aperte, key=lambda p: p[1]):
            if p[1] <= chiusura:
                cap += p[2] * p[4]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p[1], cap))
        aperte = [p for p in aperte if p[1] > chiusura]
        scelte = []
        for M in monete:
            Tm, Hm, Lm, Cm, Am, idx, R = M.serie(g["ore"], g["atr_p"])
            j = idx.get(t)
            if j is None or j < 30 or not Am[j - 1] or Hm[j] == Lm[j]: continue
            z = (Cm[j] - Cm[j - 1]) / Am[j - 1]
            if z <= g["moneta"]: continue
            if g["rsi"] is not None and (R[j] is None or R[j] > g["rsi"]): continue
            scelte.append((z, M, j))
        scelte.sort(key=lambda x: -x[0])
        for z, M, j in scelte[g["salta"]:]:
            if len(aperte) >= g["maxpos"] or any(p[0] == M.m for p in aperte): continue
            _, _, _, Cm, Am, _, _ = M.serie(g["ore"], g["atr_p"])
            e, a = Cm[j], Am[j]; pct = g["stop"] * a / e
            if not 0.002 <= pct <= 0.10: continue
            k = bisect.bisect_left(M.QT, chiusura)
            if k >= len(M.Q) - 1 or M.QT[k] - chiusura > 3600: continue
            importo = cap * RISCHIO; noz = importo / pct
            if sum(p[3] for p in aperte) + noz > LEVA * cap: continue
            fine, px = esci(M, k, e, a, chiusura, g)
            lordo = (px - e) / (g["stop"] * a); ore = (fine - chiusura) / 3600
            netto = lordo - (2 * COSTO + M.sp + RITARDO + FUNDING_ORA * ore) / pct
            aperte.append((M.m, fine, importo, noz, netto)); ops.append((chiusura, M.m, lordo, netto))
    for p in sorted(aperte, key=lambda p: p[1]):
        cap += p[2] * p[4]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p[1], cap))
    return ops, cap, calo, curva

def media(v): return sum(v) / len(v) if v else 0.0

def voto(ops, calo):
    if len(ops) < MIN_OP: return -9.0
    if calo < -0.20: return -5.0 + calo
    v = sorted(o[3] for o in ops)[:-10]
    if len(v) < 5: return -9.0
    mu = media(v); sd = math.sqrt(sum((x - mu) ** 2 for x in v) / len(v)) or 1e-9
    return mu / sd * math.sqrt(len(v))

def chiave(g): return tuple(g[k] for k in GENI)

def evolvi(seme, valuta):
    rng = random.Random(seme)
    pop = [dict(CECCHINO)] + [{k: rng.choice(v) for k, v in GENI.items()} for _ in range(POP - 1)]
    for gen in range(GEN):
        pop.sort(key=valuta, reverse=True)
        if gen % 5 == 0 or gen == GEN - 1:
            print(f"   seme {seme} generazione {gen + 1:>2}: miglior voto {valuta(pop[0]):+.2f}", flush=True)
        nuova = [dict(x) for x in pop[:ELITE]]
        while len(nuova) < POP:
            a = max(rng.sample(pop, 3), key=valuta); b = max(rng.sample(pop, 3), key=valuta)
            f = {k: (a[k] if rng.random() < 0.5 else b[k]) for k in GENI}
            for k, vals in GENI.items():
                if rng.random() < 0.12:
                    i = vals.index(f[k])
                    f[k] = vals[max(0, min(len(vals) - 1, i + rng.choice((-2, -1, 1, 2))))] if rng.random() < 0.7 else rng.choice(vals)
            nuova.append(f)
        pop = nuova
    pop.sort(key=valuta, reverse=True)
    return pop

def descrivi(g):
    s = (f"{'BTC >' + str(g['btc_atr']) + ' ATR' if g['tipo'] == 'atr' else 'BTC >' + str(g['btc_pct']) + ' %'} | {g['ore']}h | ATR{g['atr_p']} | "
         f"moneta >{g['moneta']} | max {g['maxpos']} | dalla {g['salta'] + 1}a | RSI {g['rsi'] or '-'} | stop {g['stop']} | pari {g['pari']} | "
         f"trail {g['trail']} | f1 {g['f1']}h | fase2 {g['s2']} | allarga {g['allarga']} | "
         f"{'media ' + str(g['sma']) + ' -' + str(int(g['toll'] * 100)) + '%' if g['regime'] else 'senza regime'}")
    return s.replace(".", ",")

def main():
    inizio = time.time(); SP = spread(); gruppi = {}
    for nome, lista in (("12", LIQUIDE12), ("17", NUOVE)):
        gruppi[nome] = []
        for m in lista:
            b = carica(m, 1)
            if not b or len(b) < 5000: continue
            q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
            if len(q) >= 20000: gruppi[nome].append(Moneta(m, b, q, SP.get(m, SPREAD_DEFAULT)))
    btc = Moneta("XBT", carica("XBT", 1), [], 0)
    liq = gruppi["12"]
    t0 = max(max(M.uno[0][0], M.Q[0][0]) for M in liq) + 40 * 86400; t1 = min(min(M.uno[-1][0], M.Q[-1][0]) for M in liq) - 3 * 86400
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    combinazioni = 1
    for v in GENI.values(): combinazioni *= len(v)
    print(f"\n{len(liq)} liquide + {len(gruppi['17'])} nuove, dal {d(t0)} al {d(t1)}. L'algoritmo vede solo la prova fino al {d(taglio)}.")
    print(f"{len(GENI)} geni, {combinazioni:.1e} combinazioni possibili.\n")
    memo = {}
    def valuta(g):
        c = chiave(g)
        if c not in memo:
            ops, cap, calo, _ = simula(g, btc, liq, t0, taglio)
            memo[c] = voto(ops, calo)
        return memo[c]
    finali = []
    for seme in SEMI:
        pop = evolvi(seme, valuta); finali += pop[:5]
        print(f"   seme {seme}: {descrivi(pop[0])}   [{len(memo)} combinazioni valutate, {(time.time() - inizio) / 60:.0f} min]\n", flush=True)
    unici = {}
    for g in finali: unici[chiave(g)] = g
    migliori = sorted(unici.values(), key=valuta, reverse=True)[:8]

    def scheda(g):
        out = {}
        for nome, gr, da, a in (("prova12", liq, t0, taglio), ("verif12", liq, taglio, t1), ("tutto12", liq, t0, t1), ("nuove17", gruppi["17"], t0, t1)):
            ops, cap, calo, _ = simula(g, btc, gr, da, a)
            anni_p = (a - da) / (365 * 86400); net = sorted(o[3] for o in ops)
            out[nome] = dict(n=len(ops) / anni_p, netto=media(net), s10=media(net[:-10]), annuo=(cap ** (1 / anni_p) - 1) if cap > 0 else -1, calo=calo)
        return out
    print("=== LE MIGLIORI (voto in prova) a confronto con CECCHINO attuale ===")
    print(f"   {'':<10}{'voto':>6} | {'prova 12: op/a netto annuo calo':^34} | {'verifica 12: netto annuo calo':^31} | {'17 nuove: netto -top10 annuo calo':^38}")
    def stampa(nome, g):
        s = scheda(g); p, v, n = s["prova12"], s["verif12"], s["nuove17"]
        print((f"   {nome:<10}{valuta(g):>+6.2f} | {p['n']:>5.0f}{p['netto']:>+8.3f}{p['annuo'] * 100:>+7.1f}%{p['calo'] * 100:>+6.0f}%      | "
               f"{v['netto']:>+8.3f}{v['annuo'] * 100:>+8.1f}%{v['calo'] * 100:>+7.0f}%        | {n['netto']:>+8.3f}{n['s10']:>+8.3f}"
               f"{n['annuo'] * 100:>+8.1f}%{n['calo'] * 100:>+7.0f}%").replace(".", ","))
        print(f"      {descrivi(g)}")
        return s
    base = stampa("CECCHINO", CECCHINO)
    schede = [(g, stampa(f"n. {k + 1}", g)) for k, g in enumerate(migliori)]
    g, s = schede[0]
    print("\n=== PARAMETRI VICINI della n. 1 (ogni gene un passo in piu' e in meno): voto in prova ===")
    v0 = valuta(g); buoni = tot = 0
    for k, vals in GENI.items():
        i = vals.index(g[k]); celle = []
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                h = dict(g); h[k] = vals[j]; vv = valuta(h); tot += 1; buoni += vv >= 0.7 * v0
                celle.append(f"{vals[j]}: {vv:+.2f}")
        print(f"   {k:<8} ({g[k]}) -> " + "   ".join(celle))
    print(f"   vicini con voto almeno 70 % della n. 1: {buoni} su {tot}")
    v, n, bv, bn = s["verif12"], s["nuove17"], base["verif12"], base["nuove17"]
    ok = v["netto"] > bv["netto"] and n["annuo"] > bn["annuo"] and n["calo"] >= -0.20 and n["s10"] > 0
    print(f"\n=== VERDETTO: verifica 12 netto {v['netto']:+.3f} (Cecchino {bv['netto']:+.3f}); 17 nuove annuo {n['annuo'] * 100:+.1f} % "
          f"(Cecchino {bn['annuo'] * 100:+.1f} %), calo {n['calo'] * 100:.0f} % (>= -20), senza 10 {n['s10']:+.3f} (> 0) -> "
          f"{'BATTE CECCHINO' if ok else 'NON BATTE CECCHINO: si tiene la regola attuale'} ===".replace(".", ","))
    print(f"Tempo totale {(time.time() - inizio) / 60:.0f} minuti.")

if __name__ == "__main__":
    main()
