#!/usr/bin/env python3
"""
BOT "SEGUGIO SHORT" (BTC guida al ribasso) - Rev 9 - MODALITA' SIMULATA (nessun ordine, nessuna chiave API)
Motore unico long/short: la Rev 10 (Cecchino + Short) usa lo stesso codice con anche il lato long attivo.

Regola SHORT (scelta dall'algoritmo genetico, genetico_short_rev1.py, n. 1; perpetui Kraken, 29 monete):
  CANDELE    da 8 ore (00, 08, 16 UTC), costruite da due candele da 4 ore
  SEGNALE    la candela da 8 ore di BTC chiude in DISCESA di oltre l'1,5 %, e BTC e' sotto la sua media di 160
             candele da 8 ore (al massimo +5 % sopra: tolleranza)
  COSA VENDE le monete scese di oltre 1,8 ATR (ATR 20 candele) nella stessa candela, con RSI 14 non sotto 25;
             si saltano le 2 piu' deboli (tendono a rimbalzare) e si vendono le successive, max 8 posizioni short
  STOP       0,9 ATR sopra l'ingresso; a pareggio quando il guadagno arriva a 1,75 ATR; poi segue il minimo a 2,0 ATR
  FASE 1     se dopo 8 ore dalla chiusura del segnale non ha superato +2,5 ATR di guadagno, si chiude
  FASE 2     oltre +2,5 ATR: niente limite di tempo, distanza 2,0 + 0,10 x (guadagno - 2,5) ATR
  RISCHIO    0,75 % del capitale per operazione; posizioni totali al massimo 3 volte il capitale;
             mai due posizioni (long o short) sulla stessa moneta
Costi simulati: vendita al "bid", riacquisto all'"ask" (spread vero), 0,07 % di commissione per ordine,
funding 0,01 % ogni 8 ore (pagato sempre, per prudenza). Stop controllati sulle candele da 15 minuti.

Gira ogni 15 minuti su GitHub. File: stato.json (memoria), registro.csv (operazioni), README.md (cruscotto).
"""
import csv, json, os, time, urllib.request
from datetime import datetime, timezone

# ------------------------- IMPOSTAZIONI -------------------------
NOME = "🐕 Segugio Short"
SOTTOTITOLO = "BTC guida al ribasso · Rev 9"
CARATTERE = "lavora quando BTC e' debole: vende le monete che crollano con BTC, ma non le piu' crollate"
ATTESE = "circa 70 operazioni all'anno, +9 % all'anno, calo massimo -10 % (test 2022-2026 su 29 monete)"
CAPITALE = 2000.0
LONG = None
SHORT = dict(ore=8, btc_pct=1.5, atr_p=20, moneta=1.8, maxpos=8, salta=2, rsi_min=25, stop=0.9, pari=1.75,
             trail=2.0, f1=8, s2=2.5, allarga=0.10, sma=160, toll=0.05)
RISCHIO, LEVA_MAX, MAX_RITARDO_MIN = 0.0075, 3.0, 45
COMMISSIONE, FUNDING_8H = 0.0007, 0.0001
MONETE = ["AAVE", "ADA", "DOGE", "DOT", "ETH", "LINK", "LTC", "NEAR", "SOL", "TRX", "UNI", "XRP",
          "ALGO", "APE", "ARB", "ATOM", "AVAX", "AXS", "BCH", "COMP", "CRV", "ETC", "FIL", "INJ", "MANA",
          "OP", "SAND", "XLM", "XTZ"]
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

def chiuse(m, ore, ora, quante):
    """Candele chiuse da 'ore' ore (4 o 8), costruite dalle 4 ore di Kraken, allineate a UTC."""
    b4 = [b for b in candele(m, "4h", ora - (quante * ore // 4 + 4) * H4, ora) if b[0] + H4 <= ora]
    if ore == 4: return b4
    L, out, g = ore * 3600, [], []
    for b in b4:
        if g and g[0][0] // L != b[0] // L:
            if len(g) == ore // 4: out.append((g[0][0] // L * L, g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4]))
            g = []
        g.append(b)
    if len(g) == ore // 4 and g[0][0] // L * L + L <= ora:
        out.append((g[0][0] // L * L, g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4]))
    return out

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

def rsi(C, n=14):
    out, ag, al = [None] * len(C), None, None
    for i in range(1, len(C)):
        d = C[i] - C[i - 1]; g, l = max(d, 0), max(-d, 0)
        if ag is None: ag, al = g, l
        else: ag = (ag * (n - 1) + g) / n; al = (al * (n - 1) + l) / n
        if i >= n: out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out

# ------------------------- STATO -------------------------
def carica_stato():
    if os.path.exists(STATO):
        with open(STATO) as f: return json.load(f)
    return {"capitale": CAPITALE, "posizioni": [], "ultima_candela": {"long": 0, "short": 0}, "chiuse": 0, "vinte": 0,
            "somma_r": 0.0, "segnali": {"long": 0, "short": 0}, "ultimo_segnale": {}, "btc_ultima": {}, "avvio": int(time.time())}

def registra(riga):
    nuovo = not os.path.exists(REGISTRO)
    with open(REGISTRO, "a", newline="") as f:
        w = csv.writer(f)
        if nuovo: w.writerow(["data_utc", "moneta", "azione", "prezzo", "stop", "R", "risultato_usd", "capitale_usd", "nota"])
        w.writerow(riga)

def ora_txt(t): return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")
def num(x, d=2): return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
def regola(lato): return LONG if lato == "long" else SHORT

# ------------------------- GESTIONE POSIZIONI -------------------------
def chiudi(s, p, prezzo_lordo, quando, nota, bid_ask):
    d = 1 if p["lato"] == "long" else -1
    mezzo = (bid_ask[1] - bid_ask[0]) / 2 / ((bid_ask[1] + bid_ask[0]) / 2) if bid_ask else 0.0
    uscita = prezzo_lordo * (1 - d * mezzo)          # il long vende al bid, lo short ricompra all'ask
    q = p["quantita"]
    lordo = (uscita - p["prezzo"]) * q * d
    costi = COMMISSIONE * (p["prezzo"] + uscita) * q + FUNDING_8H * p["prezzo"] * q * (quando - p["ingresso"]) / (8 * 3600)
    risultato = lordo - costi; r = risultato / p["rischio_usd"]
    s["capitale"] += risultato; s["chiuse"] += 1; s["somma_r"] += r
    if risultato > 0: s["vinte"] += 1
    s.setdefault("ultime", []).insert(0, {"moneta": p["moneta"], "lato": p["lato"], "entrata": p["ingresso"], "uscita": quando,
                                          "prezzo_in": p["prezzo"], "prezzo_out": uscita, "r": r, "usd": risultato, "nota": nota})
    s["ultime"] = s["ultime"][:15]
    registra([ora_txt(quando), p["moneta"], ("VENDE" if d > 0 else "RICOMPRA") + f" ({p['lato']})", f"{uscita:.6g}", f"{p['stop']:.6g}",
              f"{r:+.2f}", f"{risultato:+.2f}", f"{s['capitale']:.2f}", nota])

def aggiorna_posizioni(s, ora, prezzi):
    aperte = []
    for p in s["posizioni"]:
        g = regola(p["lato"]); d = 1 if p["lato"] == "long" else -1
        barre = candele(p["moneta"], "15m", max(p["ultimo_15m"] + 900, p["entrata_t"] - 900), ora)
        barre = [b for b in barre if b[0] >= p["entrata_t"] - (p["entrata_t"] % 900) + 900 and b[0] > p["ultimo_15m"] and b[0] + 900 <= ora]
        chiusa = False
        for t, o, h, l, c in barre:
            if not p["fase2"] and t >= p["ingresso"] + g["f1"] * 3600:
                chiudi(s, p, p["ultima_chiusura"], t, f"{g['f1']} ore senza fase 2", prezzi.get(p["moneta"])); chiusa = True; break
            if (d > 0 and l <= p["stop"]) or (d < 0 and h >= p["stop"]):
                nota = "stop iniziale" if p["stop"] == p["stop0"] else ("pareggio" if p["stop"] == p["prezzo"] else "trailing")
                chiudi(s, p, min(p["stop"], o) if d > 0 else max(p["stop"], o), t + 900, nota, prezzi.get(p["moneta"])); chiusa = True; break
            estremo = h if d > 0 else l
            if (estremo - p["estremo"]) * d > 0:
                p["estremo"] = estremo
                gg = (estremo - p["prezzo"]) * d / p["atr"]
                if not p["fase2"] and gg >= g["s2"]: p["fase2"] = True
                if gg >= g["pari"]:
                    dist = g["trail"] + (g["allarga"] * (gg - g["s2"]) if p["fase2"] else 0.0)
                    nuovo = estremo - d * dist * p["atr"]
                    p["stop"] = max(p["stop"], p["prezzo"], nuovo) if d > 0 else min(p["stop"], p["prezzo"], nuovo)
            p["ultima_chiusura"] = c; p["ultimo_15m"] = t
        if not chiusa: aperte.append(p)
    s["posizioni"] = aperte

# ------------------------- NUOVI SEGNALI -------------------------
def cerca_segnale(s, ora, prezzi, lato):
    g = regola(lato); d = 1 if lato == "long" else -1; ore = g["ore"]; D = ore * 3600
    serve = max(g.get("sma") or 0, 60) + 3 * g["atr_p"] + 40
    btc = chiuse("BTC", ore, ora, serve)
    if len(btc) < 40: return
    T = [b[0] for b in btc]; H = [b[2] for b in btc]; L = [b[3] for b in btc]; C = [b[4] for b in btc]
    A = atr(H, L, C, g["atr_p"]); i = len(C) - 1
    z_btc, p_btc = (C[i] - C[i - 1]) / A[i - 1], C[i] / C[i - 1] - 1
    sma = sum(C[-g["sma"]:]) / g["sma"] if g.get("sma") and len(C) >= g["sma"] else None
    s["btc_ultima"][lato] = {"t": T[i], "z": z_btc, "pct": p_btc, "atr": A[i], "prezzo": C[i], "sma": sma, "ore": ore}
    if T[i] <= s["ultima_candela"].get(lato, 0): return
    s["ultima_candela"][lato] = T[i]
    if lato == "long": ok = z_btc > g["btc_atr"]
    else: ok = p_btc < -g["btc_pct"] / 100 and sma is not None and C[i] < sma * (1 + g["toll"])
    if not ok: return
    chiusura = T[i] + D
    s["segnali"][lato] = s["segnali"].get(lato, 0) + 1
    s["ultimo_segnale"][lato] = {"t": chiusura, "z": z_btc, "pct": p_btc, "monete": [], "nota": ""}
    ritardo = (ora - chiusura) / 60
    if ritardo > MAX_RITARDO_MIN:
        s["ultimo_segnale"][lato]["nota"] = f"saltato: controllo arrivato {ritardo:.0f} minuti dopo la chiusura"
        registra([ora_txt(ora), "BTC", f"SEGNALE {lato.upper()} SALTATO", "", "", "", "", f"{s['capitale']:.2f}", s["ultimo_segnale"][lato]["nota"]]); return
    scelte = []
    for m in MONETE:
        b = chiuse(m, ore, ora, 3 * g["atr_p"] + 60)
        if len(b) < 40 or b[-1][0] != T[i]: continue
        Hm = [x[2] for x in b]; Lm = [x[3] for x in b]; Cm = [x[4] for x in b]
        Am = atr(Hm, Lm, Cm, g["atr_p"]); j = len(Cm) - 1
        if Hm[j] == Lm[j] or not Am[j - 1]: continue
        z = (Cm[j] - Cm[j - 1]) / Am[j - 1]
        if z * d <= g["moneta"]: continue
        if lato == "short":
            r = rsi(Cm)[j]
            if r is None or r < g["rsi_min"]: continue
        scelte.append((z, m, Am[j]))
    scelte.sort(key=lambda x: -x[0] * d)                  # long: piu' forti prima; short: piu' deboli prima
    s["ultimo_segnale"][lato]["monete"] = [f"{m} ({z:+.1f} ATR)".replace(".", ",") for z, m, _ in scelte]
    if g.get("salta"): s["ultimo_segnale"][lato]["nota"] = f"saltate le {g['salta']} piu' deboli"
    for z, m, a in scelte[g.get("salta", 0):]:
        mie = [p for p in s["posizioni"] if p["lato"] == lato]
        if len(mie) >= g["maxpos"] or m in {p["moneta"] for p in s["posizioni"]} or m not in prezzi: continue
        bid, ask = prezzi[m]; e = ask if d > 0 else bid; stop = e - d * g["stop"] * a
        pct = g["stop"] * a / e
        if not 0.002 <= pct <= 0.10: continue
        rischio_usd = s["capitale"] * RISCHIO; q = rischio_usd / (g["stop"] * a); nozionale = q * e
        if sum(p["quantita"] * p["prezzo"] for p in s["posizioni"]) + nozionale > LEVA_MAX * s["capitale"]: continue
        s["posizioni"].append({"moneta": m, "lato": lato, "ingresso": chiusura, "entrata_t": ora, "prezzo": e, "atr": a,
                               "stop": stop, "stop0": stop, "estremo": e, "fase2": False, "quantita": q, "rischio_usd": rischio_usd,
                               "ultimo_15m": 0, "ultima_chiusura": e, "z": z})
        registra([ora_txt(ora), m, "COMPRA (long)" if d > 0 else "VENDE ALLO SCOPERTO (short)", f"{e:.6g}", f"{stop:.6g}", "", "",
                  f"{s['capitale']:.2f}", f"BTC {p_btc * 100:+.2f} % ({z_btc:+.1f} ATR), moneta {z:+.1f} ATR, posizione {nozionale:.0f} $"])

# ------------------------- CRUSCOTTO -------------------------
def spiega_lato(lato):
    g = regola(lato)
    if lato == "long":
        return f"""### Lato LONG (regola Cecchino 29)
1. **Segnale:** la candela da {g['ore']} ore di BTC chiude in salita di oltre **{num(g['btc_atr'], 1)} volte il suo ATR** ({g['atr_p']} candele).
2. **Compra** le monete salite di oltre **{num(g['moneta'], 1)} ATR** nella stessa candela, le piu' forti, al massimo **{g['maxpos']}** posizioni long.
3. **Stop** {num(g['stop'], 1)} ATR sotto; **pareggio** a +{num(g['pari'], 2)} ATR; poi segue il massimo a {num(g['trail'], 1)} ATR.
4. Se dopo **{g['f1']} ore** non ha superato +{num(g['s2'], 1)} ATR si chiude; oltre (**fase 2**) niente limite di tempo e la distanza si allarga di {num(g['allarga'], 2)} ATR per ogni ATR in piu'.
"""
    return f"""### Lato SHORT (regola Segugio Short)
1. **Segnale:** la candela da {g['ore']} ore di BTC (chiude alle 00, 08, 16 UTC) scende di oltre **{num(g['btc_pct'], 1)} %**, e BTC e' **sotto la sua media di {g['sma']} candele** da {g['ore']} ore (tolleranza +{num(g['toll'] * 100, 0)} %): si vende solo quando il mercato e' debole.
2. **Vende allo scoperto** le monete scese di oltre **{num(g['moneta'], 1)} ATR** ({g['atr_p']} candele) nella stessa candela, con RSI non sotto {g['rsi_min']}; **salta le {g['salta']} piu' deboli** (le piu' crollate tendono a rimbalzare); al massimo **{g['maxpos']}** posizioni short.
3. **Stop** {num(g['stop'], 1)} ATR sopra l'ingresso; **pareggio** quando guadagna {num(g['pari'], 2)} ATR; poi segue il minimo a {num(g['trail'], 1)} ATR.
4. Se dopo **{g['f1']} ore** non ha guadagnato +{num(g['s2'], 1)} ATR si chiude; oltre (**fase 2**) niente limite di tempo e la distanza si allarga di {num(g['allarga'], 2)} ATR per ogni ATR in piu'.
"""

def cruscotto(s, ora, prezzi):
    aperto = 0.0; righe = []
    for p in s["posizioni"]:
        d = 1 if p["lato"] == "long" else -1
        bid, ask = prezzi.get(p["moneta"], (p["prezzo"], p["prezzo"]))
        px = bid if d > 0 else ask
        pl = (px - p["prezzo"]) * p["quantita"] * d; aperto += pl
        righe.append(f"| {'🟢' if pl > 0 else '🔴'} **{p['moneta']}** | {p['lato']} | {ora_txt(p['entrata_t'])} | {num(p['prezzo'], 4)} | {num(px, 4)} | "
                     f"{pl:+.2f} $ | {num(p['stop'], 4)} | {'2' if p['fase2'] else '1'} | {(ora - p['ingresso']) / 3600:.0f} h |".replace(".", ","))
    totale = s["capitale"] + aperto; resa = totale / CAPITALE - 1
    freccia = "⬆️" if resa > 0.0005 else ("⬇️" if resa < -0.0005 else "➡️")
    r_medio = s["somma_r"] / s["chiuse"] if s["chiuse"] else 0.0
    lati = [x for x in ("long", "short") if regola(x)]
    conteggi = " / ".join(f"{x} {s['segnali'].get(x, 0)}" for x in lati)
    stato_btc = []
    for lato in lati:
        b = s["btc_ultima"].get(lato); g = regola(lato)
        if not b: stato_btc.append(f"- {lato}: in attesa del primo controllo"); continue
        if lato == "long": txt = f"{b['z']:+.1f} ATR (serve oltre {g['btc_atr']:.1f})"
        else:
            sotto = "sotto la media " + str(g["sma"]) if b.get("sma") and b["prezzo"] < b["sma"] * (1 + g["toll"]) else "sopra la media " + str(g["sma"]) + ": short spenti"
            txt = f"{b['pct'] * 100:+.2f} % (serve sotto -{g['btc_pct']:.2f} %), BTC {sotto}"
        stato_btc.append(f"- {lato}: candela {b['ore']} h chiusa alle {ora_txt(b['t'] + b['ore'] * 3600)} UTC: **{txt}**".replace(".", ","))
    L = [f"# {NOME}", f"**{SOTTOTITOLO} · SIMULATO** (nessun ordine reale)", "",
         f"## {freccia} {num(totale)} $   ({'+' if resa >= 0 else ''}{num(resa * 100)} %)", "",
         f"Capitale di partenza {num(CAPITALE, 0)} $ simulati · attivo da {(ora - s['avvio']) / 86400:.0f} giorni · ultimo controllo {ora_txt(ora)} UTC", "",
         "| Posizioni aperte | Operazioni chiuse | Vinte | Risultato medio | Segnali di BTC |", "|:-:|:-:|:-:|:-:|:-:|",
         f"| **{len(s['posizioni'])}** | **{s['chiuse']}** | **{(s['vinte'] / s['chiuse'] * 100) if s['chiuse'] else 0:.0f} %** | "
         f"**{r_medio:+.2f} R** | **{conteggi}** |".replace(".", ","), "",
         "**BTC adesso:**"] + stato_btc + [""]
    if righe:
        L += ["### Posizioni aperte", "", "| | Lato | Dal (UTC) | Prezzo d'ingresso | Prezzo ora | Risultato | Stop | Fase | Da |",
              "|---|---|---|--:|--:|--:|--:|:-:|--:|"] + righe + [""]
    for lato in lati:
        seg = s["ultimo_segnale"].get(lato)
        if seg:
            mon = ", ".join(seg["monete"]) if seg["monete"] else "nessuna moneta abbastanza mossa"
            L += [f"**Ultimo segnale {lato}:** {ora_txt(seg['t'])} UTC, BTC {seg['pct'] * 100:+.2f} % ({seg['z']:+.1f} ATR) → {mon}"
                  f"{' · ' + seg['nota'] if seg['nota'] else ''}".replace(".", ","), ""]
    if s.get("ultime"):
        L += ["### Ultime operazioni chiuse", "", "| | Moneta | Lato | Entrata | Uscita | Risultato | R | Motivo |", "|---|---|---|---|---|--:|--:|---|"]
        for u in s["ultime"]:
            L.append(f"| {'✅' if u['usd'] > 0 else '❌'} | {u['moneta']} | {u.get('lato', 'long')} | {ora_txt(u['entrata'])} | {ora_txt(u['uscita'])} | "
                     f"{u['usd']:+.2f} $ | {u['r']:+.2f} | {u['nota']} |".replace(".", ","))
        L.append("")
    L += ["---", "", "## Come agisce", "", f"**Carattere:** {CARATTERE}.", ""] + [spiega_lato(x) for x in lati] + [
          f"**Rischio:** ogni operazione rischia lo **{num(RISCHIO * 100, 2)} % del capitale** (quanto si perde se tocca lo stop iniziale); "
          f"la somma delle posizioni non supera {num(LEVA_MAX, 0)} volte il capitale; mai due posizioni sulla stessa moneta.", "",
          f"**Costi simulati:** spread vero (si entra e si esce al prezzo peggiore tra bid e ask), {num(COMMISSIONE * 100, 2)} % di commissione per ordine, "
          f"funding {num(FUNDING_8H * 100, 2)} % ogni 8 ore.", "",
          f"**Cosa aspettarsi (test):** {ATTESE}. Numeri da regole scelte guardando il passato: **dal vivo e' normale che siano piu' bassi**. "
          "Questo bot serve a scoprirlo senza rischiare soldi.", "",
          "**Come leggere:** R = risultato diviso il rischio (−1 R = stop iniziale pieno). Ogni operazione e' nel file [registro.csv](registro.csv).", "",
          "<details><summary>Note tecniche</summary>", "", __doc__.strip().replace("\n", "  \n"), "</details>", ""]
    with open(CRUSCOTTO, "w") as f: f.write("\n".join(L))

# ------------------------- AVVIO -------------------------
def main():
    s = carica_stato(); prima = json.dumps(s, sort_keys=True)
    ora = int(time.time()); prezzi = ticker()
    aggiorna_posizioni(s, ora, prezzi)
    for lato in ("long", "short"):
        if regola(lato): cerca_segnale(s, ora, prezzi, lato)
    dopo = json.dumps(s, sort_keys=True)
    vecchio = open(CRUSCOTTO).read() if os.path.exists(CRUSCOTTO) else ""
    if dopo != prima or SOTTOTITOLO not in vecchio:
        with open(STATO, "w") as f: json.dump(s, f, indent=1)
        cruscotto(s, ora, prezzi); print("aggiornato")
    else:
        print("nessuna novita'")

if __name__ == "__main__":
    main()
