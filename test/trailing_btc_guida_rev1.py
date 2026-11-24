#!/usr/bin/env python3
"""
TRAILING "BTC GUIDA" - Rev 1  (perpetui Kraken, solo long, BTC + 12 monete liquide, spread nei costi)
Ingresso (come sempre): una candela di BTC chiude in salita di oltre 2 ATR; si comprano le monete che nella
stessa candela sono salite di oltre 1,5 ATR (al massimo 5, le piu' forti).
Nuova gestione dello stop (metodo del trader):
  stop iniziale  sotto l'ultimo minimo rilevante prima dell'ingresso (minimo locale: 2 candele piu' alte per
                 lato, nelle ultime 30 candele), meno 0,1 ATR di margine
  pareggio       quando il prezzo arriva a +0,5 % lo stop va al prezzo d'ingresso
  trailing       quando il prezzo arriva a +2 % lo stop segue il massimo raggiunto a una distanza dell'1 %
  lo stop si aggiorna con il massimo della candela e vale dalla candela successiva (ipotesi prudente)
Versioni:
  A) 4 ore, stop fisso 1,5 ATR, uscita dopo 16 ore             (la regola attuale, per confronto)
  B) 4 ore, nuovo stop, uscita al massimo dopo 16 ore          (stop seguiti minuto per minuto)
  C) 15 minuti, stop fisso 1,5 ATR, uscita dopo 4 candele      (la regola attuale portata a 15 minuti)
  D) 15 minuti, nuovo stop, uscita al massimo dopo 16 candele  (tutto su candele da 15 minuti)
Ingresso: A e B 5 minuti dopo la chiusura (prezzi da 1 minuto); C e D alla chiusura + 0,05 % di costo per il ritardo.
Costi: 0,07 % per ordine + spread di oggi della moneta + funding 0,01 % ogni 8 ore.
Portafoglio: rischio 0,75 % del capitale per operazione, massimo 5 posizioni, leva max 3, interesse composto.

Uso (nella cartella dati):  python ../trailing_btc_guida_rev1.py
Solo libreria standard Python 3.8+.
"""
import calendar, csv, json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G1
import genetico_btc_guida_rev2 as G2
import misuratore_anticipo_rev3 as m3
from misuratore_ritest_rev1 import atr, COSTO, FUNDING_ORA

Z_BTC, Z_MONETA, MAX_SCATTO = 2.0, 1.5, 5
PAREGGIO, AVVIO_TRAIL, DIST_TRAIL = 0.005, 0.02, 0.01
RISCHIO, MAX_POS = 0.75, 5
API15 = "https://futures.kraken.com/api/charts/v1/trade/PF_{m}USD/15m?from={a}&to={b}"

def scarica_15m(m, t0, t1):
    path = f"PF_{m}USD_15m.csv"
    if os.path.exists(path):
        righe = [tuple(float(x) for x in r) for r in csv.reader(open(path))]
        return [(int(r[0]),) + r[1:] for r in righe]
    out = {}; t = t0
    while t < t1:
        js = None
        for tentativo in range(3):
            try:
                with urllib.request.urlopen(API15.format(m=m, a=t, b=min(t + 1500 * 900, t1)), timeout=30) as r:
                    js = json.load(r); break
            except Exception:
                time.sleep(2 + 3 * tentativo)
        for c in (js or {}).get("candles", []):
            ts = int(c["time"]) // 1000
            out[ts] = (ts, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]))
        t += 1500 * 900; time.sleep(0.2)
    righe = [out[k] for k in sorted(out)][:-1]
    with open(path, "w", newline="") as f: csv.writer(f).writerows(righe)
    return righe

def minimo_rilevante(L, i, e, A):
    """Ultimo minimo locale (2 candele piu' alte per lato) nelle 30 candele prima di i, sotto l'ingresso."""
    for j in range(i - 2, max(i - 30, 2), -1):
        if L[j] < e and L[j] <= min(L[j - 2:j + 3]):
            return L[j] - 0.1 * A
    return None

def gestisci(e, stop, barre):
    """barre = lista di (apertura, massimo, minimo, chiusura). Ritorna (prezzo d'uscita, indice)."""
    massimo = e
    for k, (o, h, l, c) in enumerate(barre):
        if l <= stop: return min(stop, o), k
        massimo = max(massimo, h)
        if massimo >= e * (1 + PAREGGIO): stop = max(stop, e)
        if massimo >= e * (1 + AVVIO_TRAIL): stop = max(stop, massimo * (1 - DIST_TRAIL))
    return barre[-1][3], len(barre) - 1

def risultato(e, stop0, uscita, costo):
    pct = (e - stop0) / e
    return (uscita - e) / (e - stop0) - costo / pct, pct

def versione_4h(D, SP, monete, nuovo_stop):
    S = D.serie(4); Tb, Hb, Lb, Cb, Ab, _, _ = S["XBT"]
    forti = {Tb[i] for i in range(1, len(Cb)) if Ab[i - 1] and (Cb[i] - Cb[i - 1]) / Ab[i - 1] > Z_BTC}
    cache = json.load(open("MINUTI_4h.json")) if os.path.exists("MINUTI_4h.json") else {}
    ops = []; durata = 4 * 3600
    for m in monete:
        if m == "XBT": continue
        T, H, L, C, A, _, idx = S[m]
        for i in range(520, len(C) - 5):
            if T[i] not in forti or not A[i - 1] or H[i] == L[i] or (C[i] - C[i - 1]) / A[i - 1] <= Z_MONETA: continue
            righe = cache.get(f"{m}_{T[i]}")
            if righe is None:
                righe = m3.scarica_minuti(m, T[i] + durata - 120, T[i] + 5 * durata + 60)
                if righe: cache[f"{m}_{T[i]}"] = righe
            if not righe: continue
            chiusura = T[i] + durata
            minuti = sorted(r for r in righe if chiusura <= r[0] < chiusura + 4 * durata)
            if len(minuti) < 0.8 * 4 * durata / 60: continue
            k = next((q for q, r in enumerate(minuti) if r[0] >= chiusura + 4 * 60), None)
            if k is None: continue
            e = minuti[k][4]
            stop0 = minimo_rilevante(L, i, e, A[i]) if nuovo_stop else e - 1.5 * A[i]
            if stop0 is None or not (0.003 <= (e - stop0) / e <= 0.10): continue
            barre = [(r[1], r[2], r[3], r[4]) for r in minuti[k + 1:]]
            if nuovo_stop: px, q = gestisci(e, stop0, barre)
            else:
                px, q = barre[-1][3], len(barre) - 1
                for q2, b in enumerate(barre):
                    if b[2] <= stop0: px, q = min(stop0, b[0]), q2; break
            ore_aperta = (q + 1) / 60
            costo = 2 * COSTO + SP.get(m, G2.SPREAD_DEFAULT) + FUNDING_ORA * ore_aperta
            r, pct = risultato(e, stop0, px, costo)
            z = (C[i] - C[i - 1]) / A[i - 1]
            ops.append((chiusura + 4 * 60, chiusura + 4 * 60 + int(ore_aperta * 3600), m, z, pct, r))
    json.dump(cache, open("MINUTI_4h.json", "w"))
    return scegli(ops)

def versione_15m(dati15, SP, monete, nuovo_stop):
    b = dati15["XBT"]; Tb = [x[0] for x in b]; Cb = [x[4] for x in b]
    Ab = atr([x[2] for x in b], [x[3] for x in b], Cb)
    forti = {Tb[i] for i in range(1, len(Cb)) if Ab[i - 1] and (Cb[i] - Cb[i - 1]) / Ab[i - 1] > Z_BTC}
    ops = []
    for m in monete:
        if m == "XBT" or m not in dati15: continue
        bb = dati15[m]; T = [x[0] for x in bb]; O = [x[1] for x in bb]; H = [x[2] for x in bb]
        L = [x[3] for x in bb]; C = [x[4] for x in bb]; A = atr(H, L, C)
        for i in range(100, len(C) - 17):
            if T[i] not in forti or not A[i - 1] or H[i] == L[i] or (C[i] - C[i - 1]) / A[i - 1] <= Z_MONETA: continue
            e = C[i]
            stop0 = minimo_rilevante(L, i, e, A[i]) if nuovo_stop else e - 1.5 * A[i]
            if stop0 is None or not (0.002 <= (e - stop0) / e <= 0.10): continue
            n = 16 if nuovo_stop else 4
            barre = [(O[k], H[k], L[k], C[k]) for k in range(i + 1, i + 1 + n)]
            if nuovo_stop: px, q = gestisci(e, stop0, barre)
            else:
                px, q = barre[-1][3], n - 1
                for q2, bar in enumerate(barre):
                    if bar[2] <= stop0: px, q = min(stop0, bar[0]), q2; break
            costo = 2 * COSTO + 0.0005 + SP.get(m, G2.SPREAD_DEFAULT) + FUNDING_ORA * (q + 1) / 4
            r, pct = risultato(e, stop0, px, costo)
            ops.append((T[i] + 900, T[i + 1 + q] + 900, m, (C[i] - C[i - 1]) / A[i - 1], pct, r))
    return scegli(ops)

def scegli(ops):
    """Al massimo MAX_SCATTO monete per scatto, le piu' forti."""
    per = {}
    for o in ops: per.setdefault(o[0], []).append(o)
    out = []
    for t in sorted(per): out += sorted(per[t], key=lambda o: -o[3])[:MAX_SCATTO]
    return out

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    D = G1.Dati(); SP = G2.spread()
    monete = ["XBT"] + sorted(sorted((m for m in D.uno if m != "XBT"), key=lambda m: SP.get(m, 1))[:12])
    print(f"\nMonete: {' '.join(monete)}", flush=True)
    t0 = D.t0; t1 = D.t1 + 3600
    with ThreadPoolExecutor(4) as ex:
        dati15 = dict(zip(monete, ex.map(lambda m: scarica_15m(m, t0, t1), monete)))
    print("Candele da 15 minuti: " + "  ".join(f"{m} {len(v)}" for m, v in dati15.items()), flush=True)
    versioni = [
        ("A) 4h, stop fisso 1,5 ATR (attuale)", versione_4h(D, SP, monete, False)),
        ("B) 4h, nuovo stop + trailing", versione_4h(D, SP, monete, True)),
        ("C) 15 min, stop fisso 1,5 ATR", versione_15m(dati15, SP, monete, False)),
        ("D) 15 min, nuovo stop + trailing", versione_15m(dati15, SP, monete, True)),
    ]
    tutti = [o for _, v in versioni for o in v]
    inizio, fine = min(o[0] for o in tutti), max(o[1] for o in tutti)
    taglio = D.taglio; durata = (fine - inizio) / (365 * 86400)
    anni = sorted({time.gmtime(o[0]).tm_year for o in tutti})
    print(f"Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(taglio))}.\n")
    print("RISULTATO PER OPERAZIONE (costi e spread inclusi)")
    print(f"   {'Versione':38}{'Oper./a':>8}{'Vinte':>7}{'Stop medio':>11}{'Durata':>8}{'R prova':>9}{'R verif.':>9}" + "".join(f"{a:>7}" for a in anni))
    for nome, ops in versioni:
        if not ops: print(f"   {nome:38} nessuna operazione"); continue
        pr = [o[5] for o in ops if o[0] < taglio]; ve = [o[5] for o in ops if o[0] >= taglio]
        s = "🟢" if media(pr) > 0.05 and media(ve) > 0.05 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
        dur = media([(o[1] - o[0]) / 3600 for o in ops])
        celle = "".join(f"{media([o[5] for o in ops if time.gmtime(o[0]).tm_year == a]):>+7.2f}" for a in anni)
        print(f"{s} {nome:38}{len(ops) / durata:>8.0f}{sum(1 for o in ops if o[5] > 0) / len(ops) * 100:>6.0f}%"
              f"{media([o[4] for o in ops]) * 100:>10.2f}%{dur:>7.1f}h{media(pr):>+9.2f}{media(ve):>+9.2f}{celle}")
    print(f"\nPORTAFOGLIO (rischio {RISCHIO} % per operazione, massimo {MAX_POS} posizioni, leva max 3, interesse composto)".replace(".", ","))
    print(f"   {'Versione':38}{'Annuo':>7}{'Calo':>7}" + "".join(f"{a:>7}" for a in anni))
    for nome, ops in versioni:
        if not ops: continue
        cap, calo, curva, _ = G1.portafoglio(ops, RISCHIO, MAX_POS)
        def valore(t):
            v = 1.0
            for tt, c in curva:
                if tt <= t: v = c
                else: break
            return v
        celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
        annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
        s = "🟢" if annuo > 0 and calo >= -0.20 else ("🟡" if annuo > 0 else "🔴")
        print(f"{s} {nome:38}{annuo * 100:>+6.0f}%{calo * 100:>+6.0f}%{celle}")
    print("""
Stop medio: distanza media dello stop iniziale dal prezzo d'ingresso.  Durata: ore medie in posizione.
R: risultato in multipli del rischio (R = -1 stop iniziale pieno).
🟢 positivo in prova e in verifica (oltre +0,05 R)   🟡 positivo ma debole   🔴 negativo in almeno un periodo
Nel portafoglio: 🟢 guadagna entro il -20 % di calo   🟡 guadagna ma supera il -20 %   🔴 perde""")

if __name__ == "__main__":
    main()
