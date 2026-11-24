#!/usr/bin/env python3
"""
PORTAFOGLIO COMBINATO - Rev 1
Due bot sullo stesso capitale, con calo massimo voluto entro il 20 %:
  TREND        bot giornaliero Canale 55/20 su 30 monete, spot, filtro forza +10 % (come il bot Rev 3):
               usa una parte del capitale (quota trend), 1/30 della quota per moneta.
  BTC GUIDA    perpetui, solo long: dopo uno scatto di BTC (candela 4h oltre 2 ATR) compra le monete gia'
               partite, ingresso 5 minuti dopo, uscita dopo 16 ore (vedi portafoglio_btc_guida_rev1.py).
               Rischia una % del capitale TOTALE per operazione, massimo 5 posizioni; il resto del capitale
               (1 - quota trend) fa da margine, con le posizioni al massimo 3 volte quel margine.
Semplificazione: le due parti si ribilanciano ogni giorno (il conto vero si ribilancerebbe ogni tanto).

Uso (nella cartella dati):  python ../portafoglio_combinato_rev1.py
Solo libreria standard Python 3.8+.
"""
import bisect, calendar, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import misuratore_trend_rev5 as tr
import portafoglio_btc_guida_rev1 as pg

QUOTE_TREND = [1.0, 0.8, 0.7, 0.6, 0.5, 0.4]
RISCHI_GUIDA = [0.0, 0.5, 0.75, 1.0]
MAX_POS, LEVA, LIMITE = 5, 3.0, -0.20

def main():
    dati = {m: d for m in tr.MONETE if (d := tr.carica(m))}
    giorni = sorted(dati["XBT"])
    C = {m: [d.get(t) for t in giorni] for m, d in dati.items()}
    r_trend, _, _, _ = tr.simula(C, C["XBT"], "long", soglia_forza=0.10)
    ops, _ = pg.operazioni()
    i0 = tr.INIZIO; T = len(giorni)
    taglio = i0 + int((T - i0) * 0.6)
    anni = sorted({time.gmtime(giorni[t]).tm_year for t in range(i0, T)})
    durata = (giorni[-1] - giorni[i0]) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(giorni[t]))
    print(f"\nDal {d(i0)} al {d(T - 1)}. Prova fino al {d(taglio)}, poi verifica.")
    print(f"Operazioni BTC guida possibili: {len(ops)}.\n")
    print(f"{'':3}{'Quota trend':>12}{'Rischio guida':>14}{'Annuo':>8}{'Calo max':>10}{'Prova':>8}{'Verifica':>10}"
          + "".join(f"{a:>7}" for a in anni))

    per_ingresso = {}
    for o in ops: per_ingresso.setdefault(o[0], []).append(o)
    ingressi = sorted(per_ingresso)

    for q in QUOTE_TREND:
        for rg in RISCHI_GUIDA:
            if q == 1.0 and rg > 0: continue
            E = [1.0] * T; aperte = []; k = 0
            for t in range(i0 + 1, T):
                e = E[t - 1] * (1 + q * r_trend[t])
                # BTC guida: ingressi e chiusure avvenuti fino a questo giorno
                while rg > 0 and k < len(ingressi) and ingressi[k] <= giorni[t]:
                    ti = ingressi[k]
                    for p in [p for p in aperte if p[0] <= ti]: e += p[1] * p[3]
                    aperte = [p for p in aperte if p[0] > ti]
                    for chiusura, fine, m, z, pct, r in sorted(per_ingresso[ti], key=lambda o: -o[3]):
                        importo = e * rg / 100; noz = importo / pct
                        if len(aperte) >= MAX_POS or sum(p[2] for p in aperte) + noz > LEVA * (1 - q) * e: continue
                        aperte.append((fine, importo, noz, r))
                    k += 1
                for p in [p for p in aperte if p[0] <= giorni[t]]: e += p[1] * p[3]
                aperte = [p for p in aperte if p[0] > giorni[t]]
                E[t] = e
            def calo(a, b):
                picco, peggio = E[a], 0.0
                for x in E[a:b + 1]: picco = max(picco, x); peggio = min(peggio, x / picco - 1)
                return peggio
            cm = calo(i0, T - 1); annuo = E[-1] ** (1 / durata) - 1
            celle = ""
            for a in anni:
                ix = [t for t in range(i0, T) if time.gmtime(giorni[t]).tm_year == a]
                celle += f"{(E[ix[-1]] / E[max(ix[0] - 1, i0)] - 1) * 100:>+6.0f}%"
            s = "🟢" if cm >= LIMITE and annuo > 0 else ("🟡" if annuo > 0 else "🔴")
            nome_r = "-" if rg == 0 else f"{rg:.2f}%"
            print(f"{s} {q * 100:>10.0f}%{nome_r:>14}{annuo * 100:>+7.0f}%{cm * 100:>+9.0f}%"
                  f"{(E[taglio] - 1) * 100:>+7.0f}%{(E[-1] / E[taglio] - 1) * 100:>+9.0f}%{celle}")
        print()
    print("""Quota trend: parte del capitale nel bot giornaliero (il resto sta fermo come margine per BTC guida).
Rischio guida: % del capitale totale persa se scatta lo stop di un'operazione BTC guida ("-" = bot spento).
Annuo: rendimento medio composto.   Calo max: peggior discesa dal massimo, misurata a fine giornata.
🟢 guadagna e resta entro il -20 %   🟡 guadagna ma supera il -20 %   🔴 perde""")

if __name__ == "__main__":
    main()
