#!/usr/bin/env python3
"""
PORTAFOGLIO ROTTURA - Rev 1
Simulazione realistica della variante migliore del test "rottura e ritest":
  rottura di una resistenza (livello toccato almeno 2 volte), ingresso subito senza ritest, solo long,
  stop sotto il livello rotto di 0,5 ATR, uscita quando la chiusura scende sotto il minimo delle
  ultime 20 candele (dopo almeno 20 candele), candele da 4 ore, 30 monete, perpetui Kraken.

Portafoglio vero, candela per candela:
  - ogni operazione rischia una quota fissa del conto (distanza tra ingresso e stop)
  - l'esposizione totale non supera un tetto (1x o 2x il conto): oltre, la posizione si riduce o si salta
  - una sola posizione per moneta
  - costi 0,07 % per ordine sul valore della posizione, funding 0,01 % ogni 8 ore a carico del long
  - se il prezzo apre gia' oltre lo stop, l'uscita avviene al prezzo di apertura (peggiore dello stop)

Uso (nella cartella dati):  python ../portafoglio_rottura_rev1.py
Usa le funzioni di misuratore_ritest_rev1.py (stessa cartella degli script).
"""
import os, sys, time
from collections import defaultdict, deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import MONETE, carica, segnali

COSTO, FUNDING_BARRA = 0.0007, 0.00005
CONFIG = [(0.005, 1), (0.01, 1), (0.01, 2), (0.02, 1), (0.02, 2)]   # (rischio per operazione, esposizione massima)

def simula(barre_per_moneta, ingressi, rischio, leva):
    tempi = sorted({b[0] for barre in barre_per_moneta.values() for b in barre})
    barra = {m: {b[0]: b for b in barre} for m, barre in barre_per_moneta.items()}
    cassa = 1.0; pos = {}; storia = defaultdict(lambda: deque(maxlen=20)); ultimo = {}
    valori, operazioni = [], []
    for t in tempi:
        # aggiorna le posizioni aperte con la candela t
        for m in list(pos):
            b = barra[m].get(t)
            if not b: continue
            _, o, h, l, c = b
            p = pos[m]; p["barre"] += 1
            cassa -= p["q"] * p["e"] * FUNDING_BARRA
            uscita = None
            if l <= p["stop"]: uscita = min(o, p["stop"])
            elif p["barre"] >= 20 and len(storia[m]) == 20 and c < min(storia[m]): uscita = c
            if uscita is not None:
                cassa += p["q"] * (uscita - p["e"]) - p["q"] * uscita * COSTO
                operazioni.append((uscita - p["e"]) / (p["e"] - p["stop"]))
                del pos[m]
        for m, barre in barra.items():
            b = barre.get(t)
            if b: ultimo[m] = b[4]
        valore = cassa + sum(p["q"] * (ultimo[m] - p["e"]) for m, p in pos.items())
        # nuovi ingressi alla chiusura di t
        for m, stop in sorted(ingressi.get(t, [])):
            if m in pos or valore <= 0: continue
            e = ultimo[m]; distanza = e - stop
            if distanza <= 0: continue
            q = rischio * valore / distanza
            esposto = sum(p["q"] * ultimo[k] for k, p in pos.items())
            spazio = leva * valore - esposto
            if q * e > spazio:
                if spazio < 0.2 * q * e: continue
                q = spazio / e
            cassa -= q * e * COSTO
            pos[m] = dict(q=q, e=e, stop=stop, barre=0)
        for m, barre in barra.items():
            b = barre.get(t)
            if b: storia[m].append(b[4])
        valori.append((t, cassa + sum(p["q"] * (ultimo[m] - p["e"]) for m, p in pos.items())))
    return valori, operazioni

def statistiche(valori):
    picco, calo = valori[0][1], 0.0
    for _, v in valori: picco = max(picco, v); calo = min(calo, v / picco - 1)
    anni = defaultdict(list)
    for t, v in valori: anni[time.gmtime(t).tm_year].append(v)
    per_anno, prec = {}, valori[0][1]
    for a in sorted(anni):
        per_anno[a] = anni[a][-1] / prec - 1; prec = anni[a][-1]
    return per_anno, calo, valori[-1][1] / valori[0][1]

def main():
    barre_per_moneta, ingressi = {}, defaultdict(list)
    for m in MONETE:
        barre = carica(m, 4)
        if not barre or len(barre) < 400: continue
        barre_per_moneta[m] = barre
        ops, _ = segnali(barre)
        for nome, d, i, stop in ops:
            if nome == "Rottura senza ritest" and d == 1:
                ingressi[barre[i][0]].append((m, stop))
    # riferimento: tenere tutte le monete in parti uguali
    tempi = sorted({b[0] for barre in barre_per_moneta.values() for b in barre})
    chiusure = {m: {b[0]: b[4] for b in barre} for m, barre in barre_per_moneta.items()}
    v, tenere, prec = 1.0, [], {}
    for t in tempi:
        g = [chiusure[m][t] / prec[m] - 1 for m in chiusure if t in chiusure[m] and m in prec]
        v *= 1 + (sum(g) / len(chiusure) if g else 0)
        for m in chiusure:
            if t in chiusure[m]: prec[m] = chiusure[m][t]
        tenere.append((t, v))

    righe = [("Tenere le monete", statistiche(tenere), None)]
    for rischio, leva in CONFIG:
        valori, ops = simula(barre_per_moneta, ingressi, rischio, leva)
        righe.append(("Rischio " + f"{rischio * 100:.1f}".replace(".", ",") + f" %, esposizione max {leva}x", statistiche(valori), ops))

    anni = sorted(righe[0][1][0])
    print(f"\n{len(barre_per_moneta)} monete, candele da 4 ore, {sum(len(x) for x in ingressi.values())} segnali di ingresso.\n")
    print("GUADAGNO ANNO PER ANNO")
    print(f"{'':3}{'':34}" + "".join(f"{a:>9}" for a in anni) + f"{'Capitale':>11}{'Calo max':>10}{'Operaz.':>9}{'Vinte':>7}")
    for nome, (per_anno, calo, tot), ops in righe:
        celle = "".join(f"{('▲' if per_anno[a] > 0 else '▼')}{per_anno[a] * 100:+.0f}%".rjust(9) for a in anni)
        extra = f"{len(ops):>9}{sum(1 for o in ops if o > 0) / max(len(ops), 1) * 100:>6.0f}%" if ops is not None else ""
        print(f"   {nome:34}{celle}{f'x{tot:.2f}'.replace('.', ','):>11}{calo * 100:>9.0f}%{extra}")
    print(f"""
Il primo anno ({anni[0]}) parte a meta' anno e l'ultimo ({anni[-1]}) e' in corso.
Capitale: quante volte il capitale iniziale.   Calo max: discesa piu' ampia dal picco del conto.
Rischio: quanto si perde, in % del conto, se un'operazione tocca lo stop.
Esposizione max: valore totale delle posizioni aperte rispetto al conto (2x = leva fino a 2).
Costi, funding e aperture oltre lo stop inclusi. Dati passati: non e' una previsione.""")

if __name__ == "__main__":
    main()
