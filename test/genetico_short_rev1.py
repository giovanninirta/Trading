#!/usr/bin/env python3
"""
ALGORITMO GENETICO "BTC GUIDA AL RIBASSO" (SHORT) - Rev 1
Stessi 18 geni e stesso metodo di genetico_cecchino_rev1.py, ma a specchio per gli short:
  segnale   candela di BTC in DISCESA oltre btc_atr ATR (tipo atr) o oltre btc_pct % (tipo pct)
  monete    scese oltre "moneta" ATR nella stessa candela; si vendono le piu' deboli (dalla 1a/2a/3a)
  rsi       anti-estensione: si scartano le monete con RSI SOTTO 100 - rsi (es. rsi 75 -> scarta RSI < 25)
  regime    BTC SOTTO la sua media (con tolleranza: sotto media x (1 + toll))
  uscita    a specchio: stop sopra, pareggio, trailing dal minimo, fase 1 a tempo, fase 2 che si allarga
Costi come i long (funding pagato anche dagli short, per prudenza).
Punto di partenza nella popolazione: lo "specchio di Cecchino".

CRITERIO (fissato prima). La migliore (voto in prova sulle 12 liquide) e' PROMOSSA se:
  sulle 17 NUOVE: netto > +0,05 R, netto senza le 10 migliori > 0, annuo > 0, calo >= -20 %,
                  e netto almeno +0,05 R sopra il controllo "short in momenti e monete a caso" (stessa uscita, 20 estrazioni)
  nella VERIFICA delle 12 liquide: netto > 0
Uso (nella cartella dati):  python ../genetico_short_rev1.py
"""
import bisect, math, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, COSTO, FUNDING_ORA
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from verifica_monete_nuove_btc_guida_rev1 import LIQUIDE12, NUOVE
import genetico_cecchino_rev1 as G

SPECCHIO = dict(G.CECCHINO)
G.CECCHINO = SPECCHIO                       # punto di partenza della popolazione
GENI, RISCHIO, LEVA, RITARDO, TETTO = G.GENI, G.RISCHIO, G.LEVA, G.RITARDO, G.TETTO
media, voto, chiave = G.media, G.voto, G.chiave

USCITE = {}
def esci(M, k, e, a, chiusura, g):
    chiave_u = (M.m, k, a, g["stop"], g["pari"], g["trail"], g["f1"], g["s2"], g["allarga"])
    if chiave_u in USCITE: return USCITE[chiave_u]
    stop, mn, fase2, ultima = e + g["stop"] * a, e, False, e; Q = M.Q; res = None
    for x in range(k, min(len(Q), k + TETTO)):
        t, o, h, l, c = Q[x]
        if not fase2 and t >= chiusura + g["f1"] * 3600: res = (t, ultima); break
        if h >= stop: res = (t + 900, max(stop, o)); break
        if l < mn:
            mn = l; gg = (e - l) / a
            if not fase2 and gg >= g["s2"]: fase2 = True
            if gg >= g["pari"]:
                stop = min(stop, e, l + (g["trail"] + (g["allarga"] * (gg - g["s2"]) if fase2 else 0.0)) * a)
        ultima = c
    if res is None:
        x = min(len(Q), k + TETTO) - 1; res = (Q[x][0] + 900, Q[x][4])
    USCITE[chiave_u] = res
    return res

def simula(g, btc, monete, t_da, t_a, momenti=None, rng=None):
    """momenti/rng: controllo a caso (ingressi nei momenti dati, monete a caso)."""
    T, H, L, C, A, _, _ = btc.serie(g["ore"], g["atr_p"]); D = g["ore"] * 3600
    sma = None
    if g["regime"] and momenti is None:
        n = g["sma"]; sma = [None] * len(C); acc = 0.0
        for i, x in enumerate(C):
            acc += x
            if i >= n: acc -= C[i - n]
            if i >= n - 1: sma[i] = acc / n
    cap, picco, calo, aperte, ops, curva = 1.0, 1.0, 0.0, [], [], []
    indici = momenti if momenti is not None else range(max(bisect.bisect_left(T, t_da), 30), len(C))
    for i in indici:
        t = T[i]
        if t > t_a: break
        if t < t_da or not A[i - 1]: continue
        if momenti is None:
            if g["tipo"] == "atr":
                if (C[i] - C[i - 1]) / A[i - 1] >= -g["btc_atr"]: continue
            elif C[i] / C[i - 1] - 1 >= -g["btc_pct"] / 100: continue
            if g["regime"] and not (sma[i] and C[i] < sma[i] * (1 + g["toll"])): continue
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
            if momenti is None:
                if z >= -g["moneta"]: continue
                if g["rsi"] is not None and (R[j] is None or R[j] < 100 - g["rsi"]): continue
            scelte.append((z, M, j))
        if momenti is None: scelte = sorted(scelte, key=lambda x: x[0])[g["salta"]:]
        else: rng.shuffle(scelte); scelte = scelte[:g["maxpos"]]
        for z, M, j in scelte:
            if len(aperte) >= g["maxpos"] or any(p[0] == M.m for p in aperte): continue
            _, _, _, Cm, Am, _, _ = M.serie(g["ore"], g["atr_p"])
            e, a = Cm[j], Am[j]; pct = g["stop"] * a / e
            if not 0.002 <= pct <= 0.10: continue
            k = bisect.bisect_left(M.QT, chiusura)
            if k >= len(M.Q) - 1 or M.QT[k] - chiusura > 3600: continue
            importo = cap * RISCHIO; noz = importo / pct
            if sum(p[3] for p in aperte) + noz > LEVA * cap: continue
            fine, px = esci(M, k, e, a, chiusura, g)
            lordo = (e - px) / (g["stop"] * a); ore = (fine - chiusura) / 3600
            netto = lordo - (2 * COSTO + M.sp + RITARDO + FUNDING_ORA * ore) / pct
            aperte.append((M.m, fine, importo, noz, netto)); ops.append((chiusura, M.m, lordo, netto, fine, pct))
    for p in sorted(aperte, key=lambda p: p[1]):
        cap += p[2] * p[4]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p[1], cap))
    return ops, cap, calo, curva

def descrivi(g):
    s = (f"{'BTC <-' + str(g['btc_atr']) + ' ATR' if g['tipo'] == 'atr' else 'BTC <-' + str(g['btc_pct']) + ' %'} | {g['ore']}h | ATR{g['atr_p']} | "
         f"moneta <-{g['moneta']} | max {g['maxpos']} | dalla {g['salta'] + 1}a piu' debole | RSI min {100 - g['rsi'] if g['rsi'] else '-'} | "
         f"stop {g['stop']} | pari {g['pari']} | trail {g['trail']} | f1 {g['f1']}h | fase2 {g['s2']} | allarga {g['allarga']} | "
         f"{'BTC sotto media ' + str(g['sma']) + ' +' + str(int(g['toll'] * 100)) + '%' if g['regime'] else 'senza regime'}")
    return s.replace(".", ",")

def main():
    inizio = time.time(); SP = spread(); gruppi = {}
    for nome, lista in (("12", LIQUIDE12), ("17", NUOVE)):
        gruppi[nome] = []
        for m in lista:
            b = carica(m, 1)
            if not b or len(b) < 5000: continue
            q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
            if len(q) >= 20000: gruppi[nome].append(G.Moneta(m, b, q, SP.get(m, SPREAD_DEFAULT)))
    btc = G.Moneta("XBT", carica("XBT", 1), [], 0)
    liq = gruppi["12"]
    t0 = max(max(M.uno[0][0], M.Q[0][0]) for M in liq) + 40 * 86400; t1 = min(min(M.uno[-1][0], M.Q[-1][0]) for M in liq) - 3 * 86400
    taglio = t0 + (t1 - t0) * 0.6
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nSHORT. {len(liq)} liquide + {len(gruppi['17'])} nuove, dal {d(t0)} al {d(t1)}. L'algoritmo vede solo la prova fino al {d(taglio)}.\n")
    memo = {}
    def valuta(g):
        c = chiave(g)
        if c not in memo:
            ops, cap, calo, _ = simula(g, btc, liq, t0, taglio)
            memo[c] = voto(ops, calo)
        return memo[c]
    finali = []
    for seme in G.SEMI:
        pop = G.evolvi(seme, valuta); finali += pop[:5]
        print(f"   seme {seme}: {descrivi(pop[0])}   [{len(memo)} combinazioni, {(time.time() - inizio) / 60:.0f} min]\n", flush=True)
    unici = {}
    for g in finali: unici[chiave(g)] = g
    migliori = sorted(unici.values(), key=valuta, reverse=True)[:8]

    def misura(ops, cap, calo, anni_p):
        net = sorted(o[3] for o in ops)
        return dict(n=len(ops) / anni_p, netto=media(net), s10=media(net[:-10]), annuo=(cap ** (1 / anni_p) - 1) if cap > 0 else -1, calo=calo)
    def scheda(g):
        out = {}
        for nome, gr, da, a in (("prova12", liq, t0, taglio), ("verif12", liq, taglio, t1), ("nuove17", gruppi["17"], t0, t1)):
            ops, cap, calo, _ = simula(g, btc, gr, da, a); out[nome] = misura(ops, cap, calo, (a - da) / (365 * 86400))
        return out
    def stampa(nome, g):
        s = scheda(g); p, v, n = s["prova12"], s["verif12"], s["nuove17"]
        print((f"   {nome:<10}{valuta(g):>+6.2f} | {p['n']:>5.0f}{p['netto']:>+8.3f}{p['annuo'] * 100:>+7.1f}%{p['calo'] * 100:>+6.0f}%      | "
               f"{v['netto']:>+8.3f}{v['annuo'] * 100:>+8.1f}%{v['calo'] * 100:>+7.0f}%        | {n['n']:>5.0f}{n['netto']:>+8.3f}{n['s10']:>+8.3f}"
               f"{n['annuo'] * 100:>+8.1f}%{n['calo'] * 100:>+7.0f}%").replace(".", ","))
        print(f"      {descrivi(g)}")
        return s
    print("=== LE MIGLIORI (voto in prova) e lo SPECCHIO DI CECCHINO ===")
    print(f"   {'':<10}{'voto':>6} | {'prova 12: op/a netto annuo calo':^34} | {'verifica 12: netto annuo calo':^31} | {'17 nuove: op/a netto -top10 annuo calo':^43}")
    stampa("SPECCHIO", SPECCHIO)
    schede = [(g, stampa(f"n. {k + 1}", g)) for k, g in enumerate(migliori)]
    g, s = schede[0]
    # controllo a caso sulle 17 nuove con i parametri della migliore
    T = btc.serie(g["ore"], g["atr_p"])[0]
    validi = [i for i in range(31, len(T)) if t0 <= T[i] <= t1]
    n_ev = max(1, round(s["nuove17"]["n"] * (t1 - t0) / (365 * 86400) / max(1, g["maxpos"]) * 1.5))
    controlli = []
    for seme in range(20):
        rng = random.Random(seme)
        momenti = sorted(rng.sample(validi, min(len(validi), n_ev)))
        ops, cap, calo, _ = simula(g, btc, gruppi["17"], t0, t1, momenti, rng)
        controlli.append(misura(ops, cap, calo, (t1 - t0) / (365 * 86400)))
    cc = {k: media([x[k] for x in controlli]) for k in ("n", "netto", "s10", "annuo", "calo")}
    print((f"\n   controllo 17 nuove, short in momenti e monete a caso (parametri d'uscita della n. 1, 20 estrazioni): "
           f"{cc['n']:.0f} op/a, netto {cc['netto']:+.3f} R, senza 10 {cc['s10']:+.3f}, annuo {cc['annuo'] * 100:+.1f} %, calo {cc['calo'] * 100:.0f} %").replace(".", ","))
    n, v = s["nuove17"], s["verif12"]
    ok = (n["netto"] > 0.05 and n["s10"] > 0 and n["annuo"] > 0 and n["calo"] >= -0.20 and n["netto"] >= cc["netto"] + 0.05 and v["netto"] > 0)
    print((f"\n=== VERDETTO n. 1: 17 nuove netto {n['netto']:+.3f} (> +0,05), senza 10 {n['s10']:+.3f} (> 0), annuo {n['annuo'] * 100:+.1f} % (> 0), "
           f"calo {n['calo'] * 100:.0f} % (>= -20), controllo a caso {cc['netto']:+.3f} (serve +0,05 in piu'); verifica 12 netto {v['netto']:+.3f} (> 0) -> "
           f"{'PROMOSSA' if ok else 'BOCCIATA'} ===").replace(".", ","))
    print(f"Tempo totale {(time.time() - inizio) / 60:.0f} minuti.")

if __name__ == "__main__":
    main()
