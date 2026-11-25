#!/usr/bin/env python3
"""
STATISTICHE OPERAZIONI PULLBACK - Rev 1  (stesse regole di test_intraday_rev2.py)
Per alcune varianti stampa, operazione per operazione aggregata:
  - come finiscono: stop, obiettivo (TP), tempo scaduto, trailing; dopo quante candele
  - quanto erano andate in guadagno prima dello stop (escursione favorevole massima, in R)
  - le operazioni "troncate": chiuse allo stop ma che entro 48 ore dall'ingresso avrebbero raggiunto
    l'obiettivo 2R; e di quanto si sarebbe dovuto allargare lo stop per restare dentro (in ATR orari)
  - quanto scende il prezzo dopo lo stop (per capire se lo stop protegge davvero)
Uso (nella cartella dati):  python ../statistiche_pullback_rev1.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica
from genetico_btc_guida_rev2 import spread, SPREAD_DEFAULT
from test_intraday_rev1 import LIQUIDE, MIN_STOP, MAX_STOP
from test_intraday_rev2 import Moneta2

VARIANTI = [("nessuno", "nessuno", 3, "2R"), ("struttura", "minimi", 3, "2R"),
            ("struttura", "minimi", 4, "2R"), ("struttura", "minimi", 3, "trail")]
DOPO = 48   # ore dall'ingresso in cui si guarda "cosa sarebbe successo"

def simula(M, i, e, stop, uscita, rischio, hh):
    """Come esci() di Rev 2, ma ritorna i dettagli."""
    H, L, C, A = M.H, M.L, M.C, M.A; n = len(C)
    limite, tp = {"2R": (48, e + 2 * rischio), "massimo": (72, hh), "trail": (120, None)}[uscita]
    estremo, mfe, j, stop0 = e, 0.0, i, stop
    while j < min(i + limite, n - 1):
        j += 1
        if L[j] <= stop:
            ambigua = tp is not None and H[j] >= tp
            tipo = "stop" if stop == stop0 else "trail"
            return dict(tipo=tipo, n=j - i, r=(stop - e) / rischio, mfe=mfe, j=j, ambigua=ambigua)
        if tp is not None and H[j] >= tp: return dict(tipo="tp", n=j - i, r=(tp - e) / rischio, mfe=max(mfe, 2.0), j=j)
        mfe = max(mfe, (H[j] - e) / rischio)
        if uscita == "trail":
            estremo = max(estremo, H[j]); stop = max(stop, estremo - 3 * A[j])
    return dict(tipo="tempo", n=j - i, r=(C[j] - e) / rischio, mfe=mfe, j=j)

def operazioni(M, P, trend, supp, uscita):
    H, L, C, A = M.H, M.L, M.C, M.A
    ops, i = [], 220
    while i < len(C) - 1:
        k = M.m72[i]; hh = H[k]
        if k >= i - 1 or not (C[i] > H[i - 1] and C[i] < hh): i += 1; continue
        ll = min(L[k:i + 1])
        if (hh - ll) / A[i] < P or not M.trend_orario(trend, k, ll) or not M.supporto(supp, k, ll, A[i]): i += 1; continue
        e = C[i]; stop = ll - 0.3 * A[i]; rischio = e - stop
        if not (MIN_STOP <= rischio / e <= MAX_STOP): i += 1; continue
        d = simula(M, i, e, stop, uscita, rischio, hh)
        # cosa succede entro DOPO ore dall'ingresso, ignorando lo stop
        fine = min(i + DOPO, len(C) - 1); tp2 = e + 2 * rischio; minimo = e; arriva = None
        for x in range(i + 1, fine + 1):
            minimo = min(minimo, L[x])
            if H[x] >= tp2: arriva = x; break
        d["arriva2R"] = arriva is not None
        d["allarga"] = (stop - minimo) / A[i] if arriva is not None else None   # ATR in piu' necessari
        d["mae_dopo"] = (e - min(L[i + 1:fine + 1])) / rischio if fine > i else 0.0  # discesa max in R (48h)
        d["atr_stop"] = rischio / A[i]
        ops.append(d)
        i = d["j"] + 1
    return ops

def pct(a, b): return f"{a:>5} ({a / b * 100:>4.0f} %)" if b else f"{a:>5}"

def fasce(valori, limiti, etichette, tot):
    out = []
    for (lo, hi), et in zip(limiti, etichette):
        c = sum(1 for v in valori if lo <= v < hi)
        out.append(f"      {et:<24}{pct(c, tot)}")
    return "\n".join(out)

def rapporto(nome, ops):
    N = len(ops)
    if not N: print(f"\n### {nome}: nessuna operazione"); return
    st = [o for o in ops if o["tipo"] == "stop"]; tp = [o for o in ops if o["tipo"] == "tp"]
    tr = [o for o in ops if o["tipo"] == "trail"]; te = [o for o in ops if o["tipo"] == "tempo"]
    print(f"\n### {nome}   ({N} operazioni; stop iniziale in media {sum(o['atr_stop'] for o in ops) / N:.1f} ATR orari dall'ingresso)".replace(".", ","))
    print(f"   Come finiscono:")
    print(f"      {'stop iniziale':<24}{pct(len(st), N)}")
    if tp: print(f"      {'obiettivo 2R (TP)':<24}{pct(len(tp), N)}")
    if tr:
        print(f"      {'trailing in guadagno':<24}{pct(sum(1 for o in tr if o['r'] > 0.05), N)}")
        print(f"      {'trailing in pari/perdita':<24}{pct(sum(1 for o in tr if o['r'] <= 0.05), N)}")
    print(f"      {'tempo scaduto':<24}{pct(len(te), N)}   (R medio {sum(o['r'] for o in te) / max(1, len(te)):+.2f})".replace(".", ","))
    amb = sum(1 for o in st if o.get("ambigua"))
    if amb: print(f"      di cui stop con TP nella stessa candela (contati come stop): {amb}")
    print(f"   Stop iniziale: dopo quante candele (ore)")
    print(fasce([o["n"] for o in st], [(1, 2), (2, 4), (4, 7), (7, 13), (13, 25), (25, 999)],
                ["1 candela", "2-3", "4-6", "7-12", "13-24", "oltre 24"], len(st)))
    print(f"   Stop iniziale: quanto era andata in guadagno prima (massimo, in R)")
    print(fasce([o["mfe"] for o in st], [(-1, 0.25), (0.25, 0.5), (0.5, 1), (1, 1.5), (1.5, 9)],
                ["meno di +0,25 R", "+0,25 / +0,5 R", "+0,5 / +1 R", "+1 / +1,5 R", "oltre +1,5 R"], len(st)))
    if tp:
        print(f"   Obiettivo 2R: dopo quante candele")
        print(fasce([o["n"] for o in tp], [(1, 4), (4, 7), (7, 13), (13, 25), (25, 999)],
                    ["1-3", "4-6", "7-12", "13-24", "oltre 24"], len(tp)))
    if tr:
        print(f"   Trailing: risultato all'uscita e massimo raggiunto")
        print(fasce([o["r"] for o in tr], [(-9, 0.05), (0.05, 1), (1, 2), (2, 4), (4, 99)],
                    ["<= 0 R", "0 / +1 R", "+1 / +2 R", "+2 / +4 R", "oltre +4 R"], len(tr)))
        g = [o["mfe"] - o["r"] for o in tr if o["mfe"] > 1]
        if g: print(f"      guadagno restituito dal massimo (trade arrivati oltre +1 R): {sum(g) / len(g):.2f} R in media".replace(".", ","))
    tronc = [o for o in st if o["arriva2R"]]
    print(f"   TRONCATE: chiuse allo stop ma arrivate a +2R entro {DOPO} ore dall'ingresso: {pct(len(tronc), len(st))} degli stop")
    if tronc:
        print(f"   Di quanto andava allargato lo stop per restare dentro (ATR orari oltre lo stop)")
        print(fasce([o["allarga"] for o in tronc], [(0, 0.25), (0.25, 0.5), (0.5, 1), (1, 2), (2, 99)],
                    ["fino a 0,25 ATR", "0,25 / 0,5", "0,5 / 1", "1 / 2", "oltre 2"], len(tronc)))
    print(f"   Dopo lo stop, discesa massima entro {DOPO} ore dall'ingresso (in R; -1 = lo stop)")
    print(fasce([o["mae_dopo"] for o in st], [(0, 1.5), (1.5, 2), (2, 3), (3, 99)],
                ["fino a 1,5 R", "1,5 / 2 R", "2 / 3 R", "oltre 3 R"], len(st)))

def motivo_trend(M, k, ll):
    """Perche' il filtro 'struttura' scarta (prima condizione che fallisce)."""
    ph = M.confermati(M.ph, M.phi, k); pl = M.confermati(M.pl, M.pli, k)
    if len(ph) < 2 or len(pl) < 2: return "pochi pivot"
    if not ph[-1][1] > ph[-2][1]: return "massimi non crescenti"
    if not pl[-1][1] > pl[-2][1]: return "minimi non crescenti"
    if not ll > pl[-1][1]: return "pullback rompe l'ultimo minimo"
    return None

def imbuto(monete, P):
    """Ogni pullback (un massimo hh) conta una volta, alla prima ripartenza; senza blocco delle posizioni."""
    cat = {}
    for M in monete:
        H, L, C, A = M.H, M.L, M.C, M.A; visti = set()
        for i in range(220, len(C) - 1):
            k = M.m72[i]; hh = H[k]
            if k in visti or k >= i - 1 or not (C[i] > H[i - 1] and C[i] < hh): continue
            ll = min(L[k:i + 1])
            if (hh - ll) / A[i] < P: continue
            visti.add(k)
            e = C[i]; stop = ll - 0.3 * A[i]; rischio = e - stop
            if not (MIN_STOP <= rischio / e <= MAX_STOP): c = "stop fuori limiti"
            else:
                mt = motivo_trend(M, k, ll)
                if mt: c = "NO trend: " + mt
                elif not M.supporto("minimi", k, ll, A[i]): c = "trend si, NO supporto"
                else: c = "PRESA (trend + supporto)"
            r = simula(M, i, e, stop, "2R", rischio, hh)["r"] if rischio > 0 else 0.0
            cat.setdefault(c, []).append(r)
    N = sum(len(v) for v in cat.values())
    print(f"\n### IMBUTO: tutti i pullback di almeno {P} ATR con ripartenza ({N}); esito ipotetico con uscita 2R, R lordo")
    print(f"      {'categoria':<44}{'quanti':>14}{'R medio':>9}{'TP 2R':>8}")
    ordine = sorted(cat, key=lambda c: (not c.startswith("PRESA"), not c.startswith("trend"), c))
    for c in ordine:
        v = cat[c]; tp = sum(1 for x in v if x >= 1.99)
        print(f"      {c:<44}{pct(len(v), N):>14}{sum(v) / len(v):>+9.3f}{tp / len(v) * 100:>7.0f}%".replace(".", ","))
    nt = [x for c, v in cat.items() if c.startswith("NO trend") for x in v]
    if nt: print(f"      {'totale scartate dal filtro trend':<44}{pct(len(nt), N):>14}{sum(nt) / len(nt):>+9.3f}".replace(".", ","))

def main():
    SP = spread(); monete = []
    for m in LIQUIDE:
        b = carica(m, 1)
        if b and len(b) > 5000: monete.append(Moneta2(m, b, SP.get(m, SPREAD_DEFAULT)))
    t0 = max(M.T[0] for M in monete); t1 = min(M.T[-1] for M in monete)
    print(f"{len(monete)} monete liquide, dal {time.strftime('%Y-%m-%d', time.gmtime(t0))}. R lordi (senza costi).")
    for trend, supp, P, usc in VARIANTI:
        ops = []
        for M in monete: ops += operazioni(M, P, trend, supp, usc)
        rapporto(f"trend {trend} | supporto {supp} | P {P} | uscita {usc}", ops)
    for P in (3, 4): imbuto(monete, P)

if __name__ == "__main__":
    main()
