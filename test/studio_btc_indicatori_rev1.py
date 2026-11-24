#!/usr/bin/env python3
"""
STUDIO BTC INDICATORI - Rev 1
BTC, candele da 1 ora, ultimi 4 anni (perpetuo Kraken PF_XBTUSD).

Ogni ora si calcolano 7 indicatori (solo con dati fino a quell'ora):
  1 RSI         RSI a 14 ore (0-100; sotto 30 = ipervenduto, sopra 70 = ipercomprato)
  2 MACD        istogramma MACD 12/26/9 in % del prezzo (positivo = spinta in su)
  3 Bollinger   posizione nelle bande 20/2 (0 = banda bassa, 1 = banda alta)
  4 ADX         forza del trend a 14 ore (sotto 20 = laterale, sopra 30 = trend forte)
  5 Volatilita' ATR 14 diviso la sua mediana dell'ultimo mese (1 = normale, 0,5 = mercato fermo)
  6 Media 200   distanza del prezzo dalla media a 200 ore, in %
  7 Ultime 24h  rendimento delle ultime 24 ore, in %

Poi, per ogni ora, si guarda cosa e' successo DOPO partendo dalla chiusura:
  ha toccato prima +10 % o prima -10 %?
  "Partenza pulita long"  = arriva a +10 % prima di scendere del 3 % (il trade che vorremmo prendere)
  "Partenza pulita short" = arriva a -10 % prima di salire del 3 %
Si confrontano gli indicatori di queste partenze con quelli di un'ora qualsiasi, e si guarda come
erano 48, 24, 6 ore prima e come diventano 6 e 24 ore dopo.
Infine, la prova vera: dividendo ogni indicatore in 5 fasce (stabilite sul primo 60 % dei dati),
in quale fascia le partenze pulite sono piu' frequenti, e se resta cosi' anche nell'ultimo 40 %.

Uso (nella cartella dati):  python ../studio_btc_indicatori_rev1.py
Solo libreria standard Python 3.8+.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica

ANNI = 4
OBIETTIVO, STOP = 0.10, 0.03

def ema(v, n):
    a, out, e = 2 / (n + 1), [], None
    for x in v:
        e = x if e is None else e + a * (x - e); out.append(e)
    return out

def wilder(v, n):
    out, e = [], None
    for x in v:
        e = x if e is None else (e * (n - 1) + x) / n; out.append(e)
    return out

def indicatori(H, L, C):
    n = len(C)
    su = [0.0] + [max(C[i] - C[i - 1], 0) for i in range(1, n)]
    giu = [0.0] + [max(C[i - 1] - C[i], 0) for i in range(1, n)]
    ms, mg = wilder(su, 14), wilder(giu, 14)
    rsi = [100 - 100 / (1 + ms[i] / mg[i]) if mg[i] else 100.0 for i in range(n)]
    macd = [a - b for a, b in zip(ema(C, 12), ema(C, 26))]
    seg = ema(macd, 9)
    isto = [(macd[i] - seg[i]) / C[i] * 100 for i in range(n)]
    boll = [None] * n
    for i in range(19, n):
        w = C[i - 19:i + 1]; m = sum(w) / 20; sd = (sum((x - m) ** 2 for x in w) / 20) ** 0.5
        boll[i] = (C[i] - (m - 2 * sd)) / (4 * sd) if sd else 0.5
    tr = [H[0] - L[0]] + [max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1])) for i in range(1, n)]
    dmp = [0.0] + [(H[i] - H[i - 1]) if (H[i] - H[i - 1]) > (L[i - 1] - L[i]) and H[i] > H[i - 1] else 0.0 for i in range(1, n)]
    dmm = [0.0] + [(L[i - 1] - L[i]) if (L[i - 1] - L[i]) > (H[i] - H[i - 1]) and L[i] < L[i - 1] else 0.0 for i in range(1, n)]
    atr, sp, sm = wilder(tr, 14), wilder(dmp, 14), wilder(dmm, 14)
    dx = []
    for i in range(n):
        dip, dim = (sp[i] / atr[i] * 100, sm[i] / atr[i] * 100) if atr[i] else (0, 0)
        dx.append(abs(dip - dim) / (dip + dim) * 100 if dip + dim else 0)
    adx = wilder(dx, 14)
    vol = [None] * n
    for i in range(720, n, 1):
        if i % 24 == 0 or vol[i - 1] is None:
            med = sorted(atr[i - 720:i])[360]
        vol[i] = atr[i] / med if med else None
    m200 = [None] * n; s = 0.0
    for i in range(n):
        s += C[i]
        if i >= 200: s -= C[i - 200]
        if i >= 199: m200[i] = (C[i] / (s / 200) - 1) * 100
    r24 = [None] * 24 + [(C[i] / C[i - 24] - 1) * 100 for i in range(24, n)]
    return {"RSI": rsi, "MACD %": isto, "Bollinger": boll, "ADX": adx, "Volatilita'": vol,
            "Media 200 %": m200, "Ultime 24h %": r24}

def esiti(H, L, C):
    """Per ogni ora: chi tocca prima (+10/-10), ore impiegate, partenza pulita long/short."""
    n = len(C); prima = [None] * n; ore = [None] * n; pulita_l = [False] * n; pulita_s = [False] * n
    for i in range(n):
        e = C[i]; su, giu = e * (1 + OBIETTIVO), e * (1 - OBIETTIVO)
        sl_l, sl_s = e * (1 - STOP), e * (1 + STOP)
        fatto_l = fatto_s = False
        for j in range(i + 1, n):
            if not fatto_l:
                if L[j] <= sl_l: fatto_l = True
                elif H[j] >= su: pulita_l[i] = True; fatto_l = True
            if not fatto_s:
                if H[j] >= sl_s: fatto_s = True
                elif L[j] <= giu: pulita_s[i] = True; fatto_s = True
            if prima[i] is None:
                if H[j] >= su and L[j] <= giu: prima[i] = 0; ore[i] = j - i
                elif H[j] >= su: prima[i] = 1; ore[i] = j - i
                elif L[j] <= giu: prima[i] = -1; ore[i] = j - i
            if fatto_l and fatto_s and prima[i] is not None: break
    return prima, ore, pulita_l, pulita_s

def mediana(v):
    v = sorted(x for x in v if x is not None)
    return v[len(v) // 2] if v else None

def episodi(flag, idx):
    """Conta i gruppi di ore consecutive (separati da oltre 24 ore)."""
    k, ultimo = 0, -99
    for i in idx:
        if flag[i]:
            if i - ultimo > 24: k += 1
            ultimo = i
    return k

def f(x, nome):
    if x is None: return "   -"
    if nome in ("RSI", "ADX"): return f"{x:.0f}"
    if nome in ("Bollinger", "Volatilita'"): return f"{x:.2f}".replace(".", ",")
    return f"{x:+.2f}".replace(".", ",")

def main():
    b = carica("XBT", 1)
    if not b: sys.exit("Mancano i dati di BTC.")
    inizio = b[-1][0] - ANNI * 365 * 86400
    b = [x for x in b if x[0] >= inizio - 800 * 3600]          # 800 ore in piu' per scaldare gli indicatori
    T = [x[0] for x in b]; H = [x[2] for x in b]; L = [x[3] for x in b]; C = [x[4] for x in b]
    I = indicatori(H, L, C)
    prima, ore, pl, ps = esiti(H, L, C)
    i0 = next(i for i, t in enumerate(T) if t >= inizio)
    validi = [i for i in range(max(i0, 800), len(C)) if prima[i] is not None]
    taglio = validi[int(len(validi) * 0.6)]
    prova = [i for i in validi if i < taglio]; verifica = [i for i in validi if i >= taglio]
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\nBTC 1 ora dal {d(T[validi[0]])} al {d(T[validi[-1]])} ({len(validi)} ore con esito noto)."
          f" Prova fino al {d(T[taglio])}, verifica dopo.\n")

    # 1) quadro generale
    print("1) COSA SUCCEDE DOPO UN'ORA QUALSIASI")
    for nome, idx in (("Prova", prova), ("Verifica", verifica)):
        nl = sum(1 for i in idx if prima[i] == 1); ns = sum(1 for i in idx if prima[i] == -1)
        print(f"   {nome:9} prima +10 %: {nl / len(idx) * 100:4.0f} % delle ore (in mediana dopo {mediana([ore[i] for i in idx if prima[i] == 1]) / 24:.0f} giorni)"
              f"   prima -10 %: {ns / len(idx) * 100:4.0f} % (dopo {mediana([ore[i] for i in idx if prima[i] == -1]) / 24:.0f} giorni)")
        print(f"   {'':9} partenze pulite long: {sum(pl[i] for i in idx) / len(idx) * 100:4.1f} % delle ore ({episodi(pl, idx)} episodi)"
              f"   short: {sum(ps[i] for i in idx) / len(idx) * 100:4.1f} % ({episodi(ps, idx)} episodi)")
    print()

    # 2) come erano gli indicatori prima, durante e dopo le partenze pulite (mediane, tutti i dati)
    print("2) VALORE TIPICO (mediana) DEGLI INDICATORI INTORNO ALLE PARTENZE PULITE")
    passi = [-48, -24, -6, 0, 6, 24]
    intest = f"   {'Indicatore':14}{'Ora qualsiasi':>14}  |" + "".join(f"{('ora 0' if p == 0 else f'{p:+d}h'):>8}" for p in passi)
    for gruppo, flag in (("LONG (poi +10 % senza toccare -3 %)", pl), ("SHORT (poi -10 % senza toccare +3 %)", ps)):
        print(f"   --- partenze {gruppo} ---")
        print(intest)
        for nome, v in I.items():
            base = mediana([v[i] for i in validi])
            celle = "".join(f"{f(mediana([v[i + p] for i in validi if flag[i] and 0 <= i + p < len(v)]), nome):>8}" for p in passi)
            print(f"   {nome:14}{f(base, nome):>14}  |{celle}")
    print()

    # 3) prova vera: fasce stabilite sulla prova
    print("3) GLI INDICATORI ANTICIPANO LE PARTENZE?  % di ore che diventano partenza pulita, per fascia")
    print("   Fasce = quinti dei valori nel periodo di prova (F1 = valori piu' bassi, F5 = piu' alti).")
    tot_l = (sum(pl[i] for i in prova) / len(prova), sum(pl[i] for i in verifica) / len(verifica))
    tot_s = (sum(ps[i] for i in prova) / len(prova), sum(ps[i] for i in verifica) / len(verifica))
    print(f"   Media di tutte le ore: long {tot_l[0] * 100:.1f} % prova / {tot_l[1] * 100:.1f} % verifica,"
          f" short {tot_s[0] * 100:.1f} % / {tot_s[1] * 100:.1f} %")
    print(f"   {'Indicatore':14}{'Verso':7}" + "".join(f"{'F' + str(k + 1) + ' prova/verif.':>18}" for k in range(5)) + "   Segnale")
    for nome, v in I.items():
        valori = sorted(v[i] for i in prova if v[i] is not None)
        soglie = [valori[int(len(valori) * q)] for q in (0.2, 0.4, 0.6, 0.8)]
        fascia = lambda x: sum(x > s for s in soglie)
        for verso, flag, tot in (("long", pl, tot_l), ("short", ps, tot_s)):
            celle, rapporti = "", []
            for k in range(5):
                rp = [flag[i] for i in prova if v[i] is not None and fascia(v[i]) == k]
                rv = [flag[i] for i in verifica if v[i] is not None and fascia(v[i]) == k]
                a = sum(rp) / len(rp) if rp else 0; c = sum(rv) / len(rv) if rv else 0
                rapporti.append((a / tot[0] if tot[0] else 0, c / tot[1] if tot[1] else 0, len(rv)))
                celle += f"{f'{a * 100:.1f}/{c * 100:.1f}':>18}"
            # segnale: una fascia con almeno 1,5 volte la media sia in prova sia in verifica
            buone = [f"F{k + 1}" for k, (x, y, nv) in enumerate(rapporti) if x >= 1.5 and y >= 1.5 and nv >= 200]
            print(f"   {nome:14}{verso:7}{celle}   {'🟢 ' + ','.join(buone) if buone else '🔴'}")
    print("""
Come leggere la tabella 3: se in una fascia la % di partenze pulite e' almeno 1,5 volte la media
sia in prova sia in verifica (🟢), quell'indicatore in quella fascia anticipa davvero i movimenti.
Se le percentuali sono simili in tutte le fasce, l'indicatore non dice nulla sul movimento futuro.
Attenzione: le ore consecutive di una stessa partenza contano tutte; gli "episodi" in alto dicono
quanti movimenti diversi ci sono davvero.""")

if __name__ == "__main__":
    main()
