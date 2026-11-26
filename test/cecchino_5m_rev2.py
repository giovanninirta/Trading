#!/usr/bin/env python3
"""
CECCHINO 5 MINUTI - Rev 2  (perpetui Kraken, 29 monete, candele 5m, SOLO DAL 01/01/2023: crollo 2022 escluso)
Novita' rispetto alla Rev 1:
  A) ANALISI DEGLI INGRESSI SBAGLIATI: per 11 caratteristiche del segnale (forza moneta e BTC, chiusura nella
     candela, ampiezza, movimento dell'ultima ora, distanza dal minimo/massimo 24h, volatilita' relativa,
     trend BTC 24h, quante monete scattano insieme, ora, salto all'apertura) si guarda in quintili la quota di
     operazioni "sbagliate subito" (stop iniziale senza mai toccare +0,25 R) e il risultato. Prova e verifica separate.
  B) TIPI DI INGRESSO:  mercato (apertura candela dopo il segnale, come Rev 1)
                        STOP: si entra solo se il prezzo supera di X ATR la chiusura del segnale nel verso del
                              movimento entro W candele (ordine stop = taker, +0,03 % di slittamento)
                        LIMITE realistico: ordine X ATR indietro, eseguito SOLO se il prezzo lo attraversa entro W
                              candele (maker)
     USCITA RAPIDA: dopo N candele dall'ingresso, se non ha mai toccato +0,25 R si chiude (N = 1, 2, 3 o mai)
     Resto dell'uscita come Rev 1 (stop ST ATR, pareggio 1, trailing TR, fase 1 48 candele, fase 2 da +3 ATR).
  C) PIU' OPERAZIONI: portafoglio con rischio piu' basso e piu' posizioni (0,75 %/5, 0,5 %/10, 0,25 %/20, leva 3),
     long, short e insieme; operazioni al giorno e quota di giorni con operazioni.
Costi: taker 0,07 % per ordine x2 + spread reale (+ ritardo 0,05 % solo per l'ingresso a mercato, + 0,03 % per lo
stop d'ingresso); maker 0,02 % + uscita 0,05 % + meta' spread. Uscite in stop +0,02 %. Funding 0,01 %/8h.
Metodo: si sceglie sulla PROVA (primo 60 % del 2023-2026) delle 12 liquide; si guarda verifica e 17 nuove.
CRITERIO FISSATO PRIMA (sulle 17 nuove, 2023-2026): netto > +0,05 R, senza le 10 migliori > 0, e portafoglio
0,5 % / 10 posizioni / leva 3 con annuo > 0 e calo > -20 %.
Uso (nella cartella dati):  python ../cecchino_5m_rev2.py
"""
import bisect, calendar, itertools, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cecchino_5m_rev1 as C
from cecchino_5m_rev1 import M5, COSTO, FUNDING_ORA, RITARDO, MAKER, TAKER_REALE, SLIP_STOP
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
import verifica_monete_nuove_btc_guida_rev1 as V

INIZIO_TEST = calendar.timegm((2023, 1, 1, 0, 0, 0))
ST, TR, F1 = 2.0, 1.5, 48
SLIP_INGRESSO = 0.0003
SEGNALI = [(2.0, 2.5), (3.0, 2.5), (4.0, 3.5)]                 # (ZB, ZM); il primo e' l'insieme piu' largo
INGRESSI = [("mercato", 0, 1)] + [("stop", x, w) for x in (0.25, 0.5, 1.0) for w in (1, 3)] + \
           [("limite", x, 3) for x in (0.25, 0.5)]
RAPIDA = [0, 1, 2, 3]
PORTAFOGLI = [(0.0075, 5, 3.0), (0.005, 10, 3.0), (0.0025, 20, 3.0)]

def media(v): return sum(v) / len(v) if v else 0.0
def f(x, n=2): return f"{x:+.{n}f}".replace(".", ",")

def esci(M, x0, d, e, a, rapida):
    """Gestione dalla candela x0 (prima candela in cui lo stop puo' scattare). Ritorna (x, prezzo, motivo, mfe in R)."""
    R = ST * a; stop = e - d * R; mx = e; fase2 = False; mfe = 0.0; mosso = False
    fine = min(len(M.C), x0 + C.TETTO)
    for x in range(x0, fine):
        o, h, l = M.O[x], M.H[x], M.L[x]
        if x > x0 and M.T[x] - M.T[x - 1] > 3 * M5: return x - 1, M.C[x - 1], "buco", mfe
        if not fase2 and x - x0 >= F1: return x - 1, M.C[x - 1], "tempo", mfe
        if (d > 0 and l <= stop) or (d < 0 and h >= stop):
            px = min(stop, o) if d > 0 else max(stop, o)
            return x, px, ("stop iniziale" if not mosso else "trailing"), mfe
        fav = h if d > 0 else l
        if (fav - mx) * d > 0:
            mx = fav; g = (mx - e) * d / a; mfe = max(mfe, (mx - e) * d / R)
            if g >= C.SOGLIA2: fase2 = True
            if g >= C.PAREGGIO:
                dist = (TR + (C.ALLARGA * (g - C.SOGLIA2) if fase2 else 0.0)) * a
                nuovo = mx - d * dist
                nuovo = max(stop, e, nuovo) if d > 0 else min(stop, e, nuovo)
                if (nuovo - stop) * d > 0: stop = nuovo; mosso = True
        if rapida and x - x0 + 1 == rapida and mfe < 0.25:
            return x, M.C[x], "rapida", mfe
    return fine - 1, M.C[fine - 1], "tetto", mfe

def ingresso(M, j, d, a, tipo, xatr, w):
    """Ritorna (indice candela di esecuzione, prezzo, x0 = prima candela di gestione) o None se non eseguito."""
    k = j + 1
    if tipo == "mercato": return k, M.O[k], k
    for x in range(k, min(len(M.C), k + w)):
        if M.T[x] - M.T[j] > (w + 2) * M5: return None
        if tipo == "stop":
            liv = M.C[j] + d * xatr * a
            if (d > 0 and M.H[x] >= liv) or (d < 0 and M.L[x] <= liv):
                px = max(liv, M.O[x]) if d > 0 else min(liv, M.O[x])
                return x, px, x + 1
        else:
            liv = M.C[j] - d * xatr * a
            if (d > 0 and M.L[x] <= liv) or (d < 0 and M.H[x] >= liv):
                px = min(liv, M.O[x]) if d > 0 else max(liv, M.O[x])
                return x, px, x + 1
    return None

class Btc:
    def __init__(self, b):
        self.b = b; ema = []; e = None; k = 2 / 289
        for c in b.C: e = c if e is None else e + k * (c - e); ema.append(e)
        self.ema = ema

def prefissi(v):
    out = [0.0]
    for x in v: out.append(out[-1] + (x or 0.0))
    return out

def caratteristiche(M, j, d, btc, i, z, zb, quante, pa):
    a = M.A[j - 1]; H, L, Cc = M.H, M.L, M.C
    rng = H[j] - L[j]
    chius = ((Cc[j] - L[j]) / rng if d > 0 else (H[j] - Cc[j]) / rng) if rng else 0.5
    ora1 = (Cc[j - 1] - Cc[j - 13]) * d / a if j >= 13 else 0.0
    if d > 0: dist24 = (Cc[j] - max(H[max(0, j - 288):j])) / a
    else: dist24 = (min(L[max(0, j - 288):j]) - Cc[j]) / a
    n7 = min(j, 2016); vol_rel = a / ((pa[j] - pa[j - n7]) / n7) if n7 > 100 else 1.0
    trend_btc = (btc.b.C[i] / btc.ema[i] - 1) * 100 * d
    return {"forza moneta (z ATR)": z, "forza BTC (z ATR)": zb, "chiusura nella candela (1 = sull'estremo)": chius,
            "ampiezza candela / ATR": rng / a, "movimento ora prima (ATR, nel verso)": ora1,
            "oltre estremo 24h (ATR, >0 = nuovo estremo)": dist24, "volatilita' moneta / media 7 gg": vol_rel,
            "BTC rispetto media 24h (%, nel verso)": trend_btc, "monete che scattano insieme": quante,
            "ora UTC": time.gmtime(M.T[j]).tm_hour}

def main():
    SP = spread(); lista = ["XBT"] + V.LIQUIDE12 + V.NUOVE; serie = {}
    for m in lista:
        b = C.scarica_5m(m)
        if len(b) >= 100000: serie[m] = C.Serie(m, b, SP.get(m, SPREAD_DEFAULT))
    btcS = serie.pop("XBT"); btc = Btc(btcS); monete = list(serie.values())
    pa = {M.m: prefissi(M.A) for M in monete}
    liq = [serie[m] for m in V.LIQUIDE12 if m in serie]
    t0 = INIZIO_TEST; t1 = min(M.T[-1] for M in liq + [btcS]) - 86400
    taglio = t0 + (t1 - t0) * 0.6; giorni = (t1 - t0) / 86400; durata = giorni / 365
    anni = list(range(time.gmtime(t0).tm_year, time.gmtime(t1).tm_year + 1))
    d_ = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nDal {d_(t0)} al {d_(t1)} (crollo 2022 escluso); prova fino al {d_(taglio)}. {len(monete)} monete.\n", flush=True)
    LIQ = set(V.LIQUIDE12)

    # ---------- segnali (insieme piu' largo) ----------
    zb0, zm0 = SEGNALI[0]
    segnali = {}
    for verso in (1, -1):
        out = []
        for i in C.eventi(btcS, zb0, verso):
            t = btcS.T[i]
            if not t0 <= t <= t1: continue
            zb = (btcS.C[i] - btcS.C[i - 1]) * verso / btcS.A[i - 1]; c = []
            for M in monete:
                j = M.idx.get(t)
                if j is None or j < 300 or j + 6 >= len(M.C) or not M.A[j - 1] or M.H[j] == M.L[j]: continue
                if M.T[j + 1] != t + M5: continue
                z = (M.C[j] - M.C[j - 1]) * verso / M.A[j - 1]
                if z > zm0 and 0.002 <= ST * M.A[j] / M.C[j] <= 0.10: c.append((M, j, z))
            for M, j, z in c: out.append((M, j, z, zb, i, len(c)))
        segnali[verso] = out
        print(f"Segnali {'LONG' if verso > 0 else 'SHORT'} con ZB {zb0:g} / ZM {zm0:g}: {len(out)} = {len(out) / giorni:.1f} al giorno", flush=True)

    def opera(verso, tipo, xatr, w, rapida, feat=False):
        ops = []
        for M, j, z, zb, i, quante in segnali[verso]:
            a = M.A[j]; r = ingresso(M, j, verso, a, tipo, xatr, w)
            if r is None: continue
            xe, e, x0 = r
            if x0 >= len(M.C) - 2: continue
            if tipo != "mercato" and (M.C[xe] - (e - verso * ST * a)) * verso <= 0:      # chiusa gia' oltre lo stop
                x, px, mot, mfe = xe, M.C[xe], "stop iniziale", 0.0
            else:
                x, px, mot, mfe = esci(M, x0, verso, e, a, rapida)
            pct = ST * a / e; lordo = (px - e) * verso / (ST * a)
            ore = (M.T[x] + M5 - M.T[xe]) / 3600
            fund = FUNDING_ORA * ore + (SLIP_STOP if mot in ("stop iniziale", "trailing") else 0.0)
            if tipo == "mercato": costo = 2 * COSTO + M.sp + RITARDO + fund
            elif tipo == "stop": costo = 2 * COSTO + M.sp + SLIP_INGRESSO + fund
            else: costo = MAKER + TAKER_REALE + M.sp / 2 + fund
            netto = lordo - costo / pct
            o = (M.T[xe], M.T[x] + M5, M.m, z, pct, lordo, netto, netto, zb, mot, mfe)
            if feat: o = o + (caratteristiche(M, j, verso, btc, i, z, zb, quante, pa[M.m]),)
            ops.append(o)
        return ops

    # ---------- A) analisi degli ingressi sbagliati ----------
    print("\n================ A) INGRESSI SBAGLIATI (segnali ZB 3 / ZM 2,5, ingresso a mercato, uscita Rev 1) ================")
    print("'sbagliata' = stop iniziale senza aver mai toccato +0,25 R. Quintili calcolati sulla prova, 29 monete.")
    for verso in (-1, 1):
        ops = [o for o in opera(verso, "mercato", 0, 1, 0, feat=True) if o[8] > 3.0 and o[3] > 2.5]
        sb = lambda o: o[9] == "stop iniziale" and o[10] < 0.25
        pr = [o for o in ops if o[0] < taglio]; ve = [o for o in ops if o[0] >= taglio]
        print(f"\n--- {'SHORT' if verso < 0 else 'LONG'}: {len(ops)} operazioni, sbagliate {media([sb(o) for o in ops]) * 100:.0f} %, "
              f"lordo {f(media([o[5] for o in ops]))}, netto taker {f(media([o[6] for o in ops]))} ---")
        print(f"   {'caratteristica / quintile':<48}{'n':>6}{'sbagl.':>8}{'lordo':>7}{'netto':>7}{'| verif: n':>11}{'sbagl.':>8}{'netto':>7}")
        for nome in ops[0][11]:
            vals = sorted(o[11][nome] for o in pr)
            if not vals: continue
            soglie = [vals[int(len(vals) * q / 5)] for q in range(1, 5)]
            def classe(v): return bisect.bisect_right(soglie, v)
            print(f"   {nome}")
            for q in range(5):
                gp = [o for o in pr if classe(o[11][nome]) == q]; gv = [o for o in ve if classe(o[11][nome]) == q]
                lo = vals[0] if q == 0 else soglie[q - 1]; hi = soglie[q] if q < 4 else vals[-1]
                if not gp and not gv: continue
                print(f"      {f'{lo:.2f} / {hi:.2f}'.replace('.', ','):<45}{len(gp):>6}{media([sb(o) for o in gp]) * 100:>7.0f}%"
                      f"{f(media([o[5] for o in gp])):>7}{f(media([o[6] for o in gp])):>7}{len(gv):>11}"
                      f"{media([sb(o) for o in gv]) * 100:>7.0f}%{f(media([o[6] for o in gv])):>7}", flush=True)

    # ---------- B) tipi di ingresso e uscita rapida ----------
    print("\n================ B) INGRESSO (mercato / stop / limite) x USCITA RAPIDA ================")
    print("R netto medio per operazione (stop d'ingresso = taker, limite = maker). Scelta sulla colonna 'prova liq'.")
    risultati = []
    for verso in (-1, 1):
        nome_v = "SHORT" if verso < 0 else "LONG"
        print(f"\n--- {nome_v} ---")
        print(f"   {'ZB  ZM  ingresso          rapida':<38}{'op/g':>6}{'esegu':>6}{'lordo':>7}{'netto':>7}{'prova liq':>10}"
              f"{'verif liq':>10}{'nuove':>7}{'-top10':>7}{'vinte':>6}")
        for (tipo, xatr, w), rapida in itertools.product(INGRESSI, RAPIDA):
            tutte = opera(verso, tipo, xatr, w, rapida)
            for zb, zm in SEGNALI:
                ops = [o for o in tutte if o[8] > zb and o[3] > zm]
                nseg = sum(1 for s in segnali[verso] if s[3] > zb and s[2] > zm)
                if len(ops) < 30: continue
                net = sorted(o[6] for o in ops)
                pl = [o[6] for o in ops if o[2] in LIQ and o[0] < taglio]
                vl = [o[6] for o in ops if o[2] in LIQ and o[0] >= taglio]
                nu = [o[6] for o in ops if o[2] not in LIQ]
                nome = f"{zb:g}  {zm:g}  {tipo} {xatr:g}/{w}  " + (f"{rapida * 5} min" if rapida else "no")
                risultati.append((verso, zb, zm, tipo, xatr, w, rapida, media(pl), len(ops) / giorni))
                print(f"   {nome:<38}{len(ops) / giorni:>6.1f}{len(ops) / max(nseg, 1) * 100:>5.0f}%{f(media([o[5] for o in ops])):>7}"
                      f"{f(media(net)):>7}{f(media(pl)):>10}{f(media(vl)):>10}{f(media(nu)):>7}{f(media(net[:-10])):>7}"
                      f"{media([x > 0 for x in net]) * 100:>5.0f}%".replace(".", ","), flush=True)

    # ---------- C) portafoglio: piu' operazioni ----------
    print("\n================ C) PORTAFOGLIO (migliore in prova per verso) ================")
    scelte = []
    for verso in (-1, 1):
        cand = [r for r in risultati if r[0] == verso]
        scelte.append(("migliore", max(cand, key=lambda r: r[7])))
        freq = [r for r in cand if r[8] >= 5]
        if freq: scelte.append(("migliore con almeno 5 operazioni/giorno", max(freq, key=lambda r: r[7])))
    def intest():
        print(f"   {'':<40}{'op/g':>6}{'giorni':>7}{'netto':>7}{'-top10':>7}{'annuo':>8}{'calo':>6}" + "".join(f"{a:>7}" for a in anni))
    def riga(nome, ops):
        prese, cap, calo, curva = C.portafoglio(ops, 6, t0, t1)
        if not prese: print(f"   {nome:<40} nessuna"); return 0, 0, -1, -1
        net = sorted(o[6] for o in prese); annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
        gg = len({int(o[0] // 86400) for o in prese})
        def valore(t):
            v = 1.0
            for tt, c in curva:
                if tt <= t: v = c
                else: break
            return v
        celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(max(t0, calendar.timegm((a, 1, 1, 0, 0, 0)))) - 1) * 100:>+6.0f}%" for a in anni)
        print(f"   {nome:<40}{len(prese) / giorni:>6.1f}{gg / giorni * 100:>6.0f}%{f(media(net)):>7}{f(media(net[:-10])):>7}"
              f"{annuo * 100:>+7.1f}%{calo * 100:>+5.0f}%{celle}".replace(".", ","), flush=True)
        return media(net), media(net[:-10]), annuo, calo
    verdetti = []
    ops_v = {}
    for etichetta, (verso, zb, zm, tipo, xatr, w, rapida, _, _) in scelte:
        nome_v = ("SHORT" if verso < 0 else "LONG") + (" frequente" if etichetta != "migliore" else "")
        print(f"\n--- {nome_v} ({etichetta}): ZB {zb:g}, ZM {zm:g}, ingresso {tipo} {xatr:g} ATR entro {w}, uscita rapida "
              f"{(str(rapida * 5) + ' min') if rapida else 'no'} ---")
        ops = [o for o in opera(verso, tipo, xatr, w, rapida) if o[8] > zb and o[3] > zm]
        ops_v[nome_v] = ops
        intest()
        for ris, mx, lev in PORTAFOGLI:
            C.RISCHIO, C.MAX_POS, C.LEVA = ris, mx, lev
            etich = f"{ris * 100:.2f} %, {mx} pos, leva {lev:g}".replace(".", ",")
            riga(f"29 monete  {etich}", ops)
            r = riga(f"17 NUOVE   {etich}", [o for o in ops if o[2] not in LIQ])
            if (ris, mx) == (0.005, 10): verdetti.append((nome_v, r))
    for coppia in (("LONG", "SHORT"), ("LONG frequente", "SHORT frequente")):
        if not all(c in ops_v for c in coppia): continue
        print(f"\n--- {coppia[0]} + {coppia[1]} insieme (29 monete) ---")
        intest()
        for ris, mx, lev in PORTAFOGLI:
            C.RISCHIO, C.MAX_POS, C.LEVA = ris, mx, lev
            riga(f"{ris * 100:.2f} %, {mx} pos, leva {lev:g}".replace(".", ","), ops_v[coppia[0]] + ops_v[coppia[1]])
    print("\n=== VERDETTO sulle 17 nuove (netto > +0,05, senza 10 > 0, annuo > 0, calo > -20 %, portafoglio 0,5 % / 10) ===")
    for nome, (n, n10, an, ca) in verdetti:
        ok = n > 0.05 and n10 > 0 and an > 0 and ca > -0.20
        print(f"   {nome:<16} netto {f(n, 3)}  senza 10 {f(n10, 3)}  annuo {an * 100:+.1f} %  calo {ca * 100:.0f} %  -> "
              f"{'PROMOSSA' if ok else 'BOCCIATA'}".replace(".", ","))

if __name__ == "__main__":
    main()
