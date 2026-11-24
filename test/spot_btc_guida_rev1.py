#!/usr/bin/env python3
"""
SPOT "BTC GUIDA" PER ACCUMULARE BTC - Rev 1
Il capitale sta in BTC. Quando scatta il segnale (regole del Cecchino o del Segugio) si cambia una parte
dei BTC nella moneta (coppia moneta/BTC sullo spot), poi si torna in BTC. Tutto e' misurato in BTC:
+10 % = il 10 % di BTC in piu' rispetto a tenerli fermi.
Gestione (in ATR, sul grafico moneta/BTC): stop 1 ATR, pareggio a +1 ATR, trailing 1,5 ATR, chiusura dopo 16 ore
se non supera +3 ATR, fase 2 con allargamento 0,10. ATR del rapporto = ATR della moneta in % (approssimazione).
Percorso: rapporto delle chiusure da 15 minuti (moneta / BTC).
Costi per ordine provati: 0,10 % (riferimento, quasi come i perpetui), 0,25 % (spot, ordine limite),
0,40 % (spot, ordine a mercato), 0,80 % (passando dall'euro: due ordini); piu' 0,10 % di spread.
Portafoglio: rischio 0,75 % del capitale in BTC per operazione, massimo 5 posizioni, senza leva (max 100 %).
Uso (nella cartella dati):  python ../spot_btc_guida_rev1.py
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
import ottimizza_btc_guida_rev1 as O

COSTI = [0.001, 0.0025, 0.004, 0.008]
SPREAD = 0.001
TETTO = 60 * 96

def simula(X, p, costo):
    xb = X.q15["XBT"]; tb = {x[0]: x[4] for x in xb}
    ops = []
    for ch, m, zb, pb, zm, pm, e_usd, a, k0 in X.cand:
        if p["modo"] == "atr":
            if zb <= p["btc"] or zm <= p["moneta"]: continue
        elif pb <= p["btc_pct"] or zm <= p["moneta"]: continue
        barre = X.q15[m]
        if barre[k0][0] not in tb: continue
        e = barre[k0][1] / tb[barre[k0][0]]          # rapporto all'apertura della prima candela dopo la chiusura
        a_pct = a / e_usd; ar = a_pct * e            # ATR del rapporto (approssimato)
        stop0 = e - p["stop"] * ar; stop = stop0; massimo = e; fase2 = False
        px, q = None, None; fine = min(len(barre), k0 + TETTO); n1 = p["fase1"] * 4
        for j in range(k0, fine):
            t = barre[j][0]
            if t not in tb: continue
            c = barre[j][4] / tb[t]
            if not fase2 and j - k0 >= n1: px, q = c, j - k0; break
            if c <= stop: px, q = c, j - k0; break
            if c > massimo:
                massimo = c; g = (massimo - e) / ar
                if not fase2 and g >= p["L"]: fase2 = True
                if g >= p["pareggio"]:
                    stop = max(stop, e, massimo - (p["trail"] + (p["g"] * (g - p["L"]) if fase2 else 0)) * ar)
        if px is None: continue
        pct = (e - stop0) / e
        r = (px - e) / (e - stop0) - (2 * costo + SPREAD) / pct
        ops.append((ch, ch + (q + 1) * 900, m, zm, pct, r))
    per = {}
    for o in ops: per.setdefault(o[0], []).append(o)
    out = []
    for t in sorted(per): out += sorted(per[t], key=lambda o: -o[3])[:p["max"]]
    return out

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    X = O.Dati()
    anni = list(range(time.gmtime(X.D.t0).tm_year, time.gmtime(X.D.t1).tm_year + 1))
    durata = (X.D.t1 - X.D.t0) / (365 * 86400) - 0.3
    regole = [("🎯 Cecchino (BTC oltre 2 ATR)", dict(O.BASE, moneta=1.7, stop=1.0)),
              ("🐕 Segugio (BTC oltre +1,25 %)", dict(O.BASE, modo="pct_atr", btc_pct=0.0125, moneta=1.7, stop=1.0))]
    print(f"\nTutto in BTC. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(X.taglio))}. Rischio 0,75 % per operazione, max 5 posizioni, senza leva.\n")
    print(f"   {'Regola':34}{'Costo/ordine':>13}{'Oper./a':>8}{'Vinte':>6}{'R prova':>9}{'R verif':>9}{'senza 10':>9}{'BTC/anno':>9}{'Calo':>7}" + "".join(f"{a:>7}" for a in anni))
    for nome, p in regole:
        for costo in COSTI:
            ops = simula(X, p, costo)
            cap, calo, curva, fatte = G1.portafoglio(ops, 0.75, 5, leva=1.0)
            rr = sorted(o[5] for o in fatte)
            pr = [o[5] for o in fatte if o[0] < X.taglio]; ve = [o[5] for o in fatte if o[0] >= X.taglio]
            def valore(t):
                v = 1.0
                for tt, c in curva:
                    if tt <= t: v = c
                    else: break
                return v
            celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
            annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
            s = "🟢" if media(pr) > 0.05 and media(ve) > 0.05 and media(rr[:-10]) > 0 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
            print(f"{s} {nome:34}{costo * 100:>12.2f}%{len(fatte) / durata:>8.0f}{sum(1 for r in rr if r > 0) / max(1, len(rr)) * 100:>5.0f}%"
                  f"{media(pr):>+9.2f}{media(ve):>+9.2f}{media(rr[:-10]):>+9.2f}{annuo * 100:>+8.1f}%{calo * 100:>+6.0f}%{celle}".replace(".", ","))
        print()
    print("""BTC/anno: BTC guadagnati (o persi) all'anno rispetto a tenerli fermi.  Calo: peggior discesa misurata in BTC.
R: risultato per operazione in multipli del rischio, costi inclusi.  senza 10: R togliendo le 10 operazioni migliori.
🟢 positiva in prova e verifica e anche senza le 10 migliori   🟡 positiva ma fragile   🔴 negativa""")

if __name__ == "__main__":
    main()
