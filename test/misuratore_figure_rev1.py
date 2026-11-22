#!/usr/bin/env python3
"""
MISURATORE DI FIGURE - Rev 1
Misura sui dati storici dei perpetui Kraken quali figure di analisi tecnica
hanno davvero un vantaggio, con le regole di ingresso/uscita concordate.

Figure grafiche: doppio minimo/massimo, triplo minimo/massimo, testa e spalle
(e rovesciato), triangoli (ascendente, discendente, simmetrico), rettangolo,
cunei (rialzista, ribassista), bandiere.
Candele (solo in zona di ritracciamento): engulfing, hammer/shooting star,
stella del mattino/della sera.

Regole di ogni operazione simulata:
  ingresso  alla chiusura della candela che completa/rompe la figura
  stop      oltre l'estremo della figura + 0,5 ATR
  obiettivo 2 volte la distanza dello stop
  uscita    a tempo dopo N candele; operazione scartata se lo stop e' < 0,4 % o > 4 %
  costi     commissione taker + slittamento su entrata e uscita
Risultati in "R" = multipli del rischio (R = -1 stop pieno, +2 obiettivo pieno).

Uso:
  python misuratore_figure_rev1.py                    # BTC, ETH, SOL, XRP - candele 1h, 3 anni
  python misuratore_figure_rev1.py --tf 4h
  python misuratore_figure_rev1.py --simboli PF_XBTUSD,PF_ETHUSD --anni 2
  python misuratore_figure_rev1.py --dettagli         # anche senza filtro trend e conteggi
  python misuratore_figure_rev1.py --csv mio.csv      # time,open,high,low,close (time in secondi)
Solo libreria standard Python 3.8+. Nessuna chiave API (dati pubblici).
"""
import argparse, csv, json, os, sys, time, random, urllib.request
from collections import defaultdict

# ------------------------- PARAMETRI -------------------------
CFG = dict(
    pivot_k=5,          # un massimo/minimo e' "pivot" se domina 5 candele per lato
    atr_n=14,
    stop_buffer=0.5,    # x ATR oltre l'estremo della figura
    rr=2.0,             # obiettivo = 2 x rischio
    max_bars=48,        # uscita a tempo (candele)
    min_stop=0.004,     # stop minimo 0,4 %
    max_stop=0.04,      # stop massimo 4 %
    fee=0.0005,         # taker futures Kraken livello base 0,05 %
    slip=0.0002,        # slittamento stimato per lato
    tol=1.0,            # tolleranza "stesso livello" in ATR
    quota_prova=0.6,    # primo 60 % dei dati = prova, ultimo 40 % = verifica
    min_n=30,           # operazioni minime in verifica per un verde
    soglia=0.05,        # R medio minimo per un verde
)
API = "https://futures.kraken.com/api/charts/v1/trade/{sym}/1h?from={a}&to={b}"

# ------------------------- DATI -------------------------
def scarica(sym, anni):
    cache = f"{sym}_1h.csv"
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < 6 * 3600:
        return leggi_csv(cache)
    fine = int(time.time()); inizio = fine - int(anni * 365 * 86400)
    righe, t = {}, inizio
    passo = 1500 * 3600
    while t < fine:
        url = API.format(sym=sym, a=t, b=min(t + passo, fine))
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                js = json.load(r)
        except Exception as e:
            sys.exit(f"Errore nello scaricare {sym}: {e}")
        for c in js.get("candles", []):
            ts = int(c["time"]) // 1000
            righe[ts] = (ts, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]))
        t += passo
        print(f"\r{sym}: {len(righe)} candele scaricate", end="", flush=True)
        time.sleep(0.3)
    print()
    bars = [righe[k] for k in sorted(righe)][:-1]      # l'ultima candela e' ancora aperta
    with open(cache, "w", newline="") as f:
        csv.writer(f).writerows(bars)
    return bars

def leggi_csv(path):
    out = []
    with open(path) as f:
        for r in csv.reader(f):
            try:
                out.append((int(float(r[0])), float(r[1]), float(r[2]), float(r[3]), float(r[4])))
            except (ValueError, IndexError):
                continue
    return out

def aggrega(bars, n):
    out, gruppo = [], []
    for b in bars:
        chiave = b[0] // (3600 * n)
        if gruppo and gruppo[0][0] // (3600 * n) != chiave:
            out.append((gruppo[0][0], gruppo[0][1], max(x[2] for x in gruppo), min(x[3] for x in gruppo), gruppo[-1][4]))
            gruppo = []
        gruppo.append(b)
    return out

# ------------------------- INDICATORI -------------------------
def ema(v, n):
    k, out, e = 2 / (n + 1), [], None
    for x in v:
        e = x if e is None else x * k + e * (1 - k)
        out.append(e)
    return out

def atr(H, L, C, n):
    out, a = [], None
    for i in range(len(C)):
        tr = H[i] - L[i] if i == 0 else max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1]))
        a = tr if a is None else (a * (n - 1) + tr) / n
        out.append(a)
    return out

# ------------------------- SIMULAZIONE DI UNA OPERAZIONE -------------------------
def simula(i, d, stop, H, L, C, cfg):
    """d = +1 long, -1 short. Ritorna R netto oppure None se scartata."""
    e = C[i]
    rischio = (e - stop) * d
    if rischio <= 0:
        return None
    pct = rischio / e
    if pct < cfg["min_stop"] or pct > cfg["max_stop"]:
        return None
    tp = e + d * cfg["rr"] * rischio
    fine = min(i + cfg["max_bars"], len(C) - 1)
    if fine <= i:
        return None
    r = None
    for j in range(i + 1, fine + 1):
        if d == 1:
            if L[j] <= stop: r = -1.0; break          # se nella stessa candela tocca entrambi, conta lo stop
            if H[j] >= tp:   r = cfg["rr"]; break
        else:
            if H[j] >= stop: r = -1.0; break
            if L[j] <= tp:   r = cfg["rr"]; break
    if r is None:
        r = (C[fine] - e) * d / rischio
    return r - 2 * (cfg["fee"] + cfg["slip"]) / pct

# ------------------------- RICONOSCIMENTO -------------------------
def analizza(bars, cfg, m_trend):
    """Ritorna lista di (nome, indice, direzione, in_trend, R)."""
    O = [b[1] for b in bars]; H = [b[2] for b in bars]; L = [b[3] for b in bars]; C = [b[4] for b in bars]
    n = len(C)
    A = atr(H, L, C, cfg["atr_n"])
    ef, es = ema(C, 50 * m_trend), ema(C, 200 * m_trend)
    e20, e50 = ema(C, 20), ema(C, 50)
    k, tol, buf = cfg["pivot_k"], cfg["tol"], cfg["stop_buffer"]
    piv = []                       # (indice, 'H'/'L', prezzo), alternati
    usati = set()
    segnali = []
    caldo = 200 * m_trend

    def emetti(nome, i, d, stop, chiave):
        if (nome, chiave) in usati:
            return
        usati.add((nome, chiave))
        r = simula(i, d, stop, H, L, C, cfg)
        if r is None:
            return
        in_trend = (ef[i] > es[i]) if d == 1 else (ef[i] < es[i])
        segnali.append((nome + (" ▲" if d == 1 else " ▼"), i, d, in_trend, r))

    def retta(p1, p2, x):
        return p1[2] + (p2[2] - p1[2]) * (x - p1[0]) / (p2[0] - p1[0])

    for i in range(n):
        # --- aggiorna i pivot (confermati k candele dopo: nessuna sbirciata nel futuro)
        j = i - k
        if j >= k:
            if H[j] == max(H[j - k:j + k + 1]):
                if piv and piv[-1][1] == 'H':
                    if H[j] > piv[-1][2]: piv[-1] = (j, 'H', H[j])
                else:
                    piv.append((j, 'H', H[j]))
            elif L[j] == min(L[j - k:j + k + 1]):
                if piv and piv[-1][1] == 'L':
                    if L[j] < piv[-1][2]: piv[-1] = (j, 'L', L[j])
                else:
                    piv.append((j, 'L', L[j]))
        if i < caldo or i < 2:
            continue
        a = A[i]; c = C[i]; cp = C[i - 1]

        # --- riferimento: ingresso senza figura, ogni 7 candele, nel verso del trend
        if i % 7 == 0:
            d = 1 if ef[i] > es[i] else -1
            emetti("Ingresso a caso", i, d, c - d * 1.5 * a, i)

        P = piv[-5:]
        # --- doppio minimo / doppio massimo
        if len(P) >= 3:
            p1, p2, p3 = P[-3], P[-2], P[-1]
            if p3[1] == 'L' and abs(p3[2] - p1[2]) <= tol * a and p2[2] - max(p1[2], p3[2]) >= 2 * a \
               and p3[0] - p1[0] >= 10 and c > p2[2] >= cp:
                emetti("Doppio minimo", i, 1, min(p1[2], p3[2]) - buf * a, (p1[0], p3[0]))
            if p3[1] == 'H' and abs(p3[2] - p1[2]) <= tol * a and min(p1[2], p3[2]) - p2[2] >= 2 * a \
               and p3[0] - p1[0] >= 10 and c < p2[2] <= cp:
                emetti("Doppio massimo", i, -1, max(p1[2], p3[2]) + buf * a, (p1[0], p3[0]))
        if len(P) >= 5:
            q1, q2, q3, q4, q5 = P
            # --- triplo minimo / triplo massimo
            if q5[1] == 'L':
                lows = (q1[2], q3[2], q5[2]); top = max(q2[2], q4[2])
                if max(lows) - min(lows) <= 1.5 * tol * a and top - max(lows) >= 2 * a and c > top >= cp:
                    emetti("Triplo minimo", i, 1, min(lows) - buf * a, (q1[0], q5[0]))
                # --- testa e spalle rovesciato: spalla, collo, testa, collo, spalla
                if q3[2] < q1[2] - a and q3[2] < q5[2] - a and abs(q1[2] - q5[2]) <= 1.5 * tol * a:
                    collo, collo_p = retta(q2, q4, i), retta(q2, q4, i - 1)
                    if c > collo and cp <= collo_p:
                        emetti("Testa e spalle rovesciato", i, 1, q5[2] - buf * a, (q1[0], q5[0]))
            if q5[1] == 'H':
                highs = (q1[2], q3[2], q5[2]); bot = min(q2[2], q4[2])
                if max(highs) - min(highs) <= 1.5 * tol * a and min(highs) - bot >= 2 * a and c < bot <= cp:
                    emetti("Triplo massimo", i, -1, max(highs) + buf * a, (q1[0], q5[0]))
                if q3[2] > q1[2] + a and q3[2] > q5[2] + a and abs(q1[2] - q5[2]) <= 1.5 * tol * a:
                    collo, collo_p = retta(q2, q4, i), retta(q2, q4, i - 1)
                    if c < collo and cp >= collo_p:
                        emetti("Testa e spalle", i, -1, q5[2] + buf * a, (q1[0], q5[0]))

        # --- figure a due rette (ultimi 2 massimi e 2 minimi)
        if len(P) >= 4:
            ult = P[-4:]
            hs = [p for p in ult if p[1] == 'H']; ls = [p for p in ult if p[1] == 'L']
            x0, x1 = ult[0][0], ult[-1][0]
            durata = x1 - x0
            if len(hs) == 2 and len(ls) == 2 and durata >= 15 and i - x1 <= durata:
                dh, dl = (hs[1][2] - hs[0][2]) / a, (ls[1][2] - ls[0][2]) / a
                su, giu = retta(hs[0], hs[1], i), retta(ls[0], ls[1], i)
                su_p, giu_p = retta(hs[0], hs[1], i - 1), retta(ls[0], ls[1], i - 1)
                w0 = retta(hs[0], hs[1], x0) - retta(ls[0], ls[1], x0)
                w1 = retta(hs[0], hs[1], x1) - retta(ls[0], ls[1], x1)
                piatto = lambda v: abs(v) <= 1.0
                nome = None
                if w0 > 0 and w1 > 0 and su > giu:
                    if piatto(dh) and dl > 1.0:              nome = "Triangolo ascendente"
                    elif dh < -1.0 and piatto(dl):           nome = "Triangolo discendente"
                    elif dh < -1.0 and dl > 1.0:             nome = "Triangolo simmetrico"
                    elif piatto(dh) and piatto(dl):          nome = "Rettangolo"
                    elif dh > 1.0 and dl > 1.0 and w1 < 0.8 * w0:   nome = "Cuneo rialzista"
                    elif dh < -1.0 and dl < -1.0 and w1 < 0.8 * w0: nome = "Cuneo ribassista"
                if nome:
                    chiave = (ult[0][0], ult[-1][0])
                    if c > su and cp <= su_p:
                        emetti(nome, i, 1, ls[1][2] - buf * a, chiave)
                    elif c < giu and cp >= giu_p:
                        emetti(nome, i, -1, hs[1][2] + buf * a, chiave)

        # --- bandiere: impulso di 8 candele >= 4 ATR, pausa stretta di 5-20 candele, rottura
        for lung in range(5, 21):
            pe = i - lung - 1; ps = pe - 8
            if ps < 0:
                break
            imp = C[pe] - C[ps]
            if abs(imp) < 4 * A[pe]:
                continue
            ch, cl = max(H[pe + 1:i]), min(L[pe + 1:i])
            if ch - cl > 0.5 * abs(imp):
                continue
            if imp > 0 and cl >= C[pe] - 0.5 * imp and c > ch:
                emetti("Bandiera", i, 1, cl - buf * a, pe); break
            if imp < 0 and ch <= C[pe] - 0.5 * imp and c < cl:
                emetti("Bandiera", i, -1, ch + buf * a, pe); break

        # --- candele, solo nella zona di ritracciamento tra media 20 e media 50
        zt, zb = max(e20[i], e50[i]), min(e20[i], e50[i])
        corpo = abs(c - O[i]); rng = H[i] - L[i]
        corpo_p = abs(C[i - 1] - O[i - 1])
        zona_long = L[i] <= zt and c >= zb
        zona_short = H[i] >= zb and c <= zt
        if zona_long:
            if C[i - 1] < O[i - 1] and c > O[i] and O[i] <= C[i - 1] and c >= O[i - 1] and corpo >= 0.5 * a:
                emetti("Engulfing", i, 1, min(L[i], L[i - 1]) - buf * a, i)
            if rng >= 0.8 * a and min(O[i], c) - L[i] >= 2 * corpo and H[i] - max(O[i], c) <= 0.25 * rng:
                emetti("Hammer", i, 1, L[i] - buf * a, i)
            if C[i - 2] < O[i - 2] and O[i - 2] - C[i - 2] >= 0.7 * a and corpo_p <= 0.3 * a \
               and c > O[i] and c > (O[i - 2] + C[i - 2]) / 2:
                emetti("Stella del mattino", i, 1, min(L[i], L[i - 1], L[i - 2]) - buf * a, i)
        if zona_short:
            if C[i - 1] > O[i - 1] and c < O[i] and O[i] >= C[i - 1] and c <= O[i - 1] and corpo >= 0.5 * a:
                emetti("Engulfing", i, -1, max(H[i], H[i - 1]) + buf * a, i)
            if rng >= 0.8 * a and H[i] - max(O[i], c) >= 2 * corpo and min(O[i], c) - L[i] <= 0.25 * rng:
                emetti("Shooting star", i, -1, H[i] + buf * a, i)
            if C[i - 2] > O[i - 2] and C[i - 2] - O[i - 2] >= 0.7 * a and corpo_p <= 0.3 * a \
               and c < O[i] and c < (O[i - 2] + C[i - 2]) / 2:
                emetti("Stella della sera", i, -1, max(H[i], H[i - 1], H[i - 2]) + buf * a, i)
    return segnali, n

# ------------------------- STATISTICHE E TABELLA -------------------------
def media(v): return sum(v) / len(v) if v else 0.0

def riassumi(righe, cfg):
    """righe: lista di (R, in_verifica)."""
    pr = [r for r, v in righe if not v]; ve = [r for r, v in righe if v]
    tot = pr + ve
    vinte = sum(1 for r in tot if r > 0) / len(tot) if tot else 0
    mp, mv = media(pr), media(ve)
    mt = media(tot)
    sd = (sum((x - mt) ** 2 for x in tot) / len(tot)) ** 0.5 if tot else 0
    t = mt / (sd / len(tot) ** 0.5) if sd > 0 else 0      # solidita' statistica
    if len(tot) < 10:                                                    s = "⚪"
    elif len(ve) >= cfg["min_n"] and mp > cfg["soglia"] and mv > cfg["soglia"] and t >= 3.0: s = "🟢"
    elif mp > 0 and mv > 0:                                              s = "🟡"
    else:                                                                s = "🔴"
    return s, len(tot), vinte, mp, mv, len(pr), len(ve)

def stampa(titolo, gruppi, cfg, dettagli):
    print(f"\n{titolo}")
    print(f"{'':3}{'Figura':30}{'N':>6}{'Vinte':>7}{'R prova':>9}{'R verifica':>12}" + ("   (n prova / n verifica)" if dettagli else ""))
    ordine = {"🟢": 0, "🟡": 1, "🔴": 2, "⚪": 3}
    out = []
    for nome, righe in gruppi.items():
        out.append((nome,) + riassumi(righe, cfg))
    out.sort(key=lambda x: (x[0].startswith("Ingresso a caso"), ordine[x[1]], -x[5]))
    for nome, s, n, vinte, mp, mv, npr, nve in out:
        if s == "⚪" and not dettagli:
            continue
        extra = f"   ({npr} / {nve})" if dettagli else ""
        print(f"{s} {nome:30}{n:>6}{vinte * 100:>6.0f}%{mp:>+9.2f}{mv:>+12.2f}{extra}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simboli", default="PF_XBTUSD,PF_ETHUSD,PF_SOLUSD,PF_XRPUSD")
    ap.add_argument("--tf", default="1h", choices=["1h", "4h"])
    ap.add_argument("--anni", type=float, default=3)
    ap.add_argument("--csv", help="file time,open,high,low,close al posto dello scarico")
    ap.add_argument("--dettagli", action="store_true")
    args = ap.parse_args()

    con, senza = defaultdict(list), defaultdict(list)
    for sym in (["CSV"] if args.csv else args.simboli.split(",")):
        bars = leggi_csv(args.csv) if args.csv else scarica(sym, args.anni)
        if args.tf == "4h":
            bars = aggrega(bars, 4)
        m = 4 if args.tf == "1h" else 1          # trend: medie 50/200 su 4 ore
        if args.tf == "4h":
            CFG["max_stop"] = 0.08               # figure piu' ampie: stop ammesso fino all'8 %
        if len(bars) < 200 * m + 500:
            sys.exit(f"{sym}: troppi pochi dati ({len(bars)} candele)")
        segnali, n = analizza(bars, CFG, m)
        taglio = int(n * CFG["quota_prova"])
        for nome, i, d, in_trend, r in segnali:
            senza[nome].append((r, i >= taglio))
            if in_trend or nome.startswith("Ingresso a caso"):
                con[nome].append((r, i >= taglio))
        print(f"{sym}: {n} candele {args.tf}, {len(segnali)} segnali")

    stampa("CON FILTRO TREND (la strategia concordata)", con, CFG, args.dettagli)
    if args.dettagli:
        stampa("SENZA FILTRO TREND", senza, CFG, True)
    print("""
▲ = ingresso long   ▼ = ingresso short
R = guadagno medio per operazione in multipli del rischio, costi inclusi
    (+0,10 con rischio 1 % = +0,1 % del capitale a operazione)
🟢 positivo sia in prova (primo 60 %) sia in verifica (ultimo 40 %), almeno 30 casi in verifica,
   e troppo netto per essere fortuna (t >= 3)
🟡 positivo in entrambi ma con pochi casi o margine minimo: non basta
🔴 non regge   ⚪ meno di 10 casi (visibili con --dettagli)
Con una ventina di righe, 1 o 2 verdi possono uscire per puro caso: un verde va confermato
su un'altra moneta o un altro intervallo prima di fidarsi.""")

if __name__ == "__main__":
    main()
