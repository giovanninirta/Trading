#!/usr/bin/env python3
"""
STATISTICHE CECCHINO 5 MINUTI - Rev 1  (sulla migliore di cecchino_5m_rev1.py: SHORT, ZB 4, ZM 3,5, ST 2, TR 1,5, F1 48)
1) Portafoglio sulle 29 monete (maker e taker): operazioni al giorno, curva del capitale (salvata in
   ../risultati/curva_cecchino_5m_rev1.csv), giorni positivi / negativi, rendimento giornaliero.
2) Statistica delle operazioni prese: vinte / perse, motivo d'uscita (stop iniziale, pareggio, trailing, tempo),
   R medio per motivo, MFE (massimo guadagno toccato, in R) e MAE (massima perdita toccata) di vinte e perse,
   durata, dove le perse arrivano prima di girarsi.
3) Uscite alternative sugli STESSI ingressi (tutti i candidati, 29 monete, senza portafoglio): R medio netto maker e
   taker in prova e verifica. Serve a capire se la gestione dell'uscita si puo' migliorare: si sceglie in prova,
   si guarda la verifica.
Uso (nella cartella dati):  python ../statistiche_cecchino_5m_rev1.py
"""
import calendar, csv, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cecchino_5m_rev1 as C
from cecchino_5m_rev1 import M5, COSTO, FUNDING_ORA, RITARDO, MAKER, TAKER_REALE, SLIP_STOP
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
import verifica_monete_nuove_btc_guida_rev1 as V

VERSO, ZB, ZM, ST, TR, F1 = -1, 4.0, 3.5, 2.0, 1.5, 48

def gestione(M, k, d, e, a, st=ST, be=1.0, ts=1.0, td=TR, tp=None, tmax=F1, fase2_on=True, tetto=288):
    """Uscita generica (unita' ATR). be = pareggio (None = mai), ts/td = avvio e distanza trailing (td None = niente),
    tp = obiettivo fisso, tmax = limite in candele se non in fase 2. Ritorna (x, prezzo, motivo, mfe, mae) in R."""
    R = st * a; stop = e - d * st * a; mx = e; fase2 = False; mfe = mae = 0.0; mosso = False
    fine = min(len(M.C), k + tetto)
    for x in range(k, fine):
        o, h, l = M.O[x], M.H[x], M.L[x]
        if x > k and M.T[x] - M.T[x - 1] > 3 * M5: return x - 1, M.C[x - 1], "buco", mfe, mae
        if not fase2 and x - k >= tmax: return x - 1, M.C[x - 1], "tempo", mfe, mae
        fav, avv = (h, l) if d > 0 else (l, h)
        if (d > 0 and l <= stop) or (d < 0 and h >= stop):
            mae = max(mae, (e - stop) * d / R)
            px = min(stop, o) if d > 0 else max(stop, o)
            g = (px - e) * d / R
            mot = "stop iniziale" if not mosso else ("pareggio" if abs(g) < 0.05 else "trailing")
            return x, px, mot, mfe, mae
        mae = max(mae, (e - avv) * d / R)
        if tp is not None and (fav - e) * d >= tp * a:
            return x, e + d * tp * a, "obiettivo", max(mfe, tp * a / R), mae
        if (fav - mx) * d > 0:
            mx = fav; g = (mx - e) * d / a; mfe = max(mfe, (mx - e) * d / R)
            if fase2_on and g >= C.SOGLIA2: fase2 = True
            meglio = (lambda p, q: max(p, q)) if d > 0 else (lambda p, q: min(p, q))
            nuovo = stop
            if be is not None and g >= be: nuovo = meglio(nuovo, e)
            if td is not None and g >= ts:
                dist = (td + (C.ALLARGA * (g - C.SOGLIA2) if fase2 else 0.0)) * a
                nuovo = meglio(nuovo, mx - d * dist)
            if (nuovo - stop) * d > 0: stop = nuovo; mosso = True
    return fine - 1, M.C[fine - 1], "tetto", mfe, mae

def netti(M, e, px, a, st, ore, mot):
    pct = st * a / e; lordo = (px - e) * VERSO / (st * a)
    fund = FUNDING_ORA * ore + (SLIP_STOP if mot in ("stop iniziale", "pareggio", "trailing") else 0.0)
    return lordo, lordo - (2 * COSTO + M.sp + RITARDO + fund) / pct, lordo - (MAKER + TAKER_REALE + M.sp / 2 + fund) / pct

def media(v): return sum(v) / len(v) if v else 0.0
def f(x, n=2): return f"{x:+.{n}f}".replace(".", ",")

def main():
    SP = spread(); lista = ["XBT"] + V.LIQUIDE12 + V.NUOVE; serie = {}
    for m in lista:
        b = C.scarica_5m(m)
        if len(b) >= 100000: serie[m] = C.Serie(m, b, SP.get(m, SPREAD_DEFAULT))
    btc = serie.pop("XBT"); monete = list(serie.values())
    liq = [serie[m] for m in V.LIQUIDE12 if m in serie]
    t0 = max(M.T[0] for M in liq + [btc]) + 86400; t1 = min(M.T[-1] for M in liq + [btc]) - 86400
    taglio = t0 + (t1 - t0) * 0.6; giorni = (t1 - t0) / 86400; durata = giorni / 365
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nSHORT ZB {ZB:g} ZM {ZM:g} ST {ST:g} TR {TR:g} F1 {F1} - 29 monete - dal {d(t0)} al {d(t1)} ({giorni:.0f} giorni)\n")

    # ---------- candidati con statistiche d'uscita (regola attuale) ----------
    cand = []
    for i in C.eventi(btc, ZB, VERSO):
        t = btc.T[i]; zb = (btc.C[i] - btc.C[i - 1]) * VERSO / btc.A[i - 1]
        if not t0 <= t <= t1: continue
        for M in monete:
            j = M.idx.get(t)
            if j is None or j < 30 or j + 2 >= len(M.C) or not M.A[j - 1] or M.H[j] == M.L[j]: continue
            if M.T[j + 1] != t + M5: continue
            z = (M.C[j] - M.C[j - 1]) * VERSO / M.A[j - 1]
            if z <= ZM: continue
            k = j + 1; e = M.O[k]; a = M.A[j]; pct = ST * a / e
            if not 0.002 <= pct <= 0.10: continue
            cand.append((M, k, e, a, z, zb))
    print(f"Segnali candidati: {len(cand)} ({len(cand) / durata:.0f}/anno, {len(cand) / giorni:.2f}/giorno)")

    def esegui(M, k, e, a, **kw):
        x, px, mot, mfe, mae = gestione(M, k, VERSO, e, a, **kw)
        ore = (M.T[x] + M5 - M.T[k]) / 3600
        lo, nt, nm = netti(M, e, px, a, kw.get("st", ST), ore, mot)
        return dict(t=M.T[k], fine=M.T[x] + M5, m=M.m, z=0, pct=kw.get("st", ST) * a / e, lordo=lo, nt=nt, nm=nm,
                    mot=mot, mfe=mfe, mae=mae, min=(M.T[x] + M5 - M.T[k]) / 60)

    base = []
    for M, k, e, a, z, zb in cand:
        o = esegui(M, k, e, a); o["z"] = z; base.append(o)
    # controllo: deve coincidere con cecchino_5m_rev1
    ops_ref = C.operazioni(btc, monete, (ZB, ZM, ST, TR, F1), VERSO)
    ops_ref = [o for o in ops_ref if t0 <= o[0] <= t1]
    print(f"Controllo con cecchino_5m_rev1: lordo medio {f(media([o[5] for o in ops_ref]), 3)} contro {f(media([o['lordo'] for o in base]), 3)}\n")

    # ---------- portafoglio ----------
    for nome, sc in (("MAKER", 7), ("TAKER", 6)):
        prese, cap, calo, curva = C.portafoglio(ops_ref, sc, t0, t1)
        annuo = cap ** (1 / durata) - 1
        print(f"=== PORTAFOGLIO {nome} (rischio 0,75 %, max 5, leva 3) ===")
        print(f"   operazioni prese {len(prese)} = {len(prese) / durata:.0f}/anno = {len(prese) / giorni:.2f}/giorno; "
              f"capitale x{cap:.2f}; annuo {annuo * 100:+.1f} %; calo massimo {calo * 100:.0f} %".replace(".", ","))
        # giornaliero
        per_g = {}; v = 1.0; idx = 0; curva = sorted(curva)
        g0 = int(t0 // 86400); g1 = int(t1 // 86400); serie_g = []
        for g in range(g0, g1 + 1):
            while idx < len(curva) and curva[idx][0] < (g + 1) * 86400: v = curva[idx][1]; idx += 1
            serie_g.append((g, v))
        rend = [serie_g[q][1] / serie_g[q - 1][1] - 1 for q in range(1, len(serie_g))]
        attivi = [r for r in rend if r != 0]
        print(f"   giorni {len(rend)}: con operazioni chiuse {len(attivi)} ({len(attivi) / len(rend) * 100:.0f} %), "
              f"positivi {sum(r > 0 for r in rend)}, negativi {sum(r < 0 for r in rend)}, "
              f"oltre +1 % {sum(r >= 0.01 for r in rend)}, sotto -1 % {sum(r <= -0.01 for r in rend)}")
        print(f"   rendimento medio al giorno {media(rend) * 100:+.3f} % (obiettivo +1 %); migliore {max(rend) * 100:+.1f} %, "
              f"peggiore {min(rend) * 100:+.1f} %".replace(".", ","))
        mesi = {}
        for g, v in serie_g: mesi.setdefault(time.strftime("%Y-%m", time.gmtime(g * 86400)), []).append(v)
        chiavi = sorted(mesi); prec = 1.0; celle = []
        for c in chiavi: celle.append(f"{c[2:]} {(mesi[c][-1] / prec - 1) * 100:+.0f}%"); prec = mesi[c][-1]
        print("   mesi: " + "  ".join(celle).replace(".", ","))
        if nome == "MAKER":
            os.makedirs("../risultati", exist_ok=True)
            with open("../risultati/curva_cecchino_5m_rev1.csv", "w", newline="") as fh:
                w = csv.writer(fh); w.writerow(["data", "capitale_maker"])
                for g, v in serie_g: w.writerow([time.strftime("%Y-%m-%d", time.gmtime(g * 86400)), f"{v:.5f}"])
            prese_maker = {(o[0], o[2]) for o in prese}
        print()

    # ---------- statistica delle operazioni prese (maker) ----------
    ops = [o for o in base if (o["t"], o["m"]) in prese_maker]
    print(f"=== OPERAZIONI PRESE NEL PORTAFOGLIO MAKER: {len(ops)} ===")
    vinte = [o for o in ops if o["nm"] > 0]; perse = [o for o in ops if o["nm"] <= 0]
    print(f"   vinte {len(vinte)} ({len(vinte) / len(ops) * 100:.0f} %), R netto medio {f(media([o['nm'] for o in vinte]))}, "
          f"mediana {f(sorted(o['nm'] for o in vinte)[len(vinte) // 2])}, durata mediana {sorted(o['min'] for o in vinte)[len(vinte) // 2]:.0f} min")
    print(f"   perse {len(perse)} ({len(perse) / len(ops) * 100:.0f} %), R netto medio {f(media([o['nm'] for o in perse]))}, "
          f"durata mediana {sorted(o['min'] for o in perse)[len(perse) // 2]:.0f} min")
    tot = sum(o["nm"] for o in ops); srt = sorted(ops, key=lambda o: -o["nm"])
    print(f"   somma R netto {f(tot, 1)}; le 10 migliori valgono {f(sum(o['nm'] for o in srt[:10]), 1)} R, le 30 migliori {f(sum(o['nm'] for o in srt[:30]), 1)} R")
    print("   distribuzione R netto: " + "  ".join(
        f"{lab}: {sum(1 for o in ops if lo <= o['nm'] < hi)}" for lab, lo, hi in
        (("< -1,2", -99, -1.2), ("-1,2/-0,8", -1.2, -0.8), ("-0,8/-0,2", -0.8, -0.2), ("-0,2/0", -0.2, 0), ("0/0,5", 0, 0.5),
         ("0,5/1", 0.5, 1), ("1/2", 1, 2), ("2/4", 2, 4), ("4/8", 4, 8), (">= 8", 8, 999))))
    print(f"\n   {'motivo uscita':<16}{'n':>5}{'quota':>7}{'lordo':>8}{'netto':>8}{'vinte':>7}{'MFE':>7}{'MAE':>7}{'min':>6}")
    for mot in ("stop iniziale", "pareggio", "trailing", "tempo", "tetto", "buco"):
        g = [o for o in ops if o["mot"] == mot]
        if not g: continue
        print(f"   {mot:<16}{len(g):>5}{len(g) / len(ops) * 100:>6.0f}%{f(media([o['lordo'] for o in g])):>8}{f(media([o['nm'] for o in g])):>8}"
              f"{sum(o['nm'] > 0 for o in g) / len(g) * 100:>6.0f}%{media([o['mfe'] for o in g]):>7.2f}{media([o['mae'] for o in g]):>7.2f}"
              f"{sorted(o['min'] for o in g)[len(g) // 2]:>6.0f}".replace(".", ","))
    print("   (MFE = massimo guadagno toccato in R, MAE = massima perdita toccata in R; R = stop = 2 ATR 5m)")
    print("\n   PERSE: fin dove erano arrivate a favore prima di girarsi (MFE)")
    for lab, lo, hi in (("mai sopra +0,25 R", 0, 0.25), ("+0,25/+0,5 R", 0.25, 0.5), ("+0,5/+1 R", 0.5, 1), ("+1/+2 R", 1, 2), ("oltre +2 R", 2, 99)):
        g = [o for o in perse if lo <= o["mfe"] < hi]
        print(f"      {lab:<20}{len(g):>5} ({len(g) / len(perse) * 100:>3.0f} %)  R netto medio {f(media([o['nm'] for o in g]))}")
    print("   VINTE: quanto hanno restituito dal massimo (MFE - risultato lordo)")
    rest = [o["mfe"] - o["lordo"] for o in vinte]
    print(f"      massimo medio toccato {f(media([o['mfe'] for o in vinte]))} R, chiuse in media a {f(media([o['lordo'] for o in vinte]))} R lordo, "
          f"restituito in media {media(rest):.2f} R".replace(".", ","))
    print("   Ingressi: R netto per forza della moneta (z) e minuti del giorno UTC")
    for lab, lo, hi in (("z 3,5-4,5", 3.5, 4.5), ("z 4,5-6", 4.5, 6), ("z oltre 6", 6, 99)):
        g = [o for o in ops if lo <= o["z"] < hi]
        print(f"      {lab:<12}{len(g):>5}  R netto {f(media([o['nm'] for o in g]))}")
    for lab, lo, hi in (("00-08 UTC", 0, 8), ("08-13 UTC", 8, 13), ("13-17 UTC", 13, 17), ("17-24 UTC", 17, 24)):
        g = [o for o in ops if lo <= time.gmtime(o["t"]).tm_hour < hi]
        print(f"      {lab:<12}{len(g):>5}  R netto {f(media([o['nm'] for o in g]))}")

    # ---------- uscite alternative sugli stessi ingressi ----------
    print(f"\n=== USCITE ALTERNATIVE sugli stessi {len(cand)} ingressi (tutti i candidati, senza portafoglio; R = 2 ATR) ===")
    print(f"   {'gestione':<46}{'lordo':>7}{'maker':>7}{'prova':>7}{'verif':>7}{'-top10':>7}{'taker':>7}{'vinte':>6}{'min':>5}")
    varianti = [
        ("ATTUALE (pareggio 1, trail 1,5 da 1, fase 2)", {}),
        ("senza pareggio (trail 1,5 da 1)", dict(be=None)),
        ("pareggio a 2 ATR, trail da 2", dict(be=2.0, ts=2.0)),
        ("trailing 1,0", dict(td=1.0)),
        ("trailing 2,5", dict(td=2.5)),
        ("trailing 1,5 che parte da 2 ATR", dict(ts=2.0)),
        ("obiettivo fisso 1 R (2 ATR), niente trailing", dict(be=None, td=None, tp=2.0)),
        ("obiettivo fisso 1,5 R", dict(be=None, td=None, tp=3.0)),
        ("obiettivo fisso 2 R", dict(be=None, td=None, tp=4.0)),
        ("obiettivo fisso 3 R", dict(be=None, td=None, tp=6.0)),
        ("solo stop + tempo 15 min", dict(be=None, td=None, tmax=3, fase2_on=False)),
        ("solo stop + tempo 30 min", dict(be=None, td=None, tmax=6, fase2_on=False)),
        ("solo stop + tempo 1 h", dict(be=None, td=None, tmax=12, fase2_on=False)),
        ("solo stop + tempo 4 h", dict(be=None, td=None, tmax=48, fase2_on=False)),
        ("attuale ma limite fase 1 = 30 min", dict(tmax=6)),
        ("attuale ma limite fase 1 = 1 h", dict(tmax=12)),
        ("stop 1 ATR (R diverso!), resto attuale", dict(st=1.0)),
        ("stop 3 ATR (R diverso!), resto attuale", dict(st=3.0)),
        ("pareggio 1 + obiettivo 2 R", dict(td=None, tp=4.0)),
        ("trailing 1,5 senza fase 2, tetto 24 h", dict(fase2_on=False, tmax=288)),
    ]
    for nome, kw in varianti:
        rr = [esegui(M, k, e, a, **kw) for M, k, e, a, z, zb in cand]
        nm = sorted(o["nm"] for o in rr)
        pr = [o["nm"] for o in rr if o["t"] < taglio]; ve = [o["nm"] for o in rr if o["t"] >= taglio]
        print(f"   {nome:<46}{f(media([o['lordo'] for o in rr])):>7}{f(media(nm)):>7}{f(media(pr)):>7}{f(media(ve)):>7}"
              f"{f(media(nm[:-10])):>7}{f(media([o['nt'] for o in rr])):>7}{sum(x > 0 for x in nm) / len(nm) * 100:>5.0f}%"
              f"{sorted(o['min'] for o in rr)[len(rr) // 2]:>5.0f}", flush=True)
    print("\nLettura: si sceglie guardando la colonna 'prova'; 'verif' dice se regge. Il maker resta ottimista (limite sempre eseguito).")

if __name__ == "__main__":
    main()
