#!/usr/bin/env python3
"""
OTTIMIZZA "BTC GUIDA" - Rev 2: prova congiunta dei valori migliori della Rev 1
Ingresso BTC: 2 ATR, oppure +1 % o +1,25 % nella candela 4h.  Monete: oltre 1,5 / 1,7 / 2,0 ATR.
Stop iniziale: 0,6 - 1,5 ATR (la Rev 1 aveva il migliore al bordo, 1,0).  Resto come la regola di partenza.
Uso (nella cartella dati):  python ../ottimizza_btc_guida_rev2.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ottimizza_btc_guida_rev1 as O

def main():
    X = O.Dati()
    anni = list(range(time.gmtime(X.D.t0).tm_year, time.gmtime(X.D.t1).tm_year + 1))
    print(f"\nVerifica dal {time.strftime('%Y-%m-%d', time.gmtime(X.taglio))}. Rischio 0,75 %, massimo 5 posizioni.")
    ingressi = [("BTC 2 ATR", dict(modo="atr", btc=2.0)), ("BTC +1 %", dict(modo="pct_atr", btc_pct=0.01)),
                ("BTC +1,25 %", dict(modo="pct_atr", btc_pct=0.0125))]
    migliori = []
    for nome, ing in ingressi:
        for mon in (1.5, 1.7, 2.0):
            print(f"\n   {nome}, monete oltre {mon} ATR".replace(".", ",") + "   (Valore = stop iniziale in ATR)\n" + O.TESTA)
            for stop in (0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5):
                p = dict(O.BASE, **ing, moneta=mon, stop=stop)
                r = O.misura(X, p)
                print(O.riga(str(stop), r))
                if r: migliori.append((r["s10"], nome, mon, stop, r))
    print("\nLE 5 PIU' SOLIDE (ordinate per R senza le 10 operazioni migliori)\n")
    for s10, nome, mon, stop, r in sorted(migliori, key=lambda x: -x[0])[:5]:
        print(f"   {nome}, monete {mon} ATR, stop {stop} ATR".replace(".", ",") + f":  {r['n']:.0f} oper./anno, "
              f"annuo {r['annuo'] * 100:+.0f} %, calo {r['calo'] * 100:+.0f} %, R verifica {r['ve']:+.2f}, senza 10 {s10:+.2f}".replace(".", ","))
        print("      " + O.anni_riga(r, anni))
    print("\n🟢 oltre +0,05 R in prova, verifica e senza le 10 migliori, calo entro il -20 %   🟡 positiva ma debole   🔴 no")

if __name__ == "__main__":
    main()
