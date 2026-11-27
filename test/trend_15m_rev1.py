#!/usr/bin/env python3
"""
TREND 15 MINUTI CON STOP LARGO - Rev 1  (29 perpetui Kraken + BTC, candele 15m ricavate dai 5m, dal 01/01/2023)
Idea: in trend si compra (o si vende, sui perpetui) in un buon punto; stop LARGO; il guadagno si mette al sicuro presto:
  USCITA "1-2"  a +1 % lo stop va a pareggio; a +2 % lo stop va a +1 % e poi segue il massimo a 1 % di distanza
  USCITA "2-4"  uguale ma raddoppiata: pareggio a +2 %, a +4 % stop a +2 % e trailing 2 %
  TP 1 % / TP 2 %  obiettivo fisso, niente trailing (solo lo stop largo)
  STOP LARGO 3 % / 5 % / 10 %; tetto 30 giorni.
TREND   "1h": EMA 50 > EMA 200 su grafico 1 ora (= EMA 200/800 sui 15m) e prezzo sopra EMA 200 1h
        "4h": EMA 50 > EMA 200 su grafico 4 ore (= EMA 800/3200 sui 15m)        (short: tutto al contrario)
INGRESSO (alla chiusura della candela 15m, si entra all'apertura della successiva), solo in trend:
  media  il minimo tocca la EMA 50 dei 15m e la candela chiude sopra, verde
  rsi    RSI 14 (15m) risale sopra 35 (short: scende sotto 65)
  ritr   prezzo almeno 2 % sotto il massimo delle 24 h e candela verde (short: 2 % sopra il minimo, rossa)
  caso   qualsiasi candela in trend (per vedere se il punto d'ingresso conta)
Una posizione alla volta per moneta.
COSTI  SPOT (solo long): 0,25 % ingresso (limite) + 0,40 % uscita + spread reale
       PERPETUI (long e short): 0,07 % x2 + spread reale + funding 0,01 %/8h
PORTAFOGLIO 10 % del capitale per operazione, max 10 posizioni, nessuna leva, interesse composto.
Metodo: scelta sulla PROVA (primo 60 %) delle 13 liquide (12 + BTC): long con costi spot, long con costi perpetui, short (perpetui).
CRITERIO FISSATO PRIMA (17 nuove): netto medio per operazione > +0,10 %, senza le 10 migliori > 0, annuo > 0, calo > -20 %.
Uso (nella cartella dati):  python ../trend_15m_rev1.py
"""
import bisect, calendar, itertools, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cecchino_5m_rev1 as C
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
import verifica_monete_nuove_btc_guida_rev1 as V

INIZIO = calendar.timegm((2023, 1, 1, 0, 0, 0))
Q = 900; TETTO = 30 * 96
SPOT_IN, SPOT_OUT, PERP, FUND_ORA = 0.0025, 0.0040, 0.0007, 0.0001 / 8
QUOTA, MAX_POS = 0.10, 10
TRENDS = ("1h", "4h"); INGRESSI = ("media", "rsi", "ritr", "caso")
USCITE = {"1-2": (0.01, 0.02, 0.01, None), "2-4": (0.02, 0.04, 0.02, None), "TP 1 %": (None, None, None, 0.01), "TP 2 %": (None, None, None, 0.02)}
STOPS = (0.03, 0.05, 0.10)
LIQ = set(V.LIQUIDE12 + ["XBT"])

def media(v): return sum(v) / len(v) if v else 0.0
def p(x, n=2): return f"{x * 100:+.{n}f}%".replace(".", ",")

def ema(v, n):
    k = 2 / (n + 1); out = []; e = None
    for x in v: e = x if e is None else e + k * (x - e); out.append(e)
    return out

def rsi(C_, n=14):
    out = [50.0] * len(C_); g = l = 0.0
    for i in range(1, len(C_)):
        d = C_[i] - C_[i - 1]; up, dn = max(d, 0), max(-d, 0)
        if i <= n: g += up / n; l += dn / n
        else: g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n
        out[i] = 100 - 100 / (1 + g / l) if l else 100.0
    return out

class S15:
    def __init__(self, m, b5, sp):
        self.m, self.sp = m, sp; g = []; out = []
        for b in b5:
            if g and g[0][0] // Q != b[0] // Q:
                if len(g) == 3: out.append((g[0][0] // Q * Q, g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4]))
                g = []
            g.append(b)
        self.T = [x[0] for x in out]; self.O = [x[1] for x in out]; self.H = [x[2] for x in out]
        self.L = [x[3] for x in out]; self.C = [x[4] for x in out]
        c = self.C
        self.e50 = ema(c, 50); self.e200 = ema(c, 200); self.e800 = ema(c, 800); self.e3200 = ema(c, 3200)
        self.rsi = rsi(c)

    def trend(self, i, tipo, d):
        if tipo == "1h": return (self.e200[i] - self.e800[i]) * d > 0 and (self.C[i] - self.e800[i]) * d > 0
        return (self.e800[i] - self.e3200[i]) * d > 0

    def segnale(self, i, tipo, d):
        O, H, L, C_ = self.O, self.H, self.L, self.C
        if tipo == "caso": return True
        if tipo == "media":
            if d > 0: return L[i] <= self.e50[i] < C_[i] and C_[i] > O[i]
            return H[i] >= self.e50[i] > C_[i] and C_[i] < O[i]
        if tipo == "rsi":
            return (self.rsi[i - 1] < 35 <= self.rsi[i]) if d > 0 else (self.rsi[i - 1] > 65 >= self.rsi[i])
        if d > 0: return C_[i] <= max(H[max(0, i - 96):i + 1]) * 0.98 and C_[i] > O[i]
        return C_[i] >= min(L[max(0, i - 96):i + 1]) * 1.02 and C_[i] < O[i]

def esci(M, k, d, e, stop_pct, usc):
    a, b, tr, tp = USCITE[usc]
    stop = e * (1 - d * stop_pct); mx = e; fine = min(len(M.C), k + TETTO); mosso = False
    for x in range(k, fine):
        o, h, l = M.O[x], M.H[x], M.L[x]
        if x > k and M.T[x] - M.T[x - 1] > 4 * Q: return x - 1, M.C[x - 1], "buco"
        if (d > 0 and l <= stop) or (d < 0 and h >= stop):
            return x, (min(stop, o) if d > 0 else max(stop, o)), ("stop largo" if not mosso else ("pareggio" if stop == e else "trailing"))
        fav = h if d > 0 else l
        if tp is not None:
            obj = e * (1 + d * tp)
            if (fav - obj) * d >= 0: return x, (max(obj, o) if d > 0 else min(obj, o)), "obiettivo"
            continue
        if (fav - mx) * d > 0:
            mx = fav; g = (mx - e) * d / e; nuovo = stop
            if g >= a: nuovo = e
            if g >= b:
                nuovo = max(e * (1 + a), mx * (1 - tr)) if d > 0 else min(e * (1 - a), mx * (1 + tr))
            if (nuovo - stop) * d > 0: stop = nuovo; mosso = True
    return fine - 1, M.C[fine - 1], "30 giorni"

def operazioni(M, tr_tipo, ing, d, stop_pct, usc, i0, i1, cache):
    chiave = (M.m, tr_tipo, ing, d)
    if chiave not in cache:
        cache[chiave] = [i for i in range(max(i0, 3300), i1 - 1) if M.trend(i, tr_tipo, d) and M.segnale(i, ing, d)]
    cand = cache[chiave]; ops = []; pos = 0
    while pos < len(cand):
        i = cand[pos]; k = i + 1
        if M.T[k] - M.T[i] != Q: pos += 1; continue
        e = M.O[k]; x, px, mot = esci(M, k, d, e, stop_pct, usc)
        lordo = (px - e) * d / e; ore = (M.T[x] + Q - M.T[k]) / 3600
        spot = lordo - SPOT_IN - SPOT_OUT - M.sp if d > 0 else None
        perp = lordo - 2 * PERP - M.sp - FUND_ORA * ore
        ops.append((M.T[k], M.T[x] + Q, M.m, lordo, spot, perp, mot, ore))
        pos = bisect.bisect_right(cand, x, pos)
    return ops

def portafoglio(ops, idx, t0, t1):
    cap, picco, calo, aperte, prese, curva = 1.0, 1.0, 0.0, [], [], []
    for o in sorted(ops, key=lambda o: o[0]):
        if not t0 <= o[0] <= t1: continue
        for q in sorted(aperte):
            if q[0] <= o[0]:
                cap += q[1]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((q[0], cap))
        aperte = [q for q in aperte if q[0] > o[0]]
        if len(aperte) >= MAX_POS or any(q[2] == o[2] for q in aperte): continue
        aperte.append((o[1], cap * QUOTA * o[idx], o[2])); prese.append(o)
    for q in sorted(aperte):
        cap += q[1]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((q[0], cap))
    return prese, cap, calo, curva

def main():
    SP = spread(); serie = {}
    for m in ["XBT"] + V.LIQUIDE12 + V.NUOVE:
        b = C.scarica_5m(m)
        if len(b) >= 100000: serie[m] = S15(m, b, SP.get(m, SPREAD_DEFAULT))
        b = None
    monete = list(serie.values())
    liq = [M for M in monete if M.m in LIQ]; nuove = [M for M in monete if M.m not in LIQ]
    t0 = INIZIO; t1 = min(M.T[-1] for M in liq) - 86400
    taglio = t0 + (t1 - t0) * 0.6; giorni = (t1 - t0) / 86400; durata = giorni / 365
    anni = list(range(time.gmtime(t0).tm_year, time.gmtime(t1).tm_year + 1))
    d_ = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nDal {d_(t0)} al {d_(t1)}; prova fino al {d_(taglio)}. {len(liq)} liquide (con BTC) + {len(nuove)} nuove.\n", flush=True)
    rng = {M.m: (bisect.bisect_left(M.T, t0 - 3400 * Q), bisect.bisect_right(M.T, t1)) for M in monete}
    cache = {}

    def tutte(gruppo, tr_tipo, ing, d, st, usc):
        out = []
        for M in gruppo: out += operazioni(M, tr_tipo, ing, d, st, usc, *rng[M.m], cache)
        return [o for o in out if t0 <= o[0] <= t1]

    risultati = []
    for d, nome_v, idx in ((1, "LONG (costi SPOT)", 4), (1, "LONG (costi PERPETUI)", 5), (-1, "SHORT (costi PERPETUI)", 5)):
        print(f"================ {nome_v}: griglia sulla PROVA delle 13 liquide ================")
        print(f"   {'trend ingresso uscita stop':<30}{'op/g':>6}{'lordo':>8}{'netto':>8}{'n.perp':>8}{'vinte':>7}{'stop':>6}{'durata':>8}")
        righe = []
        for tr_tipo, ing, usc, st in itertools.product(TRENDS, INGRESSI, USCITE, STOPS):
            ops = [o for o in tutte(liq, tr_tipo, ing, d, st, usc) if o[0] < taglio]
            if len(ops) < 50: continue
            righe.append((media([o[idx] for o in ops]), tr_tipo, ing, usc, st, ops))
        righe.sort(key=lambda r: -r[0])
        gg = (taglio - t0) / 86400
        for pos, (n, tr_tipo, ing, usc, st, ops) in enumerate(righe[:20] + righe[-5:]):
            if pos == 20: print("   ... (peggiori)")
            dur = sorted(o[7] for o in ops)[len(ops) // 2]
            print(f"   {f'{tr_tipo} {ing} {usc} {st * 100:g}%':<30}{len(ops) / gg:>6.1f}{p(media([o[3] for o in ops])):>8}{p(n):>8}"
                  f"{p(media([o[5] for o in ops])):>8}{media([o[idx] > 0 for o in ops]) * 100:>6.0f}%"
                  f"{media([o[6] == 'stop largo' for o in ops]) * 100:>5.0f}%{dur:>6.0f} h", flush=True)
        print(f"   varianti con netto > 0: {sum(1 for r in righe if r[0] > 0)} su {len(righe)}")
        # il punto d'ingresso conta? confronto con 'caso' a parita' di trend/uscita/stop
        print("   Ingresso scelto contro ingresso a caso (stessa uscita e stop, media su tutte le combinazioni, netto):")
        for ing in INGRESSI:
            v = [r[0] for r in righe if r[2] == ing]
            print(f"      {ing:<8} {p(media(v))}")
        risultati.append((d, nome_v, idx, righe[0]))
        print()

    for d, nome_v, idx, (n, tr_tipo, ing, usc, st, _) in risultati:
        print(f"================ {nome_v}: MIGLIORE IN PROVA = trend {tr_tipo}, ingresso {ing}, uscita {usc}, stop {st * 100:g} % ================")
        ops_l = tutte(liq, tr_tipo, ing, d, st, usc); ops_n = tutte(nuove, tr_tipo, ing, d, st, usc)
        print(f"   {'':<26}{'op/g':>6}{'lordo':>8}{'netto':>8}{'prova':>8}{'verif':>8}{'-top10':>8}{'vinte':>7}{'annuo':>8}{'calo':>6}"
              + "".join(f"{a:>7}" for a in anni))
        verdetto = None
        for nome, ops in (("13 liquide (scelta qui)", ops_l), ("17 NUOVE (mai viste)", ops_n), ("30 insieme", ops_l + ops_n)):
            prese, cap, calo, curva = portafoglio(ops, idx, t0, t1)
            net = sorted(o[idx] for o in prese)
            pr = [o[idx] for o in prese if o[0] < taglio]; ve = [o[idx] for o in prese if o[0] >= taglio]
            annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
            def valore(t):
                v = 1.0
                for tt, c in curva:
                    if tt <= t: v = c
                    else: break
                return v
            celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(max(t0, calendar.timegm((a, 1, 1, 0, 0, 0)))) - 1) * 100:>+6.0f}%" for a in anni)
            print(f"   {nome:<26}{len(prese) / giorni:>6.1f}{p(media([o[3] for o in prese])):>8}{p(media(net)):>8}{p(media(pr)):>8}"
                  f"{p(media(ve)):>8}{p(media(net[:-10])):>8}{media([x > 0 for x in net]) * 100:>6.0f}%{annuo * 100:>+7.1f}%"
                  f"{calo * 100:>+5.0f}%{celle}".replace(".", ","), flush=True)
            if nome.startswith("17"): verdetto = (media(net), media(net[:-10]), annuo, calo)
            if nome.startswith("30"):
                vinte = [x for x in net if x > 0]; perse = [x for x in net if x <= 0]
                print(f"\n   Statistica (30 monete, operazioni del portafoglio): vinte {len(vinte)} ({len(vinte) / max(len(net), 1) * 100:.0f} %) "
                      f"media {p(media(vinte))}; perse {len(perse)} media {p(media(perse))}; peggiore {p(net[0] if net else 0)}")
                print(f"   {'motivo uscita':<16}{'n':>6}{'quota':>7}{'netto medio':>13}{'durata med.':>13}")
                for mot in ("obiettivo", "pareggio", "trailing", "stop largo", "30 giorni", "buco"):
                    g = [o for o in prese if o[6] == mot]
                    if g: print(f"   {mot:<16}{len(g):>6}{len(g) / len(prese) * 100:>6.0f}%{p(media([o[idx] for o in g])):>13}"
                                f"{sorted(o[7] for o in g)[len(g) // 2]:>11.0f} h")
                print()
        n, n10, an, ca = verdetto
        ok = n > 0.001 and n10 > 0 and an > 0 and ca > -0.20
        print(f"   VERDETTO {nome_v} sulle 17 nuove: netto {p(n)}, senza 10 {p(n10)}, annuo {an * 100:+.1f} %, calo {ca * 100:.0f} % -> "
              f"{'PROMOSSA' if ok else 'BOCCIATA'}\n".replace(".", ","))

if __name__ == "__main__":
    main()
