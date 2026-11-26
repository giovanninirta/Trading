#!/usr/bin/env python3
"""
CECCHINO 29 CON ORDINE STOP D'INGRESSO - Rev 1  (perpetui Kraken, 4 ore, solo long, SOLO DAL 01/01/2023)
Regola identica al bot Rev 8 (Cecchino 29): candela 4h di BTC oltre 2 ATR, monete salite oltre 1,7 ATR, le piu'
forti, max 5 posizioni, stop 1 ATR, pareggio +1 ATR, trailing 1,5 ATR, chiusura a 16 h se non oltre +3 ATR,
fase 2 con trailing che si allarga; rischio 0,75 %, leva max 3.
Cambia SOLO l'ingresso:
  ATTUALE  alla chiusura della candela 4h (+ 0,05 % di ritardo)
  STOP X/W ordine stop X ATR (ATR 4h) sopra la chiusura della candela del segnale, valido W ore: si entra solo se il
           prezzo lo raggiunge (eseguito al livello o all'apertura se ci salta sopra; +0,03 % di slittamento), poi
           stop a 1 ATR SOTTO IL PREZZO D'INGRESSO e gestione identica. Se non si raggiunge, l'operazione salta.
           X = 0,1 / 0,25 / 0,5 / 0,75 ATR, W = 1 / 4 ore. Prezzi a 15 minuti.
Periodo: dal 01/01/2023 (crollo 2022 escluso). Prova = primo 60 %, verifica = ultimo 40 %.
CRITERIO FISSATO PRIMA: una variante STOP e' PROMOSSA se sulle 29 monete batte l'attuale in annuo E in rapporto
annuo/calo, con calo > -20 %, E il suo netto per operazione e' >= all'attuale sia in prova sia in verifica,
E sulle 17 nuove netto > +0,05 R e senza le 10 migliori > 0.
Uso (nella cartella dati):  python ../cecchino_29_stop_ingresso_rev1.py
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, COSTO, FUNDING_ORA
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m
import verifica_monete_nuove_btc_guida_rev1 as V

INIZIO = calendar.timegm((2023, 1, 1, 0, 0, 0))
SLIP_INGRESSO = 0.0003
VARIANTI = [("ATTUALE", None, None)] + [(f"STOP {x:g} ATR / {w} h".replace(".", ","), x, w)
                                       for x in (0.1, 0.25, 0.5, 0.75) for w in (1, 4)]

def media(v): return sum(v) / len(v) if v else 0.0
def f(x, n=3): return f"{x:+.{n}f}".replace(".", ",")

def simula(btc, monete, x_atr, w, t0, t1):
    cap, picco, calo, aperte, ops, curva, saltate = 1.0, 1.0, 0.0, [], [], [], 0
    for i in range(30, len(btc.C)):
        t = btc.T[i]
        if not (t0 <= t <= t1) or not btc.A[i - 1]: continue
        if (btc.C[i] - btc.C[i - 1]) / btc.A[i - 1] <= 2.0: continue
        chiusura = t + V.H4
        for p in sorted(aperte, key=lambda p: p["fine"]):
            if p["fine"] <= chiusura:
                cap += p["importo"] * p["r"]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p["fine"], cap))
        aperte = [p for p in aperte if p["fine"] > chiusura]
        scelte = []
        for M in monete:
            j = M.idx.get(t)
            if j is None or j < 30 or not M.A[j - 1] or M.H[j] == M.L[j]: continue
            z = (M.C[j] - M.C[j - 1]) / M.A[j - 1]
            if z > V.MONETA_ATR: scelte.append((z, M, j))
        scelte.sort(key=lambda x: -x[0])
        for z, M, j in scelte:
            if len(aperte) >= V.MAX_POS or any(p["m"] == M.m for p in aperte): continue
            a = M.A[j]; pct = V.STOP_ATR * a / M.C[j]
            if not 0.002 <= pct <= 0.10: continue
            k = bisect.bisect_left(M.QT, chiusura)
            if k >= len(M.Q) - 1 or M.QT[k] - chiusura > 3600: continue
            if x_atr is None:
                e = M.C[j]; inizio = k; extra = V.RITARDO
            else:
                liv = M.C[j] + x_atr * a; e = None
                for q in range(k, len(M.Q)):
                    if M.Q[q][0] >= chiusura + w * 3600: break
                    if M.Q[q][2] >= liv: e = max(liv, M.Q[q][1]); inizio = q + 1; break
                if e is None: saltate += 1; continue
                extra = SLIP_INGRESSO
                if M.Q[q][4] <= e - V.STOP_ATR * a:                       # chiusa gia' sotto lo stop
                    inizio = None
            pct = V.STOP_ATR * a / e
            importo = cap * V.RISCHIO; noz = importo / pct
            if sum(p["noz"] for p in aperte) + noz > V.LEVA * cap: continue
            if inizio is None: fine, px, motivo = M.Q[q][0] + 900, M.Q[q][4], "stop"
            elif inizio >= len(M.Q): continue
            else: fine, px, motivo = V.gestisci(M, inizio, e, a, chiusura)
            lordo = (px - e) / a; ore = (fine - chiusura) / 3600
            netto = lordo - (2 * COSTO + M.sp + extra + FUNDING_ORA * ore) / pct
            aperte.append({"m": M.m, "fine": fine, "importo": importo, "noz": noz, "r": netto})
            ops.append((chiusura, M.m, lordo, netto, motivo, ore, (e / M.C[j] - 1) / (a / M.C[j])))
    for p in sorted(aperte, key=lambda p: p["fine"]):
        cap += p["importo"] * p["r"]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p["fine"], cap))
    return ops, cap, calo, curva, saltate

def main():
    SP = spread(); tutte = {}
    for m in V.LIQUIDE12 + V.NUOVE:
        b = carica(m, 1)
        if not b or len(b) < 5000: continue
        q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
        if len(q) >= 20000: tutte[m] = V.Moneta(m, b, q, SP.get(m, SPREAD_DEFAULT))
    btc = V.Moneta("XBT", carica("XBT", 1), [], 0)
    liq = [tutte[m] for m in V.LIQUIDE12 if m in tutte]
    t0 = max(INIZIO, max(max(M.T[0], M.Q[0][0]) for M in liq) + 30 * V.H4)
    t1 = min(min(M.T[-1], M.Q[-1][0]) for M in liq) - 2 * 86400
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    anni = list(range(time.gmtime(t0).tm_year, time.gmtime(t1).tm_year + 1))
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    universi = {"29 monete": list(tutte.values()), "12 liquide": liq, "17 NUOVE": [tutte[m] for m in V.NUOVE if m in tutte]}
    print(f"\nCecchino 29 - dal {d(t0)} al {d(t1)} (crollo 2022 escluso); prova fino al {d(taglio)}. {len(tutte)} monete.")
    print("Rischio 0,75 %, max 5 posizioni, leva 3. R = 1 ATR 4h. 'salt' = ordini stop mai raggiunti.\n")
    ris = {}
    for uni, gruppo in universi.items():
        print(f"=== {uni} ===")
        print(f"   {'ingresso':<22}{'op/a':>6}{'salt':>6}{'lordo':>8}{'netto':>8}{'prova':>8}{'verif':>8}{'-top10':>8}{'vinte':>7}"
              f"{'annuo':>8}{'calo':>6}{'an/calo':>8}{'peggio':>8}" + "".join(f"{a:>7}" for a in anni))
        for nome, x, w in VARIANTI:
            ops, cap, calo, curva, salt = simula(btc, gruppo, x, w, t0, t1)
            net = sorted(o[3] for o in ops)
            pr = [o[3] for o in ops if o[0] < taglio]; ve = [o[3] for o in ops if o[0] >= taglio]
            annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
            def valore(t):
                v = 1.0
                for tt, c in curva:
                    if tt <= t: v = c
                    else: break
                return v
            celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(max(t0, calendar.timegm((a, 1, 1, 0, 0, 0)))) - 1) * 100:>+6.0f}%" for a in anni)
            peggio = media([o[6] for o in ops])
            ris[(uni, nome)] = (media(net), media(pr), media(ve), media(net[:-10]), annuo, calo)
            print(f"   {nome:<22}{len(ops) / durata:>6.0f}{salt / durata:>6.0f}{f(media([o[2] for o in ops])):>8}{f(media(net)):>8}"
                  f"{f(media(pr)):>8}{f(media(ve)):>8}{f(media(net[:-10])):>8}{media([x > 0 for x in net]) * 100:>6.0f}%"
                  f"{annuo * 100:>+7.1f}%{calo * 100:>+5.0f}%{(annuo / -calo if calo < 0 else 0):>8.2f}{peggio:>+8.2f}{celle}".replace(".", ","),
                  flush=True)
        print()
    print("peggio = di quanti ATR il prezzo d'ingresso e' sopra la chiusura del segnale (in media)\n")
    print("=== VERDETTO (criterio fissato prima) ===")
    base = ris[("29 monete", "ATTUALE")]
    for nome, x, w in VARIANTI[1:]:
        n, pr, ve, n10, an, ca = ris[("29 monete", nome)]
        nn, _, _, nn10, _, _ = ris[("17 NUOVE", nome)]
        ok = (an > base[4] and (an / -ca if ca < 0 else 9) > (base[4] / -base[5] if base[5] < 0 else 9) and ca > -0.20
              and pr >= base[1] and ve >= base[2] and nn > 0.05 and nn10 > 0)
        print(f"   {nome:<22} annuo {an * 100:+.1f} % (attuale {base[4] * 100:+.1f}), calo {ca * 100:.0f} % (attuale {base[5] * 100:.0f}), "
              f"prova {f(pr)} / verif {f(ve)} (attuale {f(base[1])} / {f(base[2])}), nuove {f(nn)} senza 10 {f(nn10)} -> "
              f"{'PROMOSSA' if ok else 'bocciata'}".replace(".", ","))

if __name__ == "__main__":
    main()
