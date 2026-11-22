#!/usr/bin/env python3
"""
Backtest "compra i ritracciamenti in trend rialzista" su dati Kraken.

Confronta tre cose sugli stessi dati:
  A) uscita SOLO in guadagno (take profit), le perdenti restano aperte
  B) take profit + chiusura di tutto a mercato quando il trend finisce
  BH) compra e tieni (riferimento)

Uso:
  python backtest_trend_pullback.py                       # XBTEUR, candele giornaliere da API (ultime 720)
  python backtest_trend_pullback.py --pair ETHEUR --interval 240
  python backtest_trend_pullback.py --csv XBTEUR_60.csv   # storico lungo scaricato da Kraken (OHLCVT)
  python backtest_trend_pullback.py --csv XBTEUR_60.csv --grid   # ottimizza su 60 % dei dati, verifica sul 40 %

Solo libreria standard Python 3.8+, nessuna installazione.
"""
import argparse, csv, json, sys, urllib.request, itertools
from datetime import datetime, timezone

# ---------------- PARAMETRI (modificabili) ----------------
P = dict(
    ema_fast=50,        # trend: EMA veloce sopra EMA lenta e prezzo sopra EMA lenta
    ema_slow=200,
    lookback=20,        # massimo recente su cui misurare il ritracciamento
    dip=0.03,           # compra se il prezzo è sceso del 3 % dal massimo recente
    tp=0.03,            # take profit +3 % dal prezzo di ingresso
    size=0.10,          # ogni posizione = 10 % del capitale iniziale
    max_pos=10,         # massimo posizioni aperte insieme
    spacing=0.02,       # nuova posizione solo se lontana almeno 2 % da quelle aperte
    fee_maker=0.0040,   # Kraken Pro Tier 1 (luglio 2026): 0,40 % ordini limite
    fee_taker=0.0080,   #                                    0,80 % ordini a mercato
    capital=10000.0,
)

# ---------------- DATI ----------------
def load_api(pair, interval):
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    with urllib.request.urlopen(url, timeout=30) as r:
        js = json.load(r)
    if js.get("error"):
        sys.exit(f"Errore Kraken: {js['error']}")
    key = [k for k in js["result"] if k != "last"][0]
    rows = js["result"][key]
    # [time, open, high, low, close, vwap, volume, count]; l'ultima candela è ancora aperta
    return [(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows[:-1]]

def load_csv(path):
    # formato Kraken OHLCVT: timestamp,open,high,low,close,volume,trades (senza intestazione)
    out = []
    with open(path) as f:
        for r in csv.reader(f):
            try:
                out.append((int(float(r[0])), float(r[1]), float(r[2]), float(r[3]), float(r[4])))
            except (ValueError, IndexError):
                continue  # salta eventuale intestazione
    return out

# ---------------- INDICATORI ----------------
def ema(values, n):
    k, out, e = 2 / (n + 1), [], None
    for v in values:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out

# ---------------- MOTORE ----------------
def run(bars, p, trend_exit):
    closes = [b[4] for b in bars]
    ef, es = ema(closes, p["ema_fast"]), ema(closes, p["ema_slow"])
    cash, cap = p["capital"], p["capital"]
    open_pos = []          # dict(entry, qty, bar)
    closed = []            # pnl in euro, durata in barre
    equity, max_inv = [], 0.0
    warm = max(p["ema_slow"], p["lookback"])

    for i in range(len(bars)):
        t, o, h, l, c = bars[i]
        trend = i >= warm and c > es[i] and ef[i] > es[i]

        # 1) take profit (ordine limite già piazzato -> maker)
        still = []
        for pos in open_pos:
            target = pos["entry"] * (1 + p["tp"])
            if pos["bar"] < i and h >= target:
                proceeds = pos["qty"] * target * (1 - p["fee_maker"])
                cash += proceeds
                closed.append((proceeds - pos["cost"], i - pos["bar"]))
            else:
                still.append(pos)
        open_pos = still

        # 2) variante B: trend finito -> chiudi tutto a mercato (taker)
        if trend_exit and i >= warm and not trend and open_pos:
            for pos in open_pos:
                proceeds = pos["qty"] * c * (1 - p["fee_taker"])
                cash += proceeds
                closed.append((proceeds - pos["cost"], i - pos["bar"]))
            open_pos = []

        # 3) ingresso: trend rialzista + ritracciamento dal massimo recente
        if trend and len(open_pos) < p["max_pos"]:
            recent_high = max(b[2] for b in bars[i - p["lookback"]:i])
            far = all(abs(c / pos["entry"] - 1) >= p["spacing"] for pos in open_pos)
            spend = cap * p["size"]
            if c <= recent_high * (1 - p["dip"]) and far and cash >= spend:
                qty = spend * (1 - p["fee_maker"]) / c
                cash -= spend
                open_pos.append(dict(entry=c, qty=qty, bar=i, cost=spend))

        invested = sum(pos["cost"] for pos in open_pos)
        max_inv = max(max_inv, invested / cap)
        equity.append(cash + sum(pos["qty"] * c for pos in open_pos))

    last = closes[-1]
    unreal = sum(pos["qty"] * last - pos["cost"] for pos in open_pos)
    oldest = max((len(bars) - 1 - pos["bar"] for pos in open_pos), default=0)
    return dict(
        ret=equity[-1] / cap - 1,
        dd=max_drawdown(equity),
        n=len(closed),
        win=sum(1 for x in closed if x[0] > 0) / len(closed) if closed else 0,
        avg=sum(x[0] for x in closed) / len(closed) if closed else 0,
        hold=sum(x[1] for x in closed) / len(closed) if closed else 0,
        open_n=len(open_pos), unreal=unreal, oldest=oldest, max_inv=max_inv,
    )

def max_drawdown(eq):
    peak, dd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        dd = min(dd, v / peak - 1)
    return dd

def buy_hold(bars, p):
    c0, c1 = bars[0][4], bars[-1][4]
    eq = [b[4] / c0 for b in bars]
    return dict(ret=(c1 / c0) * (1 - p["fee_taker"]) ** 2 - 1, dd=max_drawdown(eq))

# ---------------- REPORT ----------------
def pct(x): return f"{x*100:+.1f} %"

def report(title, bars, p):
    d0 = datetime.fromtimestamp(bars[0][0], timezone.utc).date()
    d1 = datetime.fromtimestamp(bars[-1][0], timezone.utc).date()
    a, b, bh = run(bars, p, False), run(bars, p, True), buy_hold(bars, p)
    print(f"\n=== {title}: {d0} -> {d1}  ({len(bars)} candele) ===")
    print(f"{'':28}{'A: solo TP':>14}{'B: TP + uscita':>16}{'Compra&tieni':>14}")
    print(f"{'Rendimento totale':28}{pct(a['ret']):>14}{pct(b['ret']):>16}{pct(bh['ret']):>14}")
    print(f"{'Max drawdown':28}{pct(a['dd']):>14}{pct(b['dd']):>16}{pct(bh['dd']):>14}")
    print(f"{'Operazioni chiuse':28}{a['n']:>14}{b['n']:>16}")
    print(f"{'% operazioni vincenti':28}{a['win']*100:>13.0f}%{b['win']*100:>15.0f}%")
    print(f"{'Utile medio per operaz. (EUR)':28}{a['avg']:>14.1f}{b['avg']:>16.1f}")
    print(f"{'Durata media (candele)':28}{a['hold']:>14.1f}{b['hold']:>16.1f}")
    print(f"{'Posizioni ancora aperte':28}{a['open_n']:>14}{b['open_n']:>16}")
    print(f"{'  di cui perdita latente EUR':28}{a['unreal']:>14.0f}{b['unreal']:>16.0f}")
    print(f"{'  la più vecchia (candele)':28}{a['oldest']:>14}{b['oldest']:>16}")
    print(f"{'Max capitale impegnato':28}{a['max_inv']*100:>13.0f}%{b['max_inv']*100:>15.0f}%")
    return a, b, bh

def grid(train, test, base):
    best = None
    for dip, tp, lb in itertools.product([0.02, 0.03, 0.05, 0.08], [0.02, 0.03, 0.05, 0.08], [10, 20, 50]):
        p = dict(base, dip=dip, tp=tp, lookback=lb)
        r = run(train, p, True)["ret"]
        if best is None or r > best[0]:
            best = (r, p)
    p = best[1]
    print(f"\nMigliori parametri sul 60 % iniziale: dip={p['dip']}, tp={p['tp']}, lookback={p['lookback']}")
    report("IN-SAMPLE (ottimizzato)", train, p)
    report("OUT-OF-SAMPLE (mai visto)", test, p)
    print("\nSe il risultato out-of-sample crolla rispetto all'in-sample, i parametri erano solo adattati al passato.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="XBTEUR")
    ap.add_argument("--interval", type=int, default=1440, help="minuti: 60, 240, 1440...")
    ap.add_argument("--csv", help="file OHLCVT scaricato da Kraken")
    ap.add_argument("--grid", action="store_true", help="ottimizza su 60 %% e verifica su 40 %%")
    args = ap.parse_args()

    bars = load_csv(args.csv) if args.csv else load_api(args.pair, args.interval)
    if len(bars) < P["ema_slow"] + 100:
        sys.exit(f"Troppi pochi dati ({len(bars)} candele): usa candele più lunghe o un CSV storico.")

    if args.grid:
        cut = int(len(bars) * 0.6)
        grid(bars[:cut], bars[cut:], P)
    else:
        report("PERIODO COMPLETO", bars, P)
        cut = len(bars) // 2
        report("PRIMA METÀ", bars[:cut], P)
        report("SECONDA METÀ", bars[cut:], P)

if __name__ == "__main__":
    main()
