#!/usr/bin/env python3
"""
VERIFICA AL MINUTO - Rev 1: la migliore regola dell'algoritmo genetico BTC guida
Regola: candele da 1 ora. BTC chiude in salita di oltre 1 ATR e una moneta, nella stessa ora, chiude in
DISCESA di oltre 1 ATR -> si compra la moneta (al massimo le 5 piu' scese), stop 0,75 ATR, uscita dopo 3 ore.
Sospetto: una moneta che scende mentre BTC sale puo' essere un prezzo "strano" di un'ora poco scambiata
che si ricompone in pochi secondi. Se e' cosi', entrando qualche minuto dopo il vantaggio sparisce.
Qui si rifa' il conto con le candele da 1 minuto ed ingressi 0, 1, 2, 5, 15 minuti dopo la chiusura.
Costi perpetui 0,07 % per ordine + funding (senza il costo forfettario di ritardo del genetico).
Uso (nella cartella dati):  python ../verifica_minuti_genetico_rev1.py
"""
import json, math, os, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genetico_btc_guida_rev1 as G
import misuratore_anticipo_rev3 as m3
from misuratore_ritest_rev1 import COSTO, FUNDING_ORA

REGOLA = {"ore": 1, "btc": 1.0, "tipo": "ritardo", "soglia": -1.0, "tenuta": 3, "stop": 0.75, "obiettivo": None, "filtro": False}
RITARDI = [0, 1, 2, 5, 15]
CACHE = "MINUTI_genetico.json"

def media(v): return sum(v) / len(v) if v else 0.0

def main():
    D = G.Dati(); S = D.serie(1)
    ops = G.operazioni(D, REGOLA)          # al massimo 5 monete per scatto
    print(f"\n{len(ops)} operazioni candidate. Verifica dal {time.strftime('%Y-%m-%d', time.gmtime(D.taglio))}.")
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    def lavoro(o):
        chiusura, _, m, _, _, _ = o; k = f"{m}_{chiusura}"
        if k in cache: return k, cache[k]
        return k, m3.scarica_minuti(m, chiusura - 3600, chiusura + 4 * 3600 + 60)
    with ThreadPoolExecutor(4) as ex:
        for k, righe in ex.map(lavoro, ops):
            if righe: cache[k] = righe
    json.dump(cache, open(CACHE, "w"))
    ris = {r: [] for r in RITARDI}; scarti = 0; profondita = []
    for chiusura, _, m, z, pct, r_ora in ops:
        righe = cache.get(f"{m}_{chiusura}")
        if not righe: scarti += 1; continue
        T, H, L, C, A, _, idx = S[m]; j = idx[chiusura - 3600]
        per_t = {x[0]: x for x in righe}
        ultimo = per_t.get(chiusura - 60)
        minuti = sorted(x for x in righe if chiusura <= x[0] < chiusura + 3 * 3600)
        if not ultimo or len(minuti) < 150: scarti += 1; continue
        # quanto del calo dell'ora si era gia' recuperato dopo 1 e 5 minuti
        rischio = 0.75 * A[j]
        for rit in RITARDI:
            if rit == 0: e = ultimo[4]; dopo = minuti
            else:
                k = next((q for q, x in enumerate(minuti) if x[0] >= chiusura + (rit - 1) * 60), None)
                if k is None: continue
                e = minuti[k][4]; dopo = minuti[k + 1:]
            p = rischio / e
            if p < 0.002 or p > 0.15: continue
            stop = e - rischio; r = None
            for x in dopo:
                if x[3] <= stop: r = -1.0; break
            if r is None: r = (minuti[-1][4] - e) / rischio
            r -= (2 * COSTO + FUNDING_ORA * 3) / p
            ris[rit].append((time.gmtime(chiusura).tm_year, chiusura >= D.taglio, r))
        if len(minuti) > 5:
            profondita.append(((minuti[4][4] - ultimo[4]) / rischio))
    anni = sorted({a for v in ris.values() for a, _, _ in v})
    print(f"Finestre senza dati da 1 minuto: {scarti}.  Recupero medio nei primi 5 minuti: {media(profondita):+.2f} R\n")
    print(f"{'':3}{'Ingresso':22}{'N':>6}{'Vinte':>6}{'R prova':>9}{'R verif.':>9}" + "".join(f"{a:>7}" for a in anni))
    for rit in RITARDI:
        g = ris[rit]
        if not g: continue
        pr = [r for _, v, r in g if not v]; ve = [r for _, v, r in g if v]
        s = "🟢" if media(pr) > 0.05 and media(ve) > 0.05 else ("🟡" if media(pr) > 0 and media(ve) > 0 else "🔴")
        nome = "alla chiusura esatta" if rit == 0 else f"{rit} minut{'o' if rit == 1 else 'i'} dopo"
        celle = "".join(f"{media([r for a2, _, r in g if a2 == a]):>+7.2f}" for a in anni)
        print(f"{s} {nome:22}{len(g):>6}{sum(1 for _, _, r in g if r > 0) / len(g) * 100:>5.0f}%{media(pr):>+9.2f}{media(ve):>+9.2f}{celle}")
    print("""
R: risultato medio per operazione in multipli del rischio, costi inclusi.
Recupero nei primi 5 minuti: quanto il prezzo e' gia' risalito 5 minuti dopo la chiusura, in R.
Se il vantaggio crolla gia' a 1-2 minuti, era un prezzo strano che si ricompone subito: non tradabile da un bot normale.""")

if __name__ == "__main__":
    main()
