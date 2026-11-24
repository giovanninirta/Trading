#!/usr/bin/env python3
"""
PORTAFOGLIO "BTC GUIDA" - Rev 1  (perpetui Kraken, solo long, candele da 4 ore)
Regola (misurata nel test anticipo Rev 3):
  BTC chiude una candela da 4 ore in salita di oltre 2 ATR  ->  si comprano le monete che nella stessa
  candela sono salite di oltre 1,5 ATR. Ingresso 5 minuti dopo la chiusura (prezzi da 1 minuto),
  stop 1,5 ATR sotto l'ingresso, uscita dopo 4 candele (16 ore). Costi 0,07 % per ordine + funding.
Portafoglio realistico con un solo capitale:
  - rischio per operazione = % del capitale che si perde se scatta lo stop
  - massimo numero di posizioni aperte insieme (se scattano piu' monete, si prendono le piu' forti)
  - leva massima 3: la somma delle posizioni non supera 3 volte il capitale
Obiettivo: calo massimo entro il 20 %.

Uso (nella cartella dati, dopo misuratore_anticipo_rev3.py che salva MINUTI_4h.json):
  python ../portafoglio_btc_guida_rev1.py
Solo libreria standard Python 3.8+.
"""
import calendar, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, atr, MONETE, COSTO, FUNDING_ORA, MIN_STOP, MAX_STOP
import misuratore_anticipo_rev3 as m3

ORE, RITARDO, LEVA = 4, 5, 3.0
RISCHI = [0.25, 0.5, 0.75, 1.0, 1.5]
MAX_POS = [3, 5, 10]
LIMITE_CALO = -0.20

def operazioni():
    dati = {m: carica(m, ORE) for m in MONETE}
    dati = {m: b for m, b in dati.items() if b and len(b) > 700}
    b = dati["XBT"]; Tb = [x[0] for x in b]; Cb = [x[4] for x in b]
    Ab = atr([x[2] for x in b], [x[3] for x in b], Cb)
    forti = {Tb[i] for i in range(1, len(Cb)) if Ab[i - 1] and (Cb[i] - Cb[i - 1]) / Ab[i - 1] > 2}
    durata = ORE * 3600
    cache = {}
    if os.path.exists("MINUTI_4h.json"):
        with open("MINUTI_4h.json") as f: cache = json.load(f)
    ops, mancanti = [], 0
    for m, bb in dati.items():
        if m == "XBT": continue
        T = [x[0] for x in bb]; H = [x[2] for x in bb]; L = [x[3] for x in bb]; C = [x[4] for x in bb]
        A = atr(H, L, C)
        for i in range(520, len(C) - 5):
            if not (T[i] in forti and A[i - 1] and H[i] != L[i]): continue
            z = (C[i] - C[i - 1]) / A[i - 1]
            if z <= 1.5: continue
            chiave = f"{m}_{T[i]}"
            righe = cache.get(chiave)
            if righe is None:
                righe = m3.scarica_minuti(m, T[i] + durata - 120, T[i] + 5 * durata + 60)
                if righe: cache[chiave] = righe
            if not righe: mancanti += 1; continue
            chiusura = T[i] + durata; fine = chiusura + 4 * durata
            minuti = sorted(r for r in righe if chiusura <= r[0] < fine)
            if len(minuti) < 0.8 * 4 * durata / 60: mancanti += 1; continue
            k = next((j for j, r in enumerate(minuti) if r[0] >= chiusura + (RITARDO - 1) * 60), None)
            if k is None: continue
            e = minuti[k][4]; rischio = 1.5 * A[i]; pct = rischio / e
            if not (MIN_STOP <= pct <= MAX_STOP): continue
            stop = e - rischio; r = None
            for x in minuti[k + 1:]:
                if x[3] <= stop: r = -1.0; break
            if r is None: r = (minuti[-1][4] - e) / rischio
            r -= (2 * COSTO + FUNDING_ORA * ORE * 4) / pct
            ops.append((chiusura, fine, m, z, pct, r))
    with open("MINUTI_4h.json", "w") as f: json.dump(cache, f)
    return sorted(ops), mancanti

def portafoglio(ops, rischio, max_pos):
    cap, picco, calo = 1.0, 1.0, 0.0
    curva = []                                    # (tempo, capitale) a ogni chiusura
    per_ingresso = {}
    for o in ops: per_ingresso.setdefault(o[0], []).append(o)
    aperte = []                                   # (fine, importo rischiato, r, nozionale)
    prese = saltate = 0; peggior_giorno = 0.0
    for t in sorted(per_ingresso):
        # chiudi le posizioni finite prima di questo ingresso
        for p in sorted([p for p in aperte if p[0] <= t]):
            cap += p[1] * p[3]; curva.append((p[0], cap))
            picco = max(picco, cap); calo = min(calo, cap / picco - 1)
        aperte = [p for p in aperte if p[0] > t]
        gruppo = sorted(per_ingresso[t], key=lambda o: -o[3])
        esito_gruppo = 0.0
        for chiusura, fine, m, z, pct, r in gruppo:
            noz_aperto = sum(p[2] for p in aperte)
            importo = cap * rischio / 100; noz = importo / pct
            if len(aperte) >= max_pos or noz_aperto + noz > LEVA * cap: saltate += 1; continue
            aperte.append((fine, importo, noz, r)); prese += 1; esito_gruppo += importo * r
        peggior_giorno = min(peggior_giorno, esito_gruppo / cap if cap else 0)
    for p in sorted(aperte):
        cap += p[1] * p[3]; curva.append((p[0], cap)); picco = max(picco, cap); calo = min(calo, cap / picco - 1)
    return cap, calo, prese, saltate, peggior_giorno, curva

def main():
    ops, mancanti = operazioni()
    if not ops: sys.exit("Nessuna operazione: lancia prima misuratore_anticipo_rev3.py.")
    t0, t1 = ops[0][0], ops[-1][1]
    anni = sorted({time.gmtime(o[0]).tm_year for o in ops})
    durata = (t1 - t0) / (365 * 86400)
    taglio = t0 + (t1 - t0) * 0.6
    print(f"\n{len(ops)} operazioni possibili dal {time.strftime('%Y-%m-%d', time.gmtime(t0))} "
          f"al {time.strftime('%Y-%m-%d', time.gmtime(t1))} ({mancanti} senza dati da 1 minuto).")
    print(f"Scatti di BTC: {len({o[0] for o in ops})}, in media {len(ops) / len({o[0] for o in ops}):.1f} monete per scatto.\n")
    print(f"{'':3}{'Rischio':>8}{'Max pos.':>9}{'Prese':>7}{'Annuo':>8}{'Calo max':>10}{'Peggior scatto':>16}"
          f"{'Prova':>8}{'Verifica':>10}" + "".join(f"{a:>7}" for a in anni))
    for max_pos in MAX_POS:
        for rischio in RISCHI:
            cap, calo, prese, saltate, peggio, curva = portafoglio(ops, rischio, max_pos)
            def valore(t):
                v = 1.0
                for tt, c in curva:
                    if tt <= t: v = c
                    else: break
                return v
            celle = ""
            for a in anni:
                ia = calendar.timegm((a, 1, 1, 0, 0, 0))
                fa = calendar.timegm((a + 1, 1, 1, 0, 0, 0))
                celle += f"{(valore(fa) / valore(ia) - 1) * 100:>+6.0f}%"
            annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
            pr = valore(taglio) - 1; ve = cap / valore(taglio) - 1
            s = "🟢" if calo >= LIMITE_CALO and annuo > 0 else ("🔴" if annuo <= 0 else "🟡")
            print(f"{s} {rischio:>7.2f}%{max_pos:>9}{prese:>7}{annuo * 100:>+7.0f}%{calo * 100:>+9.0f}%{peggio * 100:>+15.1f}%"
                  f"{pr * 100:>+7.0f}%{ve * 100:>+9.0f}%{celle}")
        print()
    print("""Rischio: % del capitale persa se scatta lo stop di un'operazione.  Max pos.: posizioni aperte insieme.
Annuo: rendimento medio composto.  Calo max: peggior discesa dal massimo (sulle chiusure).
Peggior scatto: risultato peggiore di tutte le monete comprate sullo stesso scatto di BTC.
🟢 guadagna e resta entro il -20 %   🟡 guadagna ma supera il -20 %   🔴 perde
Attenzione: il calo e' misurato sulle chiusure; durante le 16 ore il calo puo' essere un po' piu' profondo.""")

if __name__ == "__main__":
    main()
