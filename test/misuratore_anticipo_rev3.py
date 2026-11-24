#!/usr/bin/env python3
"""
MISURATORE ANTICIPO - Rev 3: "BTC guida, gia' partite" con candele da 1 minuto
Segnale (come Rev 2): BTC chiude una candela al rialzo di oltre 2 ATR; si comprano le monete che nella
stessa candela sono salite di oltre 1,5 ATR (candela con scambi veri: massimo diverso dal minimo).
Uscita: alla chiusura della 4a candela dopo il segnale. Stop: 1,5 ATR sotto il prezzo d'ingresso,
controllato minuto per minuto. Costi 0,07 % per ordine + funding.

Novita': per ogni segnale si scaricano le candele da 1 minuto e si entra con ritardo di
0 (chiusura esatta), 1, 2, 5, 15, 30 minuti dopo la chiusura della candela del segnale.
Se il vantaggio regge con qualche minuto di ritardo, un bot normale su GitHub/VPS puo' prenderlo.

Uso (nella cartella dati):  python ../misuratore_anticipo_rev3.py
Solo libreria standard Python 3.8+.
"""
import json, math, os, sys, time, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, atr, MONETE, COSTO, FUNDING_ORA, MIN_STOP, MAX_STOP

API = "https://futures.kraken.com/api/charts/v1/trade/PF_{m}USD/1m?from={a}&to={b}"
RITARDI = [0, 1, 2, 5, 15, 30]
CACHE = "MINUTI_{ore}h.json"

def scarica_minuti(m, a, b):
    for tentativo in range(3):
        try:
            with urllib.request.urlopen(API.format(m=m, a=a, b=b), timeout=30) as r:
                js = json.load(r)
            return [(int(c["time"]) // 1000, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]))
                    for c in js.get("candles", [])]
        except Exception:
            time.sleep(2 + 3 * tentativo)
    return None

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    print()
    for etichetta, ore in (("CANDELE DA 1 ORA", 1), ("CANDELE DA 4 ORE", 4)):
        dati = {m: carica(m, ore) for m in MONETE}
        dati = {m: b for m, b in dati.items() if b and len(b) > 700}
        b = dati["XBT"]; Tb = [x[0] for x in b]; Cb = [x[4] for x in b]
        Ab = atr([x[2] for x in b], [x[3] for x in b], Cb)
        forti = {Tb[i] for i in range(1, len(Cb)) if Ab[i - 1] and (Cb[i] - Cb[i - 1]) / Ab[i - 1] > 2}
        T0, T1 = min(x[0][0] for x in dati.values()), max(x[-1][0] for x in dati.values())
        taglio = T0 + (T1 - T0) * 0.6
        segnali = []                                   # (moneta, inizio candela segnale, atr, chiusura oraria)
        for m, bb in dati.items():
            if m == "XBT": continue
            T = [x[0] for x in bb]; H = [x[2] for x in bb]; L = [x[3] for x in bb]; C = [x[4] for x in bb]
            A = atr(H, L, C)
            for i in range(520, len(C) - 5):
                if T[i] in forti and A[i - 1] and H[i] != L[i] and (C[i] - C[i - 1]) / A[i - 1] > 1.5:
                    segnali.append((m, T[i], A[i], C[i]))
        # candele da 1 minuto: dalla chiusura del segnale a 4 candele dopo
        durata = ore * 3600
        cache_file = CACHE.format(ore=ore)
        cache = {}
        if os.path.exists(cache_file):
            with open(cache_file) as f: cache = json.load(f)
        mancanti = [s for s in segnali if f"{s[0]}_{s[1]}" not in cache]
        print(f"{etichetta}: {len(segnali)} segnali, da scaricare {len(mancanti)} finestre da 1 minuto...", flush=True)
        def lavoro(s):
            m, t, _, _ = s
            a = t + durata - 120; z = t + durata + 4 * durata + 60
            return f"{m}_{t}", scarica_minuti(m, a, z)
        with ThreadPoolExecutor(4) as ex:
            for k, (chiave, righe) in enumerate(ex.map(lavoro, mancanti)):
                if righe is not None: cache[chiave] = righe
                if k % 500 == 499:
                    with open(cache_file, "w") as f: json.dump(cache, f)
        with open(cache_file, "w") as f: json.dump(cache, f)

        ris = defaultdict(list); scarti = 0; differenza = []
        for m, t, a, c_ora in segnali:
            righe = cache.get(f"{m}_{t}")
            if not righe: scarti += 1; continue
            per_t = {r[0]: r for r in righe}
            chiusura = t + durata; fine = chiusura + 4 * durata
            ultimo = per_t.get(chiusura - 60)          # minuto che chiude la candela del segnale
            if not ultimo: scarti += 1; continue
            differenza.append(abs(ultimo[4] / c_ora - 1))
            minuti = sorted(r for r in righe if chiusura <= r[0] < fine)
            if len(minuti) < 0.8 * 4 * durata / 60: scarti += 1; continue
            anno = time.gmtime(t).tm_year; ver = t >= taglio
            for rit in RITARDI:
                if rit == 0: e = ultimo[4]; dopo = minuti
                else:
                    k = next((j for j, r in enumerate(minuti) if r[0] >= chiusura + (rit - 1) * 60), None)
                    if k is None: continue
                    e = minuti[k][4]; dopo = minuti[k + 1:]
                rischio = 1.5 * a; pct = rischio / e
                if not (MIN_STOP <= pct <= MAX_STOP): continue
                stop = e - rischio; r = None
                for x in dopo:
                    if x[3] <= stop: r = -1.0; break
                if r is None: r = (minuti[-1][4] - e) / rischio
                r -= (2 * COSTO + FUNDING_ORA * ore * 4) / pct
                ris[rit].append((anno, ver, r))
        anni = sorted({a for v in ris.values() for a, _, _ in v})
        print(f"   finestre senza dati da 1 minuto: {scarti}.  Scarto medio chiusura 1h vs 1 minuto: "
              f"{media(differenza) * 100:.3f} %")
        print(f"{'':3}{'Ingresso':26}{'N':>6}{'Vinte':>6}{'R prova':>9}{'R verif.':>9}{'R tutti':>9}" + "".join(f"{a:>7}" for a in anni))
        for rit in RITARDI:
            g = ris.get(rit, [])
            if not g: continue
            pr = [r for _, v, r in g if not v]; ve = [r for _, v, r in g if v]; tot = [r for *_, r in g]
            mt = media(tot); sd = math.sqrt(media([(x - mt) ** 2 for x in tot])); ts = mt / (sd / math.sqrt(len(tot))) if sd else 0
            s = "🟢" if len(ve) >= 30 and media(pr) > 0.05 and media(ve) > 0.05 and ts >= 3 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
            nome = "alla chiusura esatta" if rit == 0 else f"{rit} minut{'o' if rit == 1 else 'i'} dopo"
            celle = "".join(f"{media([r for a2, _, r in g if a2 == a]):>+7.2f}" if any(a2 == a for a2, _, _ in g) else f"{'':>7}" for a in anni)
            print(f"{s} {nome:26}{len(g):>6}{sum(1 for r in tot if r > 0) / len(tot) * 100:>5.0f}%"
                  f"{media(pr):>+9.2f}{media(ve):>+9.2f}{mt:>+9.2f}{celle}")
        print()
    print("""R: risultato medio per operazione in multipli del rischio (stop 1,5 ATR), costi e funding inclusi.
Un bot su GitHub parte con qualche minuto di ritardo; un bot su un server sempre acceso entra in 1-2 minuti.
🟢 positivo in prova e verifica e troppo netto per essere fortuna   🟡 positivo ma non dimostrato   🔴 no""")

if __name__ == "__main__":
    main()
