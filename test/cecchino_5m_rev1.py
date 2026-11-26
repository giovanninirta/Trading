#!/usr/bin/env python3
"""
CECCHINO 5 MINUTI - Rev 1  (perpetui Kraken, 29 monete, segnale e gestione TUTTI su candele da 5 minuti)
Stessa idea di Cecchino ma senza aspettare le 4 ore:
  SEGNALE  una candela 5m di BTC chiude in salita (long) / discesa (short) di oltre ZB ATR (ATR 14 Wilder sui 5m)
  MONETE   salite/scese nella stessa candela di oltre ZM ATR (della moneta); le piu' forti, max 5 posizioni,
           mai due volte la stessa moneta, posizioni totali al massimo 3 volte il capitale
  INGRESSO all'apertura della candela 5m successiva (+ ritardo nei costi)
  USCITA   stop ST ATR; pareggio a +1 ATR; trailing TR ATR dal massimo; se entro F1 candele non ha superato
           +3 ATR si chiude; oltre +3 ATR (fase 2) niente limite (tetto 24 h) e trailing TR + 0,10 x (guadagno - 3)
           Lo stop aggiornato vale dalla candela successiva (prudente).
  RISCHIO  0,75 % del capitale per operazione (R = ST ATR), interesse composto
Moltiplicatori provati (griglia): ZB 2/3/4/5, ZM 1,5/2,5/3,5, ST 1/2, TR 1,5/3, F1 12/48 candele (1 h / 4 h).

Costi, due scenari:
  TAKER  0,07 % per ordine x2 + spread reale + 0,05 % ritardo + funding 0,01 %/8h   (come tutti i test finora)
  In entrambi: +0,02 % di slittamento sulle uscite in stop (a 5 minuti lo stop esatto e' ottimista)
  MAKER  ingresso limite post-only 0,02 % (si assume eseguito, ottimista), uscita a mercato 0,05 % + meta' spread,
         funding come sopra
Metodo: si sceglie SOLO sulla prova (primo 60 %) delle 12 liquide; poi verifica (ultimo 40 %) e 17 nuove.
CRITERIO FISSATO PRIMA (sulle 17 nuove, scenario TAKER e separatamente MAKER):
  PROMOSSA se netto > +0,05 R  E  netto senza le 10 migliori > 0  E  annuo > 0  E  calo > -20 %

Uso (nella cartella dati):  python ../cecchino_5m_rev1.py
Scarica PF_*USD_5m.csv (dal 05/2022) se non c'e' gia'. Solo libreria standard.
"""
import bisect, calendar, csv, itertools, json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import atr, COSTO, FUNDING_ORA
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
import verifica_monete_nuove_btc_guida_rev1 as V

M5 = 300
API5 = "https://futures.kraken.com/api/charts/v1/trade/PF_{m}USD/5m?from={a}&to={b}"
INIZIO = calendar.timegm((2022, 5, 1, 0, 0, 0))
RISCHIO, MAX_POS, LEVA = 0.0075, 5, 3.0
PAREGGIO, SOGLIA2, ALLARGA, TETTO = 1.0, 3.0, 0.10, 288
RITARDO, MAKER, TAKER_REALE, SLIP_STOP = 0.0005, 0.0002, 0.0005, 0.0002
GRIGLIA = dict(ZB=(2.0, 3.0, 4.0, 5.0), ZM=(1.5, 2.5, 3.5), ST=(1.0, 2.0), TR=(1.5, 3.0), F1=(12, 48))

def scarica_5m(m):
    path = f"PF_{m}USD_5m.csv"
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        out = []
        for r in csv.reader(open(path)):
            try: out.append((int(float(r[0])), float(r[1]), float(r[2]), float(r[3]), float(r[4])))
            except (ValueError, IndexError): pass
        return out
    fine = int(time.time()); passo = 1500 * M5; out = {}; t = INIZIO
    while t < fine:
        js = None
        for tentativo in range(4):
            try:
                with urllib.request.urlopen(API5.format(m=m, a=t, b=min(t + passo, fine)), timeout=30) as r:
                    js = json.load(r); break
            except Exception:
                time.sleep(2 + 3 * tentativo)
        for c in (js or {}).get("candles", []):
            ts = int(c["time"]) // 1000
            out[ts] = (ts, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]))
        t += passo; time.sleep(0.15)
    righe = [out[k] for k in sorted(out)][:-1]
    with open(path, "w", newline="") as f: csv.writer(f).writerows(righe)
    return righe

class Serie:
    def __init__(self, m, barre, sp):
        self.m, self.sp = m, sp
        self.T = [b[0] for b in barre]; self.O = [b[1] for b in barre]; self.H = [b[2] for b in barre]
        self.L = [b[3] for b in barre]; self.C = [b[4] for b in barre]
        self.A = atr(self.H, self.L, self.C); self.idx = {t: i for i, t in enumerate(self.T)}

def esci(M, k, d, e, a, st, tr, f1):
    """Gestione dalla candela k (ingresso all'apertura di k). d=+1 long, -1 short. Ritorna (indice, prezzo, uscita in stop)."""
    stop, mx, fase2 = e - d * st * a, e, False
    fine = min(len(M.C), k + TETTO)
    for x in range(k, fine):
        o, h, l = M.O[x], M.H[x], M.L[x]
        if x > k and M.T[x] - M.T[x - 1] > 3 * M5: return x - 1, M.C[x - 1], False  # buco nei dati
        if not fase2 and x - k >= f1: return x - 1, M.C[x - 1], False
        if (d > 0 and l <= stop) or (d < 0 and h >= stop):
            return x, (min(stop, o) if d > 0 else max(stop, o)), True
        estremo = h if d > 0 else l
        if (estremo - mx) * d > 0:
            mx = estremo; g = (mx - e) * d / a
            if g >= SOGLIA2: fase2 = True
            if g >= PAREGGIO:
                dist = (tr + (ALLARGA * (g - SOGLIA2) if fase2 else 0.0)) * a
                nuovo = mx - d * dist
                stop = max(stop, e, nuovo) if d > 0 else min(stop, e, nuovo)
    return fine - 1, M.C[fine - 1], False

def eventi(btc, zb, d):
    """Indici delle candele BTC con movimento oltre zb ATR nel verso d."""
    out = []
    for i in range(30, len(btc.C)):
        a = btc.A[i - 1]
        if a and (btc.C[i] - btc.C[i - 1]) * d / a > zb: out.append(i)
    return out

_CACHE = {}
def operazioni(btc, monete, p, d):
    """Operazioni candidate (prima del portafoglio): (t_ingresso, t_uscita, m, z, pct, lordo, net_taker, net_maker).
    Le uscite si calcolano una volta per (verso, ST, TR, F1) con le soglie piu' basse e poi si filtrano per ZB e ZM."""
    zb, zm, st, tr, f1 = p
    chiave = (d, tuple(M.m for M in monete), st, tr, f1)
    if chiave not in _CACHE:
        zb0, zm0 = min(GRIGLIA["ZB"]), min(GRIGLIA["ZM"]); tutte = []
        for i in eventi(btc, zb0, d):
            t = btc.T[i]; z_btc = (btc.C[i] - btc.C[i - 1]) * d / btc.A[i - 1]
            for M in monete:
                j = M.idx.get(t)
                if j is None or j < 30 or j + 2 >= len(M.C) or not M.A[j - 1] or M.H[j] == M.L[j]: continue
                if M.T[j + 1] != t + M5: continue
                z = (M.C[j] - M.C[j - 1]) * d / M.A[j - 1]
                if z <= zm0: continue
                k = j + 1; e = M.O[k]; a = M.A[j]; pct = st * a / e
                if not 0.002 <= pct <= 0.10: continue
                x, px, in_stop = esci(M, k, d, e, a, st, tr, f1)
                lordo = (px - e) * d / (st * a)
                ore = (M.T[x] + M5 - M.T[k]) / 3600
                fund = FUNDING_ORA * ore + (SLIP_STOP if in_stop else 0.0)
                n_t = lordo - (2 * COSTO + M.sp + RITARDO + fund) / pct
                n_m = lordo - (MAKER + TAKER_REALE + M.sp / 2 + fund) / pct
                tutte.append((M.T[k], M.T[x] + M5, M.m, z, pct, lordo, n_t, n_m, z_btc))
        _CACHE[chiave] = tutte
    return [o for o in _CACHE[chiave] if o[8] > zb and o[3] > zm]

def portafoglio(ops, scenario, t0, t1):
    """Applica rischio, max posizioni, leva. scenario 6 = taker, 7 = maker. Ritorna (prese, cap, calo, curva)."""
    cap, picco, calo, aperte, prese, curva = 1.0, 1.0, 0.0, [], [], []
    per_t = {}
    for o in ops:
        if t0 <= o[0] <= t1: per_t.setdefault(o[0], []).append(o)
    for t in sorted(per_t):
        for q in sorted(aperte, key=lambda q: q[0]):
            if q[0] <= t:
                cap += q[1]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((q[0], cap))
        aperte = [q for q in aperte if q[0] > t]
        for o in sorted(per_t[t], key=lambda o: -o[3]):
            if len(aperte) >= MAX_POS or any(q[2] == o[2] for q in aperte): continue
            importo = cap * RISCHIO; noz = importo / o[4]
            if sum(q[3] for q in aperte) + noz > LEVA * cap: continue
            aperte.append((o[1], importo * o[scenario], o[2], noz)); prese.append(o)
    for q in sorted(aperte, key=lambda q: q[0]):
        cap += q[1]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((q[0], cap))
    return prese, cap, calo, curva

def media(v): return sum(v) / len(v) if v else 0.0

def riga(nome, prese, cap, calo, curva, sc, durata, taglio, anni):
    net = sorted(o[sc] for o in prese)
    pr = [o[sc] for o in prese if o[0] < taglio]; ve = [o[sc] for o in prese if o[0] >= taglio]
    annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
    durate = sorted((o[1] - o[0]) / 60 for o in prese)
    print(f"   {nome:<34}{len(prese) / durata:>6.0f}{media([o[5] for o in prese]):>+7.2f}{media(net):>+7.2f}{media(pr):>+7.2f}"
          f"{media(ve):>+7.2f}{media(net[:-10]):>+7.2f}{media([1.0 if x > 0 else 0.0 for x in net]) * 100:>5.0f}%"
          f"{annuo * 100:>+8.1f}%{calo * 100:>+5.0f}%{(durate[len(durate) // 2] if durate else 0):>6.0f}m{celle}".replace(".", ","))
    return media(net), media(net[:-10]), annuo, calo

def intestazione(anni):
    print(f"   {'':<34}{'op/a':>6}{'lordo':>7}{'netto':>7}{'prova':>7}{'verif':>7}{'-top10':>7}{'vinte':>6}"
          f"{'annuo':>9}{'calo':>6}{'durata':>7}" + "".join(f"{a:>7}" for a in anni))

def main():
    SP = spread()
    lista = ["XBT"] + V.LIQUIDE12 + V.NUOVE
    print(f"Carico/scarico i dati a 5 minuti di {len(lista)} perpetui...", flush=True)
    with ThreadPoolExecutor(4) as ex: dati = dict(zip(lista, ex.map(scarica_5m, lista)))
    serie = {}
    for m, b in dati.items():
        if len(b) < 100000: print(f"   {m}: solo {len(b)} candele, esclusa"); continue
        serie[m] = Serie(m, b, SP.get(m, SPREAD_DEFAULT))
        dati[m] = None
    if "XBT" not in serie: print("BTC mancante"); return
    btc = serie.pop("XBT")
    liq = [serie[m] for m in V.LIQUIDE12 if m in serie]; nuove = [serie[m] for m in V.NUOVE if m in serie]
    t0 = max(M.T[0] for M in liq + [btc]) + 86400; t1 = min(M.T[-1] for M in liq + [btc]) - 86400
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    anni = list(range(time.gmtime(t0).tm_year, time.gmtime(t1).tm_year + 1))
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nDal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}. {len(liq)} liquide + {len(nuove)} nuove.")
    print(f"Candele 5m: BTC {len(btc.C)}. Eventi BTC long per ZB: " +
          "  ".join(f"{zb:g}: {len([i for i in eventi(btc, zb, 1) if t0 <= btc.T[i] <= t1]) / durata:.0f}/anno" for zb in GRIGLIA['ZB']))
    print("Colonne in R (R = stop). lordo = prima dei costi. durata = mediana in minuti.\n", flush=True)

    combinazioni = list(itertools.product(*GRIGLIA.values()))
    for d_nome, verso in (("LONG", 1), ("SHORT", -1)):
        print(f"=============== {d_nome}: griglia sulla PROVA delle 12 liquide ({len(combinazioni)} varianti) ===============")
        print(f"   {'ZB  ZM  ST  TR  F1':<22}{'op/a':>6}{'lordo':>7}{'n.tak':>7}{'n.mak':>7}{'cost.t':>7}")
        tabella = []
        for p in combinazioni:
            ops = [o for o in operazioni(btc, liq, p, verso) if t0 <= o[0] < taglio]
            if not ops: continue
            lordo = media([o[5] for o in ops]); nt = media([o[6] for o in ops]); nm = media([o[7] for o in ops])
            tabella.append((nm, nt, lordo, p, len(ops)))
        tabella.sort(key=lambda x: -x[0])
        dur_prova = (taglio - t0) / (365 * 86400)
        for pos, (nm, nt, lordo, p, n) in enumerate(tabella[:15] + tabella[-5:]):
            if pos == 15: print("   ... (peggiori)")
            print(f"   {'%g  %g  %g  %g  %d' % p:<22}{n / dur_prova:>6.0f}{lordo:>+7.3f}{nt:>+7.3f}{nm:>+7.3f}{lordo - nt:>7.3f}".replace(".", ","))
        positivi_lordo = sum(1 for x in tabella if x[2] > 0)
        print(f"   varianti con lordo > 0: {positivi_lordo}/{len(tabella)}; con netto taker > 0: {sum(1 for x in tabella if x[1] > 0)}; "
              f"con netto maker > 0: {sum(1 for x in tabella if x[0] > 0)}", flush=True)
        if not tabella: continue
        scelte = {"maker": max(tabella, key=lambda x: x[0])[3], "taker": max(tabella, key=lambda x: x[1])[3]}
        for sc_nome, sc in (("TAKER", 6), ("MAKER", 7)):
            p = scelte[sc_nome.lower()]
            print(f"\n   --- {d_nome} {sc_nome}: migliore in prova ZB {p[0]:g}, ZM {p[1]:g}, ST {p[2]:g}, TR {p[3]:g}, F1 {p[4]} -> portafoglio ---")
            intestazione(anni)
            ops_l = operazioni(btc, liq, p, verso); ops_n = operazioni(btc, nuove, p, verso)
            riga("12 liquide (scelta qui)", *portafoglio(ops_l, sc, t0, t1), sc, durata, taglio, anni)
            n, n10, an, ca = riga("17 NUOVE (mai viste)", *portafoglio(ops_n, sc, t0, t1), sc, durata, taglio, anni)
            riga("29 insieme", *portafoglio(ops_l + ops_n, sc, t0, t1), sc, durata, taglio, anni)
            ok = n > 0.05 and n10 > 0 and an > 0 and ca > -0.20
            print(f"   VERDETTO {d_nome} {sc_nome} sulle 17 nuove: netto {n:+.3f}, senza 10 {n10:+.3f}, annuo {an * 100:+.1f} %, "
                  f"calo {ca * 100:.0f} % -> {'PROMOSSA' if ok else 'BOCCIATA'}".replace(".", ","))
        print(flush=True)

if __name__ == "__main__":
    main()
