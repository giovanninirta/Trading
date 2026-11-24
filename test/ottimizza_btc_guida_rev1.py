#!/usr/bin/env python3
"""
OTTIMIZZA "BTC GUIDA" - Rev 1  (4 ore, perpetui, solo long, BTC + 12 monete liquide, spread nei costi)
Regola di partenza (trailing Rev 7, L = 3, g = 0,10):
  ingresso   candela 4h di BTC oltre 2 ATR; monete salite oltre 1,5 ATR nella stessa candela (max 5)
  fase 1     stop 1,5 ATR, pareggio a +1 ATR, trailing 1,5 ATR, chiusura dopo 16 ore se ancora in fase 1
  fase 2     oltre +3 ATR: niente limite di tempo, trailing 1,5 + 0,10 x (guadagno - 3) ATR
PARTE 1 - sensibilita' a passo fine: ogni parametro si muove da solo, gli altri restano fermi.
PARTE 2 - ingresso a PERCENTUALE: BTC sale di oltre X % nella candela 4h (al posto di 2 ATR),
          con le monete in ATR (1,5) oppure anch'esse in percentuale.
PARTE 3 - ottimizzazione: si cambia un parametro alla volta tenendo il valore migliore IN PROVA
          (voto = costanza per scatto, come nel genetico), per tre giri; poi si guarda la verifica.
Percorso del prezzo: candele da 15 minuti; ingresso alla chiusura + 0,05 % di ritardo.
Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.
Uso (nella cartella dati):  python ../ottimizza_btc_guida_rev1.py
"""
import bisect, calendar, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
import genetico_btc_guida_rev2 as G2
import trailing_btc_guida_rev1 as T1
from misuratore_ritest_rev1 import COSTO, FUNDING_ORA

BASE = {"modo": "atr", "btc": 2.0, "moneta": 1.5, "stop": 1.5, "pareggio": 1.0, "trail": 1.5,
        "fase1": 16, "L": 3.0, "g": 0.10, "max": 5}
GRIGLIE = {
    "btc":      [round(1.5 + 0.1 * k, 1) for k in range(16)],
    "moneta":   [round(0.8 + 0.1 * k, 1) for k in range(18)],
    "stop":     [round(1.0 + 0.1 * k, 1) for k in range(16)],
    "pareggio": [round(0.5 + 0.1 * k, 1) for k in range(16)],
    "trail":    [round(1.0 + 0.1 * k, 1) for k in range(16)],
    "fase1":    list(range(8, 34, 2)),
    "L":        [round(2.0 + 0.25 * k, 2) for k in range(13)],
    "g":        [round(0.05 * k, 2) for k in range(9)],
    "max":      list(range(1, 9)),
}
NOMI = {"btc": "scatto BTC (ATR)", "moneta": "moneta (ATR)", "stop": "stop iniziale (ATR)", "pareggio": "pareggio dopo (ATR)",
        "trail": "trailing (ATR)", "fase1": "durata fase 1 (ore)", "L": "soglia fase 2 (ATR)", "g": "allargamento g", "max": "monete per scatto"}
TETTO = 60 * 96

class Dati:
    def __init__(self):
        D = G1.Dati(); SP = G2.spread()
        self.D, self.SP = D, SP
        self.monete = ["XBT"] + sorted(sorted((m for m in D.uno if m != "XBT"), key=lambda m: SP.get(m, 1))[:12])
        self.q15 = {m: T1.scarica_15m(m, D.t0, D.t1 + 3600) for m in self.monete}
        t15 = {m: [x[0] for x in v] for m, v in self.q15.items()}
        S = D.serie(4); Tb, Hb, Lb, Cb, Ab, _, _ = S["XBT"]
        btc = {}
        for i in range(1, len(Cb)):
            if not Ab[i - 1]: continue
            z, p = (Cb[i] - Cb[i - 1]) / Ab[i - 1], Cb[i] / Cb[i - 1] - 1
            if z > 1.0 or p > 0.004: btc[Tb[i]] = (z, p)
        self.cand = []                             # (chiusura, moneta, zb, pb, zm, pm, prezzo, atr, indice 15m)
        for m in self.monete:
            if m == "XBT": continue
            T, H, L, C, A, _, _ = S[m]
            for i in range(520, len(C) - 2):
                if T[i] not in btc or not A[i - 1] or H[i] == L[i]: continue
                ch = T[i] + 4 * 3600; k = bisect.bisect_left(t15[m], ch)
                if k + 128 >= len(self.q15[m]) or self.q15[m][k][0] != ch: continue
                zb, pb = btc[T[i]]
                self.cand.append((ch, m, zb, pb, (C[i] - C[i - 1]) / A[i - 1], C[i] / C[i - 1] - 1, C[i], A[i], k))
        self.taglio = D.taglio

def simula(X, p):
    ops = []
    for ch, m, zb, pb, zm, pm, e, a, k0 in X.cand:
        if p["modo"] == "atr":
            if zb <= p["btc"] or zm <= p["moneta"]: continue
        elif p["modo"] == "pct_atr":
            if pb <= p["btc_pct"] or zm <= p["moneta"]: continue
        else:
            if pb <= p["btc_pct"] or pm <= p["moneta_pct"]: continue
        stop0 = e - p["stop"] * a; pct = p["stop"] * a / e
        if not 0.002 <= pct <= 0.10: continue
        barre = X.q15[m]; fine = min(len(barre), k0 + TETTO); n1 = p["fase1"] * 4
        stop, massimo, fase2 = stop0, e, False
        px, q = None, None
        for j in range(k0, fine):
            if not fase2 and j - k0 >= n1: px, q = barre[j - 1][4], j - 1 - k0; break
            _, o, h, l, c = barre[j]
            if l <= stop: px, q = min(stop, o), j - k0; break
            if h > massimo:
                massimo = h; G_ = (massimo - e) / a
                if not fase2 and G_ >= p["L"]: fase2 = True
                if G_ >= p["pareggio"]:
                    dist = p["trail"] + (p["g"] * (G_ - p["L"]) if fase2 else 0.0)
                    stop = max(stop, e, massimo - dist * a)
        if px is None: px, q = barre[fine - 1][4], fine - 1 - k0
        costo = 2 * COSTO + 0.0005 + X.SP.get(m, G2.SPREAD_DEFAULT) + FUNDING_ORA * (q + 1) / 4
        forza = zm if p["modo"] != "pct" else pm
        ops.append((ch, ch + (q + 1) * 900, m, forza, pct, (px - e) / (e - stop0) - costo / pct))
    per = {}
    for o in ops: per.setdefault(o[0], []).append(o)
    out = []
    for t in sorted(per): out += sorted(per[t], key=lambda o: -o[3])[:p["max"]]
    return out

def media(v): return sum(v) / len(v) if v else 0.0

def misura(X, p):
    ops = simula(X, p)
    if len(ops) < 30: return None
    cap, calo, curva, fatte = G1.portafoglio(ops, T1.RISCHIO, T1.MAX_POS)
    rr = sorted(o[5] for o in fatte)
    pr = [o[5] for o in fatte if o[0] < X.taglio]; ve = [o[5] for o in fatte if o[0] >= X.taglio]
    durata = (X.D.t1 - X.D.t0) / (365 * 86400) - 0.3
    voto = G1.voto(fatte, X.D, "prova")[0]
    return {"n": len(fatte) / durata, "pr": media(pr), "ve": media(ve), "s10": media(rr[:-10]),
            "annuo": cap ** (1 / durata) - 1 if cap > 0 else -1, "calo": calo, "voto": voto, "curva": curva}

def riga(et, r, segno=""):
    if r is None: return f"   {et:>10}  troppo poche operazioni"
    ok = r["pr"] > 0.05 and r["ve"] > 0.05 and r["s10"] > 0.05
    s = "🟢" if ok and r["calo"] >= -0.20 else ("🟡" if r["pr"] > 0 and r["ve"] > 0 and r["s10"] > 0 else "🔴")
    return (f"{s} {et:>10}{r['n']:>8.0f}{r['voto']:>+7.1f}{r['pr']:>+9.2f}{r['ve']:>+9.2f}{r['s10']:>+9.2f}"
            f"{r['annuo'] * 100:>+7.0f}%{r['calo'] * 100:>+7.0f}%  {segno}").replace(".", ",")

TESTA = f"   {'Valore':>10}{'Oper./a':>8}{'Voto':>7}{'R prova':>9}{'R verif':>9}{'senza 10':>9}{'Annuo':>8}{'Calo':>8}"

def anni_riga(r, anni):
    def valore(t):
        v = 1.0
        for tt, c in r["curva"]:
            if tt <= t: v = c
            else: break
        return v
    return "".join(f"{a}: {(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:+.0f}%   " for a in anni)

def main():
    X = Dati()
    anni = list(range(time.gmtime(X.D.t0).tm_year, time.gmtime(X.D.t1).tm_year + 1))
    print(f"\nMonete: {' '.join(X.monete)}. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(X.taglio))}.")
    print("Portafoglio: rischio 0,75 % per operazione, massimo 5 posizioni, leva max 3, interesse composto.")
    rb = misura(X, BASE)
    print("\nREGOLA DI PARTENZA:\n" + TESTA + "\n" + riga("partenza", rb) + "\n   " + anni_riga(rb, anni))

    print("\nPARTE 1 - SENSIBILITA' (un parametro alla volta, gli altri fermi; <- = valore attuale)")
    for k, valori in GRIGLIE.items():
        print(f"\n   {NOMI[k]}\n" + TESTA)
        for v in valori:
            p = dict(BASE); p[k] = v
            print(riga(str(v), misura(X, p), "<-" if v == BASE[k] else ""))

    print("\nPARTE 2 - INGRESSO A PERCENTUALE (BTC sale di oltre X % nella candela da 4 ore)")
    print("\n   BTC in %, monete oltre 1,5 ATR\n" + TESTA)
    for x in [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]:
        p = dict(BASE, modo="pct_atr", btc_pct=x / 100)
        print(riga(f"BTC {x}%", misura(X, p)))
    print("\n   BTC oltre 1 %, monete in % (oltre Y %)\n" + TESTA)
    for y in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
        p = dict(BASE, modo="pct", btc_pct=0.01, moneta_pct=y / 100)
        print(riga(f"mon. {y}%", misura(X, p)))
    print("\n   BTC e monete in %, alcune combinazioni\n" + TESTA)
    for x, y in [(1.5, 2.0), (1.5, 3.0), (2.0, 2.0), (2.0, 3.0), (2.0, 4.0), (2.5, 3.0), (3.0, 4.0)]:
        p = dict(BASE, modo="pct", btc_pct=x / 100, moneta_pct=y / 100)
        print(riga(f"{x}/{y}%", misura(X, p)))

    print("\nPARTE 3 - OTTIMIZZAZIONE SUL SOLO PERIODO DI PROVA (tre giri, un parametro alla volta)")
    p = dict(BASE); best = misura(X, p)["voto"]
    for giro in range(3):
        cambiato = False
        for k, valori in GRIGLIE.items():
            for v in valori:
                q = dict(p); q[k] = v; r = misura(X, q)
                if r and r["voto"] > best + 0.05: best, p, cambiato = r["voto"], q, True
        print(f"   giro {giro + 1}: voto in prova {best:+.2f}   " + "  ".join(f"{k}={p[k]}" for k in GRIGLIE))
        if not cambiato: break
    ro = misura(X, p)
    print("\n" + TESTA + "\n" + riga("partenza", rb) + "\n" + riga("ottimizz.", ro))
    print("   partenza:  " + anni_riga(rb, anni) + "\n   ottimizz.: " + anni_riga(ro, anni))
    print("""
Voto: costanza per scatto nel periodo di prova (quello che l'ottimizzazione guarda).  senza 10: R senza le 10 migliori.
🟢 oltre +0,05 R in prova, verifica e senza le 10 migliori, calo entro il -20 %   🟡 positiva ma debole   🔴 no
Una regola robusta ha un altopiano: tanti valori vicini tutti verdi. Un picco isolato e' quasi sempre fortuna.
L'ottimizzazione guarda solo la prova: se migliora la prova ma non la verifica, ha solo adattato la regola al passato.""")

if __name__ == "__main__":
    main()
