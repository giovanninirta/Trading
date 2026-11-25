#!/usr/bin/env python3
"""
VERIFICA SU MONETE NUOVE - "BTC guida" (Cecchino Rev 6 e Segugio Rev 7)  (perpetui Kraken, 4 ore, solo long)
Regole IDENTICHE ai bot simulati, nessun parametro toccato:
  SEGNALE  Cecchino: candela 4h di BTC in salita di oltre 2 ATR (ATR 14, Wilder)
           Segugio:  candela 4h di BTC in salita di oltre +1,25 %
  MONETE   salite di oltre 1,7 ATR nella stessa candela; si comprano le piu' forti, max 5 posizioni,
           mai due volte la stessa moneta, posizioni totali al massimo 3 volte il capitale
  INGRESSO alla chiusura della candela 4h (+ 0,05 % di ritardo + spread reale)
  USCITA   (sui 15 min) stop 1,0 ATR; pareggio a +1 ATR; trailing 1,5 ATR dal massimo; se dopo 16 ore dalla
           chiusura del segnale non ha superato +3 ATR si chiude; oltre +3 ATR (fase 2) niente limite di tempo e
           trailing 1,5 + 0,10 x (guadagno - 3) ATR
  RISCHIO  0,75 % del capitale per operazione (R = 1 ATR), interesse composto
Costi: 0,07 % per ordine x2 + spread reale + 0,05 % ritardo + funding 0,01 %/8h.

Universo: A) le 12 liquide su cui la regola e' stata costruita (riferimento)
          B) le 17 monete dei 30 perpetui MAI usate per scegliere i parametri (dati mai visti)

CRITERIO FISSATO PRIMA DEL TEST (per ciascun bot, sulle 17 nuove; stesse soglie usate per scegliere i bot):
  PROMOSSO se  R netto medio > +0,05   E   R netto senza le 10 migliori > 0   E   portafoglio annuo > 0

Uso (nella cartella dati):  python ../verifica_monete_nuove_btc_guida_rev1.py
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, atr, MONETE, COSTO, FUNDING_ORA
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from trailing_btc_guida_rev1 import scarica_15m

LIQUIDE12 = "AAVE ADA DOGE DOT ETH LINK LTC NEAR SOL TRX UNI XRP".split()
NUOVE = [m for m in MONETE if m not in LIQUIDE12 and m != "XBT"]
H4 = 4 * 3600
MONETA_ATR, STOP_ATR, PAREGGIO, TRAIL, FASE1_ORE, SOGLIA2, ALLARGA = 1.7, 1.0, 1.0, 1.5, 16, 3.0, 0.10
RISCHIO, MAX_POS, LEVA = 0.0075, 5, 3.0
RITARDO, TETTO = 0.0005, 60 * 96
BOT = {"Cecchino": ("atr", 2.0), "Segugio": ("pct", 0.0125)}

def quattro_ore(barre):
    out, g = [], []
    for b in barre:
        if g and g[0][0] // H4 != b[0] // H4:
            if len(g) == 4: out.append((g[0][0] // H4 * H4, g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4]))
            g = []
        g.append(b)
    return out

class Moneta:
    def __init__(self, m, uno, q, sp):
        self.m, self.sp, self.Q = m, sp, q; self.QT = [x[0] for x in q]
        b4 = quattro_ore(uno)
        self.T = [b[0] for b in b4]; self.H = [b[2] for b in b4]; self.L = [b[3] for b in b4]; self.C = [b[4] for b in b4]
        self.A = atr(self.H, self.L, self.C); self.idx = {t: i for i, t in enumerate(self.T)}

def gestisci(M, k, e, a, chiusura):
    """Uscita come i bot sulle candele 15 min dalla k. Ritorna (t_uscita, prezzo, motivo)."""
    stop, mx, fase2, ultima = e - STOP_ATR * a, e, False, e
    for x in range(k, min(len(M.Q), k + TETTO)):
        t, o, h, l, c = M.Q[x]
        if not fase2 and t >= chiusura + FASE1_ORE * 3600: return t, ultima, "16 ore"
        if l <= stop: return t + 900, min(stop, o), "stop"
        if h > mx:
            mx = h; g = (h - e) / a
            if not fase2 and g >= SOGLIA2: fase2 = True
            if g >= PAREGGIO:
                stop = max(stop, e, h - (TRAIL + (ALLARGA * (g - SOGLIA2) if fase2 else 0.0)) * a)
        ultima = c
    x = min(len(M.Q), k + TETTO) - 1
    return M.Q[x][0] + 900, M.Q[x][4], "tetto"

def simula(btc, monete, regola, t0, t1):
    tipo, soglia = regola
    cap, picco, calo, aperte, ops = 1.0, 1.0, 0.0, [], []
    curva = []
    for i in range(30, len(btc.C)):
        t = btc.T[i]
        if not (t0 <= t <= t1) or not btc.A[i - 1]: continue
        z_btc = (btc.C[i] - btc.C[i - 1]) / btc.A[i - 1]; p_btc = btc.C[i] / btc.C[i - 1] - 1
        if not ((tipo == "atr" and z_btc > soglia) or (tipo == "pct" and p_btc > soglia)): continue
        chiusura = t + H4
        for p in sorted(aperte, key=lambda p: p["fine"]):            # chiude le posizioni finite prima del segnale
            if p["fine"] <= chiusura:
                cap += p["importo"] * p["r"]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p["fine"], cap))
        aperte = [p for p in aperte if p["fine"] > chiusura]
        scelte = []
        for M in monete:
            j = M.idx.get(t)
            if j is None or j < 30 or not M.A[j - 1] or M.H[j] == M.L[j]: continue
            z = (M.C[j] - M.C[j - 1]) / M.A[j - 1]
            if z > MONETA_ATR: scelte.append((z, M, j))
        scelte.sort(key=lambda x: -x[0])
        for z, M, j in scelte:
            if len(aperte) >= MAX_POS or any(p["m"] == M.m for p in aperte): continue
            e, a = M.C[j], M.A[j]; pct = STOP_ATR * a / e
            if not 0.002 <= pct <= 0.10: continue
            k = bisect.bisect_left(M.QT, chiusura)
            if k >= len(M.Q) - 1 or M.QT[k] - chiusura > 3600: continue
            importo = cap * RISCHIO; noz = importo / pct
            if sum(p["noz"] for p in aperte) + noz > LEVA * cap: continue
            fine, px, motivo = gestisci(M, k, e, a, chiusura)
            lordo = (px - e) / a; ore = (fine - chiusura) / 3600
            netto = lordo - (2 * COSTO + M.sp + RITARDO + FUNDING_ORA * ore) / pct
            aperte.append({"m": M.m, "fine": fine, "importo": importo, "noz": noz, "r": netto})
            ops.append((chiusura, M.m, lordo, netto, motivo, ore))
    for p in sorted(aperte, key=lambda p: p["fine"]):
        cap += p["importo"] * p["r"]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p["fine"], cap))
    return ops, cap, calo, curva

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    SP = spread()
    def prepara(lista):
        out = []
        for m in lista:
            b = carica(m, 1)
            if not b or len(b) < 5000: print(f"   {m}: dati insufficienti"); continue
            q = scarica_15m(m, b[0][0], b[-1][0] + 3600)
            if len(q) < 20000: print(f"   {m}: dati 15 min insufficienti"); continue
            out.append(Moneta(m, b, q, SP.get(m, SPREAD_DEFAULT)))
        return out
    btc = Moneta("XBT", carica("XBT", 1), [], 0)       # per BTC servono solo le candele 4h
    gruppi = {"A) 12 liquide (origine)": prepara(LIQUIDE12), "B) 17 NUOVE (mai viste)": prepara(NUOVE)}
    liq = gruppi["A) 12 liquide (origine)"]
    t0 = max(max(M.T[0], M.Q[0][0]) for M in liq) + 30 * H4; t1 = min(min(M.T[-1], M.Q[-1][0]) for M in liq) - 2 * 86400
    taglio = t0 + (t1 - t0) * 0.6; durata = (t1 - t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    anni = list(range(time.gmtime(t0).tm_year, time.gmtime(t1).tm_year + 1))
    print(f"\nDal {d(t0)} al {d(t1)}; prova fino al {d(taglio)}. Rischio 0,75 %, max 5 posizioni, leva 3.\n")
    verdetti = []
    for bot, regola in BOT.items():
        print(f"=== {bot} ===")
        print(f"   {'universo':<26}{'op/a':>6}{'lordo':>8}{'netto':>8}{'prova':>8}{'verif':>8}{'-top10':>8}{'vinte':>7}"
              f"{'annuo':>8}{'calo':>7}" + "".join(f"{a:>7}" for a in anni))
        for nome, gruppo in gruppi.items():
            ops, cap, calo, curva = simula(btc, gruppo, regola, t0, t1)
            net = sorted(o[3] for o in ops)
            pr = [o[3] for o in ops if o[0] < taglio]; ve = [o[3] for o in ops if o[0] >= taglio]
            annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
            def valore(t):
                v = 1.0
                for tt, c in curva:
                    if tt <= t: v = c
                    else: break
                return v
            celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
            print(f"   {nome:<26}{len(ops) / durata:>6.0f}{media([o[2] for o in ops]):>+8.3f}{media(net):>+8.3f}{media(pr):>+8.3f}"
                  f"{media(ve):>+8.3f}{media(net[:-10]):>+8.3f}{media([1.0 if x > 0 else 0.0 for x in net]) * 100:>6.0f}%"
                  f"{annuo * 100:>+7.1f}%{calo * 100:>+6.0f}%{celle}".replace(".", ","))
            if nome.startswith("B"):
                ok = media(net) > 0.05 and media(net[:-10]) > 0 and annuo > 0
                verdetti.append((bot, media(net), media(net[:-10]), annuo, ok))
                per = {}
                for o in ops: per.setdefault(o[1], []).append(o[3])
                print("      nuove per moneta (operazioni / R netto medio): " + "  ".join(
                    f"{m} {len(v)}/{media(v):+.2f}".replace(".", ",") for m, v in sorted(per.items())))
        print()
    print("=== VERDETTO sulle 17 nuove (serve: netto > +0,05 R, senza le 10 migliori > 0, annuo > 0) ===")
    for bot, n, n10, an, ok in verdetti:
        print(f"   {bot:<10} netto {n:+.3f} R   senza 10 {n10:+.3f} R   annuo {an * 100:+.1f} %   -> {'PROMOSSO' if ok else 'BOCCIATO'}".replace(".", ","))

if __name__ == "__main__":
    main()
