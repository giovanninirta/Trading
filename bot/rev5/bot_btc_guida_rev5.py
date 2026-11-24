#!/usr/bin/env python3
"""
BOT "BTC GUIDA" - Rev 5 (versione B) - MODALITA' SIMULATA (nessun ordine, nessuna chiave API)

Regola (perpetui Kraken, solo long, candele da 4 ore):
  SEGNALE    una candela da 4 ore di BTC chiude in salita di oltre l'1,25 %
  COSA COMPRA le monete liquide salite di oltre 1,7 ATR nella stessa candela (al massimo 5, le piu' forti),
             subito dopo la chiusura della candela (se il controllo arriva oltre 45 minuti dopo, il segnale si salta)
  STOP       1,0 ATR sotto l'ingresso; a pareggio quando il prezzo sale di 1 ATR; poi segue il massimo a 1,5 ATR
  FASE 1     se dopo 16 ore dalla chiusura del segnale la posizione non ha superato +3 ATR, si chiude
  FASE 2     sopra +3 ATR: niente limite di tempo, lo stop segue il massimo a 1,5 + 0,10 x (guadagno - 3) ATR
  RISCHIO    0,75 % del capitale per operazione (se scatta lo stop iniziale si perde lo 0,75 %);
             al massimo 5 posizioni aperte e posizioni totali al massimo 3 volte il capitale
Costi simulati: acquisto al prezzo "ask", vendita al "bid" (spread vero), 0,07 % di commissione per ordine,
funding 0,01 % ogni 8 ore. Lo stop si controlla sulle candele da 15 minuti, come nel test.

Gira ogni 15 minuti su GitHub. File aggiornati:
  stato.json    memoria del bot      registro.csv  operazioni simulate      README.md  cruscotto
"""
import csv, json, os, time, urllib.request
from datetime import datetime, timezone

# ------------------------- IMPOSTAZIONI -------------------------
NOME = "Rev 5 · versione B (scatto BTC oltre +1,25 %)"
CAPITALE = 2000.0
INGRESSO_BTC = ("pct", 1.25)        # ("atr", soglia in ATR) oppure ("pct", soglia in %)
MONETA_ATR = 1.7
STOP_ATR, PAREGGIO_ATR, TRAIL_ATR = 1.0, 1.0, 1.5
FASE1_ORE, SOGLIA_FASE2, ALLARGAMENTO = 16, 3.0, 0.10
RISCHIO, MAX_POS, LEVA_MAX = 0.0075, 5, 3.0
MAX_RITARDO_MIN = 45
COMMISSIONE, FUNDING_8H = 0.0007, 0.0001
MONETE = ["AAVE", "ADA", "DOGE", "DOT", "ETH", "LINK", "LTC", "NEAR", "SOL", "TRX", "UNI", "XRP"]
API_CANDELE = "https://futures.kraken.com/api/charts/v1/trade/PF_{m}USD/{tf}?from={a}&to={b}"
API_TICKER = "https://futures.kraken.com/derivatives/api/v3/tickers"
STATO, REGISTRO, CRUSCOTTO = "stato.json", "registro.csv", "README.md"
H4 = 4 * 3600

# ------------------------- DATI -------------------------
def leggi(url):
    errore = None
    for tentativo in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bot-btc-guida"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            errore = e; time.sleep(3 + 3 * tentativo)
    raise RuntimeError(f"dati non disponibili ({url}): {errore}")

def candele(m, tf, da, a):
    js = leggi(API_CANDELE.format(m="XBT" if m == "BTC" else m, tf=tf, a=int(da), b=int(a)))
    out = [(int(c["time"]) // 1000, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]))
           for c in js.get("candles", [])]
    return sorted(out)

def ticker():
    out = {}
    for t in leggi(API_TICKER).get("tickers", []):
        s = t.get("symbol", "")
        if s.startswith("PF_") and s.endswith("USD") and t.get("bid") and t.get("ask"):
            out[s[3:-3]] = (float(t["bid"]), float(t["ask"]))
    return out

def atr(H, L, C, n=14):
    out, a = [], None
    for i in range(len(C)):
        tr = H[i] - L[i] if i == 0 else max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1]))
        a = tr if a is None else (a * (n - 1) + tr) / n
        out.append(a)
    return out

# ------------------------- STATO -------------------------
def carica_stato():
    if os.path.exists(STATO):
        with open(STATO) as f: return json.load(f)
    return {"capitale": CAPITALE, "posizioni": [], "ultima_candela": 0, "chiuse": 0, "vinte": 0,
            "somma_r": 0.0, "segnali": 0, "ultimo_segnale": None, "btc_ultima": None, "avvio": int(time.time())}

def registra(riga):
    nuovo = not os.path.exists(REGISTRO)
    with open(REGISTRO, "a", newline="") as f:
        w = csv.writer(f)
        if nuovo: w.writerow(["data_utc", "moneta", "azione", "prezzo", "stop", "R", "risultato_usd", "capitale_usd", "nota"])
        w.writerow(riga)

def ora_txt(t): return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")

# ------------------------- GESTIONE POSIZIONI -------------------------
def chiudi(s, p, prezzo_lordo, quando, nota, bid_ask):
    bid, ask = bid_ask if bid_ask else (prezzo_lordo, prezzo_lordo)
    mezzo_spread = (ask - bid) / 2 / ((ask + bid) / 2) if bid_ask else 0.0
    uscita = prezzo_lordo * (1 - mezzo_spread)
    q = p["quantita"]
    lordo = (uscita - p["prezzo"]) * q
    costi = COMMISSIONE * (p["prezzo"] + uscita) * q + FUNDING_8H * p["prezzo"] * q * (quando - p["ingresso"]) / (8 * 3600)
    risultato = lordo - costi
    r = risultato / p["rischio_usd"]
    s["capitale"] += risultato; s["chiuse"] += 1; s["somma_r"] += r
    if risultato > 0: s["vinte"] += 1
    s.setdefault("ultime", []).insert(0, {"moneta": p["moneta"], "entrata": p["ingresso"], "uscita": quando,
                                          "prezzo_in": p["prezzo"], "prezzo_out": uscita, "r": r, "usd": risultato, "nota": nota})
    s["ultime"] = s["ultime"][:15]
    registra([ora_txt(quando), p["moneta"], "VENDE", f"{uscita:.6g}", f"{p['stop']:.6g}", f"{r:+.2f}", f"{risultato:+.2f}",
              f"{s['capitale']:.2f}", nota])

def aggiorna_posizioni(s, ora, prezzi):
    aperte = []
    for p in s["posizioni"]:
        barre = candele(p["moneta"], "15m", max(p["ultimo_15m"] + 900, p["entrata_t"] - 900), ora)
        barre = [b for b in barre if b[0] >= p["entrata_t"] - (p["entrata_t"] % 900) + 900 and b[0] > p["ultimo_15m"] and b[0] + 900 <= ora]
        chiusa = False
        for t, o, h, l, c in barre:
            if not p["fase2"] and t >= p["ingresso"] + FASE1_ORE * 3600:
                chiudi(s, p, p["ultima_chiusura"], t, "16 ore senza fase 2", prezzi.get(p["moneta"])); chiusa = True; break
            if l <= p["stop"]:
                nota = "stop iniziale" if p["stop"] < p["prezzo"] else ("pareggio" if p["stop"] == p["prezzo"] else "trailing")
                chiudi(s, p, min(p["stop"], o), t + 900, nota, prezzi.get(p["moneta"])); chiusa = True; break
            if h > p["massimo"]:
                p["massimo"] = h
                g = (h - p["prezzo"]) / p["atr"]
                if not p["fase2"] and g >= SOGLIA_FASE2: p["fase2"] = True
                if g >= PAREGGIO_ATR:
                    dist = TRAIL_ATR + (ALLARGAMENTO * (g - SOGLIA_FASE2) if p["fase2"] else 0.0)
                    p["stop"] = max(p["stop"], p["prezzo"], h - dist * p["atr"])
            p["ultima_chiusura"] = c; p["ultimo_15m"] = t
        if not chiusa: aperte.append(p)
    s["posizioni"] = aperte

# ------------------------- NUOVI SEGNALI -------------------------
def cerca_segnale(s, ora, prezzi):
    da = ora - 120 * H4
    btc = [b for b in candele("BTC", "4h", da, ora) if b[0] + H4 <= ora]
    if len(btc) < 30: return
    T = [b[0] for b in btc]; H = [b[2] for b in btc]; L = [b[3] for b in btc]; C = [b[4] for b in btc]
    A = atr(H, L, C); i = len(C) - 1
    z_btc, p_btc = (C[i] - C[i - 1]) / A[i - 1], C[i] / C[i - 1] - 1
    s["btc_ultima"] = {"t": T[i], "z": z_btc, "pct": p_btc}
    if T[i] <= s["ultima_candela"]: return
    s["ultima_candela"] = T[i]
    tipo, soglia = INGRESSO_BTC
    if not ((tipo == "atr" and z_btc > soglia) or (tipo == "pct" and p_btc > soglia / 100)): return
    chiusura = T[i] + H4
    s["segnali"] += 1
    s["ultimo_segnale"] = {"t": chiusura, "z": z_btc, "pct": p_btc, "monete": [], "nota": ""}
    ritardo = (ora - chiusura) / 60
    if ritardo > MAX_RITARDO_MIN:
        s["ultimo_segnale"]["nota"] = f"saltato: controllo arrivato {ritardo:.0f} minuti dopo la chiusura"
        registra([ora_txt(ora), "BTC", "SEGNALE SALTATO", "", "", "", "", f"{s['capitale']:.2f}", s["ultimo_segnale"]["nota"]]); return
    scelte = []
    for m in MONETE:
        b = [x for x in candele(m, "4h", da, ora) if x[0] + H4 <= ora]
        if len(b) < 30 or b[-1][0] != T[i]: continue
        Hm = [x[2] for x in b]; Lm = [x[3] for x in b]; Cm = [x[4] for x in b]
        Am = atr(Hm, Lm, Cm); j = len(Cm) - 1
        if Hm[j] == Lm[j] or not Am[j - 1]: continue
        z = (Cm[j] - Cm[j - 1]) / Am[j - 1]
        if z > MONETA_ATR: scelte.append((z, m, Am[j]))
    scelte.sort(reverse=True)
    s["ultimo_segnale"]["monete"] = [f"{m} ({z:.1f} ATR)".replace(".", ",") for z, m, _ in scelte]
    gia = {p["moneta"] for p in s["posizioni"]}
    for z, m, a in scelte:
        if len(s["posizioni"]) >= MAX_POS or m in gia: continue
        if m not in prezzi: continue
        bid, ask = prezzi[m]; e = ask; stop = e - STOP_ATR * a
        pct = (e - stop) / e
        if not 0.002 <= pct <= 0.10: continue
        rischio_usd = s["capitale"] * RISCHIO; q = rischio_usd / (e - stop)
        nozionale = q * e
        if sum(p["quantita"] * p["prezzo"] for p in s["posizioni"]) + nozionale > LEVA_MAX * s["capitale"]: continue
        s["posizioni"].append({"moneta": m, "ingresso": chiusura, "entrata_t": ora, "prezzo": e, "atr": a, "stop": stop,
                               "stop0": stop, "massimo": e, "fase2": False, "quantita": q, "rischio_usd": rischio_usd,
                               "ultimo_15m": 0, "ultima_chiusura": e, "z": z})
        registra([ora_txt(ora), m, "COMPRA", f"{e:.6g}", f"{stop:.6g}", "", "", f"{s['capitale']:.2f}",
                  f"BTC {z_btc:+.1f} ATR, moneta {z:+.1f} ATR, posizione {nozionale:.0f} $"])

# ------------------------- CRUSCOTTO -------------------------
def num(x, d=2): return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def cruscotto(s, ora, prezzi):
    aperto = 0.0; righe_pos = []
    for p in s["posizioni"]:
        bid = prezzi.get(p["moneta"], (p["prezzo"], p["prezzo"]))[0]
        pl = (bid - p["prezzo"]) * p["quantita"]; aperto += pl
        freccia = "🟢" if pl > 0 else "🔴"
        righe_pos.append(f"| {freccia} **{p['moneta']}** | {ora_txt(p['entrata_t'])} | {num(p['prezzo'], 4)} | {num(bid, 4)} | "
                         f"{(bid / p['prezzo'] - 1) * 100:+.1f} % | {pl:+.2f} $ | {num(p['stop'], 4)} | "
                         f"{'2 · corre' if p['fase2'] else '1'} | {(ora - p['ingresso']) / 3600:.0f} h |".replace(".", ","))
    totale = s["capitale"] + aperto
    resa = totale / CAPITALE - 1
    freccia = "⬆️" if resa > 0.0005 else ("⬇️" if resa < -0.0005 else "➡️")
    r_medio = s["somma_r"] / s["chiuse"] if s["chiuse"] else 0.0
    giorni = (ora - s["avvio"]) / 86400
    btc = s.get("btc_ultima") or {}
    tipo, soglia = INGRESSO_BTC
    if btc:
        if tipo == "atr": vicino = f"{btc['z']:+.1f} ATR (serve oltre {soglia:.1f})"
        else: vicino = f"{btc['pct'] * 100:+.2f} % (serve oltre {soglia:.2f} %)"
        btc_txt = f"ultima candela 4h chiusa alle {ora_txt(btc['t'] + H4)}: **{vicino}**".replace(".", ",")
    else: btc_txt = "in attesa del primo controllo"
    L = [f"# Bot BTC guida · {NOME} · SIMULATO", "",
         f"## {freccia} {num(totale)} $   ({'+' if resa >= 0 else ''}{num(resa * 100)} %)", "",
         f"Capitale di partenza {num(CAPITALE, 0)} $ simulati · attivo da {giorni:.0f} giorni · ultimo controllo {ora_txt(ora)} UTC", "",
         "| Posizioni aperte | Operazioni chiuse | Vinte | Risultato medio | Scatti di BTC |",
         "|:-:|:-:|:-:|:-:|:-:|",
         f"| **{len(s['posizioni'])}** | **{s['chiuse']}** | **{(s['vinte'] / s['chiuse'] * 100) if s['chiuse'] else 0:.0f} %** | "
         f"**{r_medio:+.2f} R** | **{s['segnali']}** |".replace(".", ","), "",
         f"**BTC adesso:** {btc_txt}", ""]
    if righe_pos:
        L += ["### Posizioni aperte", "", "| | Dal (UTC) | Prezzo d'ingresso | Prezzo ora | Variazione | Risultato | Stop | Fase | Da |",
              "|---|---|--:|--:|--:|--:|--:|:-:|--:|"] + righe_pos + [""]
    seg = s.get("ultimo_segnale")
    if seg:
        mon = ", ".join(seg["monete"]) if seg["monete"] else "nessuna moneta abbastanza forte"
        L += [f"**Ultimo scatto di BTC:** {ora_txt(seg['t'])} UTC, {seg['z']:+.1f} ATR ({seg['pct'] * 100:+.2f} %) → {mon}"
              f"{' · ' + seg['nota'] if seg['nota'] else ''}".replace(".", ","), ""]
    if s.get("ultime"):
        L += ["### Ultime operazioni chiuse", "", "| | Moneta | Entrata | Uscita | Risultato | R | Motivo |", "|---|---|---|---|--:|--:|---|"]
        for u in s["ultime"]:
            L.append(f"| {'✅' if u['usd'] > 0 else '❌'} | {u['moneta']} | {ora_txt(u['entrata'])} | {ora_txt(u['uscita'])} | "
                     f"{u['usd']:+.2f} $ | {u['r']:+.2f} | {u['nota']} |".replace(".", ","))
        L.append("")
    L += ["<details><summary>Come funziona e come leggere</summary>", "",
          __doc__.strip().replace("\n", "  \n"), "",
          "**R** = risultato diviso il rischio: −1 R = stop iniziale pieno (−0,75 % del capitale); +2 R = guadagno doppio del rischio.  ",
          "Ogni operazione è anche nel file [registro.csv](registro.csv).", "</details>", ""]
    with open(CRUSCOTTO, "w") as f: f.write("\n".join(L))

# ------------------------- AVVIO -------------------------
def main():
    s = carica_stato(); prima = json.dumps(s, sort_keys=True)
    ora = int(time.time())
    prezzi = ticker()
    aggiorna_posizioni(s, ora, prezzi)
    cerca_segnale(s, ora, prezzi)
    dopo = json.dumps(s, sort_keys=True)
    if dopo != prima or not os.path.exists(CRUSCOTTO):
        with open(STATO, "w") as f: json.dump(s, f, indent=1)
        cruscotto(s, ora, prezzi)
        print("aggiornato")
    else:
        print("nessuna novita'")

if __name__ == "__main__":
    main()
