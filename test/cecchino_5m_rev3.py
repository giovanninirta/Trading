#!/usr/bin/env python3
"""
CECCHINO 5 MINUTI - Rev 3  (perpetui Kraken, 29 monete, candele 5m, dal 01/01/2023: crollo 2022 escluso)
Richiesta: stop piu' largo (1 % FISSO dal prezzo d'ingresso) e limite di esposizione portato da 3 a 10 volte il capitale.
Confronto:
  STOP     "2 ATR" (come Rev 1-2)  |  "1 %" fisso
  USCITA   per lo stop 1 %, due versioni:
             "ATR"  pareggio a +1 ATR, trailing 1,5 ATR, fase 2 da +3 ATR (come prima, ma con stop piu' lontano)
             "in R" tutto in proporzione allo stop: pareggio a +0,5 R, trailing 0,75 R, fase 2 da +1,5 R
                    (= le regole di prima con 1 ATR sostituito da mezzo stop)
           limite fase 1: 48 candele (4 h); fase 2 senza limite (tetto 24 h)
  SEGNALE  BTC oltre ZB ATR sulla candela 5m, monete oltre ZM ATR: (3; 2,5) e (4; 3,5)
  INGRESSO a mercato, oppure ordine STOP 0,25 / 0,5 ATR oltre la chiusura del segnale entro 1 o 3 candele
  PORTAFOGLIO rischio 0,75 % / 5 pos / leva 3 (come prima), 0,75 % / 10 / leva 10, 0,5 % / 20 / leva 10,
              0,25 % / 30 / leva 10
Dati: esclusi i segnali con ATR della moneta sotto lo 0,03 % del prezzo o forza oltre 50 ATR (candele ferme/errate).
Costi come Rev 2 (taker 0,07 % x2 + spread reale + ritardo 0,05 % a mercato / 0,03 % con stop, +0,02 % sulle uscite
in stop, funding 0,01 %/8h).
Metodo: scelta sulla PROVA (primo 60 % del 2023-2026) delle 12 liquide; si guarda verifica e 17 nuove.
CRITERIO FISSATO PRIMA (17 nuove): netto > +0,05 R, senza le 10 migliori > 0, portafoglio 0,5 % / 20 / leva 10
con annuo > 0 e calo > -20 %.
Uso (nella cartella dati):  python ../cecchino_5m_rev3.py
"""
import calendar, itertools, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cecchino_5m_rev1 as C
from cecchino_5m_rev1 import M5, COSTO, FUNDING_ORA, RITARDO, SLIP_STOP
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
import verifica_monete_nuove_btc_guida_rev1 as V

INIZIO_TEST = calendar.timegm((2023, 1, 1, 0, 0, 0))
TR, F1, SLIP_INGRESSO = 1.5, 48, 0.0003
SEGNALI = [(3.0, 2.5), (4.0, 3.5)]
STOP = [("2 ATR", "ATR"), ("1 %", "ATR"), ("1 %", "in R")]
INGRESSI = [("mercato", 0, 1), ("stop", 0.25, 1), ("stop", 0.25, 3), ("stop", 0.5, 1), ("stop", 0.5, 3)]
PORTAFOGLI = [(0.0075, 5, 3.0), (0.0075, 10, 10.0), (0.005, 20, 10.0), (0.0025, 30, 10.0)]
VERDETTO_PF = (0.005, 20, 10.0)

def media(v): return sum(v) / len(v) if v else 0.0
def f(x, n=2): return f"{x:+.{n}f}".replace(".", ",")

def esci(M, x0, d, e, R, u):
    """Gestione dalla candela x0. R = distanza dello stop (prezzo), u = unita' per pareggio/trailing/fase 2."""
    stop = e - d * R; mx = e; fase2 = False; mfe = 0.0; mosso = False
    fine = min(len(M.C), x0 + C.TETTO)
    for x in range(x0, fine):
        o, h, l = M.O[x], M.H[x], M.L[x]
        if x > x0 and M.T[x] - M.T[x - 1] > 3 * M5: return x - 1, M.C[x - 1], "buco"
        if not fase2 and x - x0 >= F1: return x - 1, M.C[x - 1], "tempo"
        if (d > 0 and l <= stop) or (d < 0 and h >= stop):
            return x, (min(stop, o) if d > 0 else max(stop, o)), ("stop iniziale" if not mosso else "trailing")
        fav = h if d > 0 else l
        if (fav - mx) * d > 0:
            mx = fav; g = (mx - e) * d / u
            if g >= C.SOGLIA2: fase2 = True
            if g >= C.PAREGGIO:
                dist = (TR + (C.ALLARGA * (g - C.SOGLIA2) if fase2 else 0.0)) * u
                nuovo = mx - d * dist
                nuovo = max(stop, e, nuovo) if d > 0 else min(stop, e, nuovo)
                if (nuovo - stop) * d > 0: stop = nuovo; mosso = True
    return fine - 1, M.C[fine - 1], "tetto"

def ingresso(M, j, d, a, tipo, xatr, w):
    k = j + 1
    if tipo == "mercato": return k, M.O[k], k
    liv = M.C[j] + d * xatr * a
    for x in range(k, min(len(M.C), k + w)):
        if M.T[x] - M.T[j] > (w + 2) * M5: return None
        if (d > 0 and M.H[x] >= liv) or (d < 0 and M.L[x] <= liv):
            return x, (max(liv, M.O[x]) if d > 0 else min(liv, M.O[x])), x + 1
    return None

def main():
    SP = spread(); lista = ["XBT"] + V.LIQUIDE12 + V.NUOVE; serie = {}
    for m in lista:
        b = C.scarica_5m(m)
        if len(b) >= 100000: serie[m] = C.Serie(m, b, SP.get(m, SPREAD_DEFAULT))
    btc = serie.pop("XBT"); monete = list(serie.values()); LIQ = set(V.LIQUIDE12)
    liq = [serie[m] for m in V.LIQUIDE12 if m in serie]
    t0 = INIZIO_TEST; t1 = min(M.T[-1] for M in liq + [btc]) - 86400
    taglio = t0 + (t1 - t0) * 0.6; giorni = (t1 - t0) / 86400; durata = giorni / 365
    anni = list(range(time.gmtime(t0).tm_year, time.gmtime(t1).tm_year + 1))
    d_ = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nDal {d_(t0)} al {d_(t1)} (crollo 2022 escluso); prova fino al {d_(taglio)}. {len(monete)} monete.", flush=True)

    zb0, zm0 = min(s[0] for s in SEGNALI), min(s[1] for s in SEGNALI)
    segnali = {}; scartati = 0
    for verso in (1, -1):
        out = []
        for i in C.eventi(btc, zb0, verso):
            t = btc.T[i]
            if not t0 <= t <= t1: continue
            zb = (btc.C[i] - btc.C[i - 1]) * verso / btc.A[i - 1]
            for M in monete:
                j = M.idx.get(t)
                if j is None or j < 300 or j + 6 >= len(M.C) or not M.A[j - 1] or M.H[j] == M.L[j]: continue
                if M.T[j + 1] != t + M5: continue
                z = (M.C[j] - M.C[j - 1]) * verso / M.A[j - 1]
                if z <= zm0: continue
                if M.A[j - 1] / M.C[j - 1] < 0.0003 or z > 50: scartati += 1; continue
                out.append((M, j, z, zb))
        segnali[verso] = out
    print(f"Segnali (ZB {zb0:g} / ZM {zm0:g}): long {len(segnali[1]) / giorni:.1f}/giorno, short {len(segnali[-1]) / giorni:.1f}/giorno; "
          f"scartati per dati anomali {scartati}".replace(".", ","))
    st_atr = sorted(2 * M.A[j] / M.C[j] * 100 for M, j, z, zb in segnali[-1])
    if st_atr:
        print(f"Per confronto, uno stop di 2 ATR vale in mediana {st_atr[len(st_atr) // 2]:.2f} % del prezzo "
              f"(10 % dei casi sotto {st_atr[len(st_atr) // 10]:.2f} %, 10 % sopra {st_atr[9 * len(st_atr) // 10]:.2f} %)".replace(".", ","))

    def opera(verso, stop_tipo, usc, tipo, xatr, w):
        ops = []
        for M, j, z, zb in segnali[verso]:
            a = M.A[j]; r = ingresso(M, j, verso, a, tipo, xatr, w)
            if r is None: continue
            xe, e, x0 = r
            if x0 >= len(M.C) - 2: continue
            R = 2 * a if stop_tipo == "2 ATR" else 0.01 * e
            pct = R / e
            if not 0.002 <= pct <= 0.10: continue
            u = a if usc == "ATR" else R / 2
            if tipo != "mercato" and (M.C[xe] - (e - verso * R)) * verso <= 0:
                x, px, mot = xe, M.C[xe], "stop iniziale"
            else:
                x, px, mot = esci(M, x0, verso, e, R, u)
            lordo = (px - e) * verso / R
            ore = (M.T[x] + M5 - M.T[xe]) / 3600
            fund = FUNDING_ORA * ore + (SLIP_STOP if mot in ("stop iniziale", "trailing") else 0.0)
            costo = 2 * COSTO + M.sp + (RITARDO if tipo == "mercato" else SLIP_INGRESSO) + fund
            netto = lordo - costo / pct
            ops.append((M.T[xe], M.T[x] + M5, M.m, z, pct, lordo, netto, netto, zb, mot, costo / pct))
        return ops

    print("\n================ A) R NETTO PER OPERAZIONE (tutti i segnali, senza portafoglio) ================")
    print("costo = costi medi in R (con stop piu' largo pesano meno). Scelta sulla colonna 'prova liq'.")
    ris = []
    for verso in (-1, 1):
        print(f"\n--- {'SHORT' if verso < 0 else 'LONG'} ---")
        print(f"   {'stop   uscita  ZB ZM   ingresso':<40}{'op/g':>6}{'lordo':>7}{'costo':>7}{'netto':>7}{'prova liq':>10}"
              f"{'verif liq':>10}{'nuove':>7}{'-top10':>7}{'vinte':>6}{'stop1':>6}")
        for (st, usc), (tipo, xatr, w) in itertools.product(STOP, INGRESSI):
            tutte = opera(verso, st, usc, tipo, xatr, w)
            for zb, zm in SEGNALI:
                ops = [o for o in tutte if o[8] > zb and o[3] > zm]
                if len(ops) < 30: continue
                net = sorted(o[6] for o in ops)
                pl = [o[6] for o in ops if o[2] in LIQ and o[0] < taglio]
                vl = [o[6] for o in ops if o[2] in LIQ and o[0] >= taglio]
                nu = [o[6] for o in ops if o[2] not in LIQ]
                ris.append((verso, st, usc, zb, zm, tipo, xatr, w, media(pl)))
                nome = f"{st:<6} {usc:<6} {zb:g}  {zm:g}  {tipo} {xatr:g}/{w}"
                print(f"   {nome:<40}{len(ops) / giorni:>6.1f}{f(media([o[5] for o in ops])):>7}{media([o[10] for o in ops]):>7.2f}"
                      f"{f(media(net)):>7}{f(media(pl)):>10}{f(media(vl)):>10}{f(media(nu)):>7}{f(media(net[:-10])):>7}"
                      f"{media([x > 0 for x in net]) * 100:>5.0f}%{media([o[9] == 'stop iniziale' for o in ops]) * 100:>5.0f}%".replace(".", ","),
                      flush=True)

    print("\n================ B) PORTAFOGLIO: migliore in prova per verso e per tipo di stop ================")
    def intest():
        print(f"   {'':<42}{'op/g':>6}{'giorni':>7}{'netto':>7}{'-top10':>7}{'annuo':>8}{'calo':>6}{'esp.max':>8}" + "".join(f"{a:>7}" for a in anni))
    def riga(nome, ops):
        prese, cap, calo, curva = C.portafoglio(ops, 6, t0, t1)
        if not prese: print(f"   {nome:<42} nessuna"); return 0, 0, -1, -1
        net = sorted(o[6] for o in prese); annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
        gg = len({int(o[0] // 86400) for o in prese})
        # esposizione massima effettiva (somma posizioni aperte / capitale) e perdita peggiore in un giorno
        eventi_e = sorted([(o[0], C.RISCHIO / o[4]) for o in prese] + [(o[1], -C.RISCHIO / o[4]) for o in prese])
        esp = mx = 0.0
        for _, v in eventi_e: esp += v; mx = max(mx, esp)
        def valore(t):
            v = 1.0
            for tt, c in curva:
                if tt <= t: v = c
                else: break
            return v
        celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(max(t0, calendar.timegm((a, 1, 1, 0, 0, 0)))) - 1) * 100:>+6.0f}%" for a in anni)
        print(f"   {nome:<42}{len(prese) / giorni:>6.1f}{gg / giorni * 100:>6.0f}%{f(media(net)):>7}{f(media(net[:-10])):>7}"
              f"{annuo * 100:>+7.1f}%{calo * 100:>+5.0f}%{mx:>7.1f}x{celle}".replace(".", ","), flush=True)
        return media(net), media(net[:-10]), annuo, calo
    verdetti = []; scelte_ops = {}
    for verso in (-1, 1):
        for st in ("2 ATR", "1 %"):
            cand = [r for r in ris if r[0] == verso and r[1] == st]
            v, st, usc, zb, zm, tipo, xatr, w, _ = max(cand, key=lambda r: r[8])
            nome_v = f"{'SHORT' if verso < 0 else 'LONG'} stop {st}"
            print(f"\n--- {nome_v}: uscita {usc}, ZB {zb:g}, ZM {zm:g}, ingresso {tipo} {xatr:g} ATR entro {w} ---".replace(".", ","))
            ops = [o for o in opera(verso, st, usc, tipo, xatr, w) if o[8] > zb and o[3] > zm]
            scelte_ops[nome_v] = ops
            intest()
            for rs, mxp, lev in PORTAFOGLI:
                C.RISCHIO, C.MAX_POS, C.LEVA = rs, mxp, lev
                et = f"{rs * 100:.2f} %, {mxp} pos, leva {lev:g}".replace(".", ",")
                riga(f"29 monete  {et}", ops)
                r = riga(f"17 NUOVE   {et}", [o for o in ops if o[2] not in LIQ])
                if (rs, mxp, lev) == VERDETTO_PF: verdetti.append((nome_v, r))
    for st in ("2 ATR", "1 %"):
        print(f"\n--- LONG + SHORT insieme, stop {st} (29 monete) ---")
        intest()
        for rs, mxp, lev in PORTAFOGLI:
            C.RISCHIO, C.MAX_POS, C.LEVA = rs, mxp, lev
            riga(f"{rs * 100:.2f} %, {mxp} pos, leva {lev:g}".replace(".", ","), scelte_ops[f"LONG stop {st}"] + scelte_ops[f"SHORT stop {st}"])
    print("\nesp.max = esposizione massima raggiunta (somma delle posizioni aperte / capitale)")
    print("\n=== VERDETTO sulle 17 nuove (netto > +0,05, senza 10 > 0, annuo > 0, calo > -20 %, portafoglio 0,5 % / 20 / leva 10) ===")
    for nome, (n, n10, an, ca) in verdetti:
        ok = n > 0.05 and n10 > 0 and an > 0 and ca > -0.20
        print(f"   {nome:<18} netto {f(n, 3)}  senza 10 {f(n10, 3)}  annuo {an * 100:+.1f} %  calo {ca * 100:.0f} %  -> "
              f"{'PROMOSSA' if ok else 'BOCCIATA'}".replace(".", ","))

if __name__ == "__main__":
    main()
