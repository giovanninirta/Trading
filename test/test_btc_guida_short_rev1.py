#!/usr/bin/env python3
"""
TEST "BTC GUIDA AL RIBASSO" (SHORT) - Rev 1  (perpetui Kraken, candele 4h, uscita sui 15 min)
Specchio di Cecchino/Segugio per gli short, con le idee di "Segugio v2".
  SEGNALE  candela 4h di BTC in discesa: oltre -2 ATR ("atr2"), oltre -1,25 % ("pct1,25"), oltre -1,6 % ("pct1,6")
  REGIME   "nessuno" oppure "sma50": BTC chiude sotto la sua media semplice di 50 candele da 4h
  MONETE   scese di oltre 1,7 ATR nella stessa candela; si vendono le 5 piu' deboli (max 5 posizioni, leva 3,
           mai due volte la stessa moneta)
  USCITA   "specchio": stop 1,0 ATR sopra; pareggio a +1 ATR di guadagno; trailing 1,5 ATR dal minimo; se dopo
                       16 ore non ha superato +3 ATR si chiude; oltre +3 ATR niente tempo e trailing 1,5+0,10x(g-3)
           "v2":       stop 1,4 ATR; pareggio a +1,2 ATR; trailing 1,3 ATR; chiusura dopo 12 ore se sotto +2,5 ATR
  RISCHIO  0,75 % per operazione (R = distanza dello stop), interesse composto
  COSTI    0,07 % x2 + spread reale + 0,05 % ritardo + funding 0,01 %/8h (pagato anche dagli short, prudenza)
CONTROLLI (sulla variante scelta):
  (a) stessi segnali di BTC, monete scelte A CASO tra quelle disponibili (media di 20 estrazioni)
  (b) short in MOMENTI A CASO (stesso numero di ingressi), monete a caso, stessa uscita (media di 20 estrazioni)
METODO E CRITERIO (fissati prima):
  scelta = miglior netto in PROVA sulle 12 liquide (almeno 30 operazioni in prova)
  PROMOSSA se sulle 17 nuove: netto > +0,05 R, netto senza le 10 migliori > 0, annuo > 0, calo >= -20 %
  e netto almeno +0,05 R sopra il controllo (b).
Uso (nella cartella dati):  python ../test_btc_guida_short_rev1.py
"""
import bisect, calendar, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, COSTO, FUNDING_ORA
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
from verifica_monete_nuove_btc_guida_rev1 import Moneta, LIQUIDE12, NUOVE, H4

RISCHIO, MAX_POS, LEVA, RITARDO, TETTO, MONETA_ATR = 0.0075, 5, 3.0, 0.0005, 60 * 96, 1.7
USCITE = {"specchio": dict(stop=1.0, pari=1.0, trail=1.5, ore=16, soglia2=3.0, allarga=0.10),
          "v2":       dict(stop=1.4, pari=1.2, trail=1.3, ore=12, soglia2=2.5, allarga=0.0)}
SEGNALI = {"atr2": ("atr", 2.0), "pct1,25": ("pct", 0.0125), "pct1,6": ("pct", 0.016)}

def gestisci_short(M, k, e, a, chiusura, u):
    """Uscita short sui 15 min dalla candela k. Ritorna (t_uscita, prezzo)."""
    stop, mn, fase2, ultima = e + u["stop"] * a, e, False, e
    for x in range(k, min(len(M.Q), k + TETTO)):
        t, o, h, l, c = M.Q[x]
        if not fase2 and t >= chiusura + u["ore"] * 3600: return t, ultima
        if h >= stop: return t + 900, max(stop, o)
        if l < mn:
            mn = l; g = (e - l) / a
            if not fase2 and g >= u["soglia2"]: fase2 = True
            if g >= u["pari"]:
                dist = u["trail"] + (u["allarga"] * (g - u["soglia2"]) if fase2 else 0.0)
                stop = min(stop, e, l + dist * a)
        ultima = c
    x = min(len(M.Q), k + TETTO) - 1
    return M.Q[x][0] + 900, M.Q[x][4]

def sma(v, n):
    out, acc = [None] * len(v), 0.0
    for i, x in enumerate(v):
        acc += x
        if i >= n: acc -= v[i - n]
        if i >= n - 1: out[i] = acc / n
    return out

def simula(btc, monete, eventi, u, scelta, rng=None):
    """eventi = lista di indici di candela 4h di BTC in cui si cerca di entrare.
    scelta: 'deboli' (le 5 piu' deboli oltre 1,7 ATR), 'caso_segnale' (a caso tra le disponibili), 'caso' (idem)."""
    cap, picco, calo, aperte, ops, curva = 1.0, 1.0, 0.0, [], [], []
    for i in eventi:
        t = btc.T[i]; chiusura = t + H4
        for p in sorted(aperte, key=lambda p: p["fine"]):
            if p["fine"] <= chiusura:
                cap += p["importo"] * p["r"]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p["fine"], cap))
        aperte = [p for p in aperte if p["fine"] > chiusura]
        cand = []
        for M in monete:
            j = M.idx.get(t)
            if j is None or j < 30 or not M.A[j - 1] or M.H[j] == M.L[j]: continue
            z = (M.C[j] - M.C[j - 1]) / M.A[j - 1]
            if scelta == "deboli" and z >= -MONETA_ATR: continue
            cand.append((z, M, j))
        if scelta == "deboli": cand.sort(key=lambda x: x[0])
        else: rng.shuffle(cand)
        for z, M, j in cand:
            if len(aperte) >= MAX_POS or any(p["m"] == M.m for p in aperte): continue
            e, a = M.C[j], M.A[j]; pct = u["stop"] * a / e
            if not 0.002 <= pct <= 0.10: continue
            k = bisect.bisect_left(M.QT, chiusura)
            if k >= len(M.Q) - 1 or M.QT[k] - chiusura > 3600: continue
            importo = cap * RISCHIO; noz = importo / pct
            if sum(p["noz"] for p in aperte) + noz > LEVA * cap: continue
            fine, px = gestisci_short(M, k, e, a, chiusura, u)
            lordo = (e - px) / (u["stop"] * a); ore = (fine - chiusura) / 3600
            netto = lordo - (2 * COSTO + M.sp + RITARDO + FUNDING_ORA * ore) / pct
            aperte.append({"m": M.m, "fine": fine, "importo": importo, "noz": noz, "r": netto})
            ops.append((chiusura, M.m, lordo, netto))
            if scelta != "deboli" and len([o for o in ops if o[0] == chiusura]) >= 5: break
    for p in sorted(aperte, key=lambda p: p["fine"]):
        cap += p["importo"] * p["r"]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p["fine"], cap))
    return ops, cap, calo, curva

def media(v): return sum(v) / len(v) if v else 0.0

def misura(ops, cap, calo, curva, taglio, durata):
    net = sorted(o[3] for o in ops)
    return dict(n=len(ops) / durata, npr=sum(1 for o in ops if o[0] < taglio), lordo=media([o[2] for o in ops]), netto=media(net),
                prova=media([o[3] for o in ops if o[0] < taglio]), verif=media([o[3] for o in ops if o[0] >= taglio]),
                s10=media(net[:-10]), annuo=(cap ** (1 / durata) - 1) if cap > 0 else -1, calo=calo, curva=curva)

def riga(m):
    return (f"{m['n']:>6.0f}{m['lordo']:>+8.3f}{m['netto']:>+8.3f}{m['prova']:>+8.3f}{m['verif']:>+8.3f}{m['s10']:>+8.3f}"
            f"{m['annuo'] * 100:>+7.1f}%{m['calo'] * 100:>+6.0f}%").replace(".", ",")

def main():
    SP = spread(); gruppi = {}
    for nome, lista in (("12", LIQUIDE12), ("17", NUOVE)):
        gruppi[nome] = []
        for m in lista:
            b = carica(m, 1)
            if not b or len(b) < 5000: continue
            q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
            if len(q) >= 20000: gruppi[nome].append(Moneta(m, b, q, SP.get(m, SPREAD_DEFAULT)))
    btc = Moneta("XBT", carica("XBT", 1), [], 0); s50 = sma(btc.C, 50)
    liq = gruppi["12"]
    t0 = max(max(M.T[0], M.Q[0][0]) for M in liq) + 30 * H4; t1 = min(min(M.T[-1], M.Q[-1][0]) for M in liq) - 2 * 86400
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    a0, a1 = time.gmtime(t0).tm_year, time.gmtime(t1).tm_year
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    validi = [i for i in range(51, len(btc.C)) if t0 <= btc.T[i] <= t1 and btc.A[i - 1]]
    def eventi(segnale, regime):
        tipo, soglia = SEGNALI[segnale]; out = []
        for i in validi:
            z = (btc.C[i] - btc.C[i - 1]) / btc.A[i - 1]; p = btc.C[i] / btc.C[i - 1] - 1
            if not ((tipo == "atr" and z < -soglia) or (tipo == "pct" and p < -soglia)): continue
            if regime == "sma50" and not (s50[i] and btc.C[i] < s50[i]): continue
            out.append(i)
        return out
    print(f"\n{len(gruppi['12'])} liquide + {len(gruppi['17'])} nuove, dal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}.")
    print(f"BTC nel periodo: da {btc.C[validi[0]]:,.0f} a {btc.C[validi[-1]]:,.0f} $.\n".replace(",", "."))
    testa = f"{'op/a':>6}{'lordo':>8}{'netto':>8}{'prova':>8}{'verif':>8}{'-top10':>8}{'annuo':>8}{'calo':>7}"
    print(f"   {'segnale | regime | uscita':<30}{'-------------- 12 LIQUIDE --------------':^61}  ||{'-------------- 17 NUOVE --------------':^61}")
    print(f"   {'':<30}{testa}  ||{testa}")
    righe = []
    for segnale in SEGNALI:
        for regime in ("nessuno", "sma50"):
            ev = eventi(segnale, regime)
            for uscita, u in USCITE.items():
                a = misura(*simula(btc, gruppi["12"], ev, u, "deboli"), taglio, durata)
                b = misura(*simula(btc, gruppi["17"], ev, u, "deboli"), taglio, durata)
                nome = f"{segnale} | {regime} | {uscita}"
                righe.append((nome, segnale, regime, uscita, a, b))
                print(f"   {nome:<30}{riga(a)}  ||{riga(b)}  ({len(ev)} segnali BTC)", flush=True)
        print()
    valide = [r for r in righe if r[4]["npr"] >= 30]
    if not valide: print("Nessuna variante con almeno 30 operazioni in prova."); return
    nome, segnale, regime, uscita, a, b = max(valide, key=lambda r: r[4]["prova"])
    u = USCITE[uscita]; ev = eventi(segnale, regime)
    print(f"=== SCELTA (miglior netto in PROVA sulle 12 liquide): {nome} ===")
    controlli = {}
    for g in ("12", "17"):
        ra, rb = [], []
        for seme in range(20):
            rng = random.Random(seme)
            ra.append(misura(*simula(btc, gruppi[g], ev, u, "caso_segnale", rng), taglio, durata))
            rng = random.Random(1000 + seme)
            momenti = sorted(rng.sample(validi, min(len(validi), len(ev))))
            rb.append(misura(*simula(btc, gruppi[g], momenti, u, "caso", rng), taglio, durata))
        controlli[g] = ({k: media([x[k] for x in ra]) for k in ("n", "lordo", "netto", "s10", "annuo", "calo")},
                        {k: media([x[k] for x in rb]) for k in ("n", "lordo", "netto", "s10", "annuo", "calo")})
    print(f"   {'':<44}{'op/a':>6}{'lordo':>8}{'netto':>8}{'-top10':>8}{'annuo':>8}{'calo':>7}")
    for g, nomeg in (("12", "12 liquide"), ("17", "17 nuove")):
        reale = a if g == "12" else b
        for etichetta, m in ((f"{nomeg}: regola (le 5 piu' deboli)", reale), (f"{nomeg}: (a) stessi segnali, monete a caso", controlli[g][0]),
                             (f"{nomeg}: (b) momenti e monete a caso", controlli[g][1])):
            print(f"   {etichetta:<44}{m['n']:>6.0f}{m['lordo']:>+8.3f}{m['netto']:>+8.3f}{m['s10']:>+8.3f}{m['annuo'] * 100:>+7.1f}%{m['calo'] * 100:>+6.0f}%".replace(".", ","))
    def anni(curva):
        def valore(t):
            v = 1.0
            for tt, c in curva:
                if tt <= t: v = c
                else: break
            return v
        return "".join(f"{(valore(calendar.timegm((x + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((x, 1, 1, 0, 0, 0))) - 1) * 100:>+7.1f}%"
                       for x in range(a0, a1 + 1)).replace(".", ",")
    print(f"\n   anno per anno      " + "".join(f"{x:>8}" for x in range(a0, a1 + 1)))
    print(f"   12 liquide         {anni(a['curva'])}")
    print(f"   17 nuove           {anni(b['curva'])}")
    cb = controlli["17"][1]["netto"]
    ok = b["netto"] > 0.05 and b["s10"] > 0 and b["annuo"] > 0 and b["calo"] >= -0.20 and b["netto"] >= cb + 0.05
    print(f"\n=== VERDETTO sulle 17 nuove: netto {b['netto']:+.3f} R (> +0,05), senza 10 {b['s10']:+.3f} (> 0), annuo {b['annuo'] * 100:+.1f} % (> 0), "
          f"calo {b['calo'] * 100:.0f} % (>= -20), controllo (b) {cb:+.3f} (serve regola >= controllo + 0,05) -> "
          f"{'PROMOSSA' if ok else 'BOCCIATA'} ===".replace(".", ","))

if __name__ == "__main__":
    main()
