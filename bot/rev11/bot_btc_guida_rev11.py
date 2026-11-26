#!/usr/bin/env python3
"""
BOT "CECCHINO 29 STOP" (BTC guida, versione D) - Rev 11 - MODALITA' SIMULATA (nessun ordine, nessuna chiave API)
Rev 11: regola identica a Cecchino 29 (Rev 8), cambia SOLO l'ingresso: invece di comprare subito alla chiusura della
candela, mette un ORDINE STOP 0,1 ATR sopra la chiusura, valido 4 ore. Compra solo se il prezzo continua a salire
fino a quel livello; altrimenti l'ordine scade e l'operazione salta. Lo stop si mette a 1 ATR sotto il prezzo pagato.
Test 2023-2026 (test/cecchino_29_stop_ingresso_rev1.py): +29,9 %/anno, calo -12 % contro +29,7 % e -14 % di Rev 8;
migliore in tutti e tre i gruppi (12 liquide, 17 nuove, 29). Gira accanto a Rev 8 per confrontarli dal vivo.

Regola (perpetui Kraken, solo long, candele da 4 ore):
  SEGNALE    una candela da 4 ore di BTC chiude in salita di oltre 2 ATR (ATR 14 candele)
  COSA COMPRA le 29 monete salite di oltre 1,7 ATR nella stessa candela (al massimo 5, le piu' forti), con un
             ordine stop 0,1 ATR sopra la chiusura valido 4 ore (se il controllo arriva oltre 45 minuti dopo la chiusura,
             il segnale si salta). Eseguito sulle candele da 15 minuti (al livello, o all'apertura se il prezzo ci
             salta sopra) o sul prezzo "ask" del momento; +0,03 % di slittamento.
  STOP       1,0 ATR sotto il prezzo pagato; a pareggio quando il prezzo sale di 1 ATR; poi segue il massimo a 1,5 ATR
  FASE 1     se dopo 16 ore dalla chiusura del segnale la posizione non ha superato +3 ATR, si chiude
  FASE 2     sopra +3 ATR: niente limite di tempo, lo stop segue il massimo a 1,5 + 0,10 x (guadagno - 3) ATR
  RISCHIO    0,75 % del capitale per operazione (se scatta lo stop iniziale si perde lo 0,75 %);
             al massimo 5 posizioni aperte e posizioni totali al massimo 3 volte il capitale
Costi simulati: acquisto al prezzo "ask" (o al livello dell'ordine + mezzo spread + 0,03 %), vendita al "bid" (spread vero), 0,07 % di commissione per ordine,
funding 0,01 % ogni 8 ore. Lo stop si controlla sulle candele da 15 minuti, come nel test.

Gira ogni 15 minuti su GitHub. File aggiornati:
  stato.json    memoria del bot      registro.csv  operazioni simulate      README.md  cruscotto
"""
import csv, json, os, time, urllib.request
from datetime import datetime, timezone

# ------------------------- IMPOSTAZIONI -------------------------
NOME = "🎯 Cecchino 29 Stop"
SOTTOTITOLO = "BTC guida · versione D · Rev 11"
CARATTERE = ("come Cecchino 29, ma non compra subito: mette un ordine un po' sopra il prezzo e compra solo se la moneta "
             "continua a salire, cosi' salta le monete che si girano appena finito lo scatto")
ATTESE = ("circa 2 scatti di BTC al mese", "circa 90 operazioni all'anno (circa 25 ordini all'anno scadono)",
          "+30 % all'anno (test 2023-2026)", "-12 %")
STOP_INGRESSO_ATR, VALIDITA_ORE, SLITTAMENTO = 0.1, 4, 0.0003
CAPITALE = 2000.0
INGRESSO_BTC = ("atr", 2.0)        # ("atr", soglia in ATR) oppure ("pct", soglia in %)
MONETA_ATR = 1.7
STOP_ATR, PAREGGIO_ATR, TRAIL_ATR = 1.0, 1.0, 1.5
FASE1_ORE, SOGLIA_FASE2, ALLARGAMENTO = 16, 3.0, 0.10
RISCHIO, MAX_POS, LEVA_MAX = 0.0075, 5, 3.0
MAX_RITARDO_MIN = 45
COMMISSIONE, FUNDING_8H = 0.0007, 0.0001
MONETE = ["AAVE", "ADA", "DOGE", "DOT", "ETH", "LINK", "LTC", "NEAR", "SOL", "TRX", "UNI", "XRP",          # 12 liquide
          "ALGO", "APE", "ARB", "ATOM", "AVAX", "AXS", "BCH", "COMP", "CRV", "ETC", "FIL", "INJ", "MANA",
          "OP", "SAND", "XLM", "XTZ"]                                                                     # 17 aggiunte
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
    return {"capitale": CAPITALE, "posizioni": [], "ordini": [], "scaduti": 0, "ultima_candela": 0, "chiuse": 0, "vinte": 0,
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
    s["btc_ultima"] = {"t": T[i], "z": z_btc, "pct": p_btc, "atr": A[i], "prezzo": C[i]}
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
    s["ordini"] = [o for o in s["ordini"] if o["moneta"] not in {m for _, m, _ in scelte}]
    for z, m, a in scelte:
        if m in gia: continue
        chiusura_m = [x for x in candele(m, "4h", T[i], ora) if x[0] == T[i]]
        if not chiusura_m: continue
        livello = chiusura_m[0][4] + STOP_INGRESSO_ATR * a
        s["ordini"].append({"moneta": m, "livello": livello, "atr": a, "ingresso": chiusura, "scadenza": chiusura + VALIDITA_ORE * 3600,
                            "z": z, "z_btc": z_btc, "ultimo_15m": ora // 900 * 900})   # solo candele 15m iniziate dopo l'ordine
        registra([ora_txt(ora), m, "ORDINE STOP", f"{livello:.6g}", "", "", "", f"{s['capitale']:.2f}",
                  f"BTC {z_btc:+.1f} ATR, moneta {z:+.1f} ATR, compra se sale a {livello:.6g} entro {VALIDITA_ORE} ore"])

def apri(s, o, e, quando, t_barra, prezzi):
    """Apre la posizione dell'ordine o al prezzo e (gia' con spread e slittamento). Ritorna True se aperta."""
    m, a = o["moneta"], o["atr"]
    if len(s["posizioni"]) >= MAX_POS or m in {p["moneta"] for p in s["posizioni"]}:
        registra([ora_txt(quando), m, "ORDINE ANNULLATO", f"{e:.6g}", "", "", "", f"{s['capitale']:.2f}", "posizioni gia' piene"]); return True
    stop = e - STOP_ATR * a; pct = (e - stop) / e
    if not 0.002 <= pct <= 0.10: return True
    rischio_usd = s["capitale"] * RISCHIO; q = rischio_usd / (e - stop); nozionale = q * e
    if sum(p["quantita"] * p["prezzo"] for p in s["posizioni"]) + nozionale > LEVA_MAX * s["capitale"]:
        registra([ora_txt(quando), m, "ORDINE ANNULLATO", f"{e:.6g}", "", "", "", f"{s['capitale']:.2f}", "oltre la leva massima"]); return True
    p = {"moneta": m, "ingresso": o["ingresso"], "entrata_t": t_barra if t_barra is not None else quando, "prezzo": e, "atr": a,
         "stop": stop, "stop0": stop, "massimo": e, "fase2": False, "quantita": q, "rischio_usd": rischio_usd,
         "ultimo_15m": t_barra if t_barra is not None else 0, "ultima_chiusura": e, "z": o["z"], "eseguito": quando}
    s["posizioni"].append(p)
    registra([ora_txt(quando), m, "COMPRA", f"{e:.6g}", f"{stop:.6g}", "", "", f"{s['capitale']:.2f}",
              f"ordine stop eseguito (livello {o['livello']:.6g}), BTC {o['z_btc']:+.1f} ATR, moneta {o['z']:+.1f} ATR, posizione {nozionale:.0f} $"])
    return p

def esegui_ordini(s, ora, prezzi):
    """Controlla gli ordini stop in attesa: candele 15 min chiuse, poi il prezzo ask del momento."""
    restano = []
    for o in sorted(s["ordini"], key=lambda o: -o["z"]):
        m = o["moneta"]; bid_ask = prezzi.get(m)
        mezzo = (bid_ask[1] - bid_ask[0]) / 2 / ((bid_ask[0] + bid_ask[1]) / 2) if bid_ask else 0.0
        fatto = False
        barre = [b for b in candele(m, "15m", o["ultimo_15m"] + 900, min(ora, o["scadenza"]))
                 if b[0] > o["ultimo_15m"] and b[0] + 900 <= ora and b[0] < o["scadenza"]]
        for t, op, h, l, c in barre:
            o["ultimo_15m"] = t
            if h >= o["livello"]:
                e = max(o["livello"], op) * (1 + mezzo + SLITTAMENTO)
                p = apri(s, o, e, t + 900, t, prezzi)
                if isinstance(p, dict) and c <= p["stop"]:
                    s["posizioni"].remove(p); chiudi(s, p, c, t + 900, "stop nella candela d'ingresso", bid_ask)
                fatto = True; break
        if not fatto and bid_ask and ora < o["scadenza"] and bid_ask[1] >= o["livello"]:
            apri(s, o, bid_ask[1] * (1 + SLITTAMENTO), ora, None, prezzi); fatto = True
        if fatto: continue
        if ora >= o["scadenza"]:
            s["scaduti"] = s.get("scaduti", 0) + 1
            registra([ora_txt(o["scadenza"]), m, "ORDINE SCADUTO", f"{o['livello']:.6g}", "", "", "", f"{s['capitale']:.2f}",
                      f"il prezzo non e' salito al livello entro {VALIDITA_ORE} ore"])
            continue
        restano.append(o)
    s["ordini"] = restano

# ------------------------- CRUSCOTTO -------------------------
def spiegazione(s):
    tipo, soglia = INGRESSO_BTC
    b = s.get("btc_ultima") or {}
    rischio_usd = CAPITALE * RISCHIO
    if tipo == "atr":
        oggi = (f" Con i prezzi di oggi (ATR di BTC circa {num(b['atr'], 0)} $) vuol dire una salita di almeno "
                f"**{num(soglia * b['atr'], 0)} $**, cioe' circa **{num(soglia * b['atr'] / b['prezzo'] * 100, 1)} %** in 4 ore."
                if b.get("atr") else "")
        scatto = (f"BTC chiude la candela da 4 ore **in salita di oltre {num(soglia, 1)} volte il suo ATR**. L'ATR e' "
                  f"l'oscillazione media di BTC nelle ultime 14 candele da 4 ore: la soglia si adatta da sola, piu' alta "
                  f"quando il mercato e' agitato, piu' bassa quando e' calmo.{oggi}")
    else:
        scatto = f"BTC chiude la candela da 4 ore **in salita di oltre l'{num(soglia, 2)} %** rispetto alla chiusura precedente."
    return f"""## Come agisce

**In una frase:** quando Bitcoin fa uno scatto forte verso l'alto, il bot compra per qualche ora le monete che lo hanno seguito con piu' forza, e le rivende quando lo slancio finisce.

**Carattere:** {CARATTERE}.

### 1 · Aspetta lo scatto di BTC
Ogni 4 ore, alla chiusura della candela (01, 05, 09, 13, 17, 21 ora italiana d'inverno; un'ora dopo d'estate), il bot guarda quanto e' salita BTC.
C'e' uno **scatto** quando {scatto}
Le candele rosse non contano: il bot compra soltanto (solo long).

### 2 · Sceglie le monete
Guarda {len(MONETE)} monete (tutti i perpetui Kraken con storia lunga, BTC escluso): {", ".join(MONETE)}.
Compra quelle che **nella stessa candela sono salite di oltre {num(MONETA_ATR, 1)} volte il loro ATR**, cioe' che hanno seguito BTC con forza.
Se sono di piu', prende le **{MAX_POS} piu' forti**. Non compra due volte la stessa moneta, non tiene mai piu' di {MAX_POS} posizioni insieme,
e la somma delle posizioni non supera {num(LEVA_MAX, 0)} volte il capitale.
**Non compra subito:** per ogni moneta scelta mette un **ordine stop {num(STOP_INGRESSO_ATR, 1)} ATR sopra la chiusura** della candela
(circa 0,2-0,3 % piu' in alto), valido {VALIDITA_ORE} ore. Compra solo se il prezzo continua a salire fino a quel livello: cosi' salta le monete che si girano appena finito lo scatto.
Se in {VALIDITA_ORE} ore il prezzo non ci arriva, l'ordine scade e l'operazione salta (circa 1 ordine su 4).
Se il controllo arriva oltre {MAX_RITARDO_MIN} minuti dopo la chiusura, il segnale si salta: entrare tardi non conviene.

### 3 · Quanto compra
Ogni operazione rischia lo **{num(RISCHIO * 100, 2)} % del capitale** ({num(rischio_usd, 0)} $ su {num(CAPITALE, 0)} $): e' quanto si perde se il prezzo tocca lo stop iniziale.
La quantita' si calcola cosi': rischio diviso la distanza dello stop. *Esempio:* ETH a 3.000 $ con ATR di 60 $ → stop {num(STOP_ATR, 1)} ATR sotto = 2.940 $;
{num(rischio_usd, 0)} $ / 60 $ = {num(rischio_usd / 60, 2)} ETH, cioe' una posizione da circa {num(rischio_usd / 60 * 3000, 0)} $.
Il rischio si ricalcola sul capitale del momento (interesse composto).

### 4 · Come esce
| Situazione | Cosa fa lo stop |
|---|---|
| Subito dopo l'ingresso | **{num(STOP_ATR, 1)} ATR sotto** il prezzo pagato (se lo tocca: −1 R = −{num(RISCHIO * 100, 2)} % del capitale) |
| Il prezzo sale di {num(PAREGGIO_ATR, 1)} ATR | lo stop va al **pareggio** (prezzo d'ingresso): da qui l'operazione non puo' piu' perdere, a parte i costi |
| Il prezzo continua a salire | lo stop **segue il massimo** raggiunto a {num(TRAIL_ATR, 1)} ATR di distanza, e puo' solo salire |
| Passano {FASE1_ORE} ore senza superare +{num(SOGLIA_FASE2, 0)} ATR | **chiude** al prezzo del momento: lo slancio dello scatto e' finito |
| Supera +{num(SOGLIA_FASE2, 0)} ATR (**fase 2**) | niente piu' limite di tempo; la distanza dello stop si allarga di {num(ALLARGAMENTO, 2)} ATR per ogni ATR oltre {num(SOGLIA_FASE2, 0)} (es. a +5 ATR: {num(TRAIL_ATR + ALLARGAMENTO * 2, 1)} ATR) per lasciarla correre |

Lo stop si controlla ogni 15 minuti sulle candele da 15 minuti.

### 5 · Costi simulati
Compra al prezzo di vendita del mercato (*ask*) e vende a quello di acquisto (*bid*): lo spread vero e' pagato.
In piu' {num(COMMISSIONE * 100, 2)} % di commissione per ordine e il funding dei perpetui ({num(FUNDING_8H * 100, 2)} % ogni 8 ore).

### Cosa aspettarsi (test sul 2023-2026, crollo 2022 escluso)
{ATTESE[0]}, {ATTESE[1]}, rendimento **{ATTESE[2]}**, calo massimo **{ATTESE[3]}**.
Questi numeri vengono da un'ottimizzazione sugli stessi dati del passato: **dal vivo e' normale che siano piu' bassi**. Questo bot serve a scoprirlo senza rischiare soldi,
confrontandolo con [Cecchino 29](../rev8/README.md) che riceve gli stessi segnali ma compra subito.
I mesi senza scatti di BTC sono normali: il bot resta fermo.
"""

def num(x, d=2): return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def cruscotto(s, ora, prezzi):
    aperto = 0.0; righe_pos = []
    for p in s["posizioni"]:
        bid = prezzi.get(p["moneta"], (p["prezzo"], p["prezzo"]))[0]
        pl = (bid - p["prezzo"]) * p["quantita"]; aperto += pl
        freccia = "🟢" if pl > 0 else "🔴"
        righe_pos.append(f"| {freccia} **{p['moneta']}** | {ora_txt(p.get('eseguito', p['entrata_t']))} | {num(p['prezzo'], 4)} | {num(bid, 4)} | "
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
    L = [f"# {NOME}", f"**{SOTTOTITOLO} · SIMULATO** (nessun ordine reale)", "",
         f"## {freccia} {num(totale)} $   ({'+' if resa >= 0 else ''}{num(resa * 100)} %)", "",
         f"Capitale di partenza {num(CAPITALE, 0)} $ simulati · attivo da {giorni:.0f} giorni · ultimo controllo {ora_txt(ora)} UTC", "",
         "| Posizioni aperte | Ordini in attesa | Operazioni chiuse | Vinte | Risultato medio | Scatti di BTC | Ordini scaduti |",
         "|:-:|:-:|:-:|:-:|:-:|:-:|:-:|",
         f"| **{len(s['posizioni'])}** | **{len(s.get('ordini', []))}** | **{s['chiuse']}** | **{(s['vinte'] / s['chiuse'] * 100) if s['chiuse'] else 0:.0f} %** | "
         f"**{r_medio:+.2f} R** | **{s['segnali']}** | **{s.get('scaduti', 0)}** |".replace(".", ","), "",
         f"**BTC adesso:** {btc_txt}", ""]
    if righe_pos:
        L += ["### Posizioni aperte", "", "| | Dal (UTC) | Prezzo d'ingresso | Prezzo ora | Variazione | Risultato | Stop | Fase | Da |",
              "|---|---|--:|--:|--:|--:|--:|:-:|--:|"] + righe_pos + [""]
    if s.get("ordini"):
        L += ["### Ordini stop in attesa", "", "| Moneta | Compra se sale a | Prezzo ora | Manca | Scade (UTC) |", "|---|--:|--:|--:|---|"]
        for o in s["ordini"]:
            ask = prezzi.get(o["moneta"], (0, 0))[1]
            manca = f"{(o['livello'] / ask - 1) * 100:+.2f} %" if ask else "?"
            L.append(f"| **{o['moneta']}** | {num(o['livello'], 4)} | {num(ask, 4)} | {manca} | {ora_txt(o['scadenza'])} |".replace(".", ","))
        L.append("")
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
    L += ["---", "", spiegazione(s), "",
          "**Come leggere il cruscotto:** R = risultato diviso il rischio (−1 R = stop iniziale pieno; +2 R = guadagno doppio del rischio). "
          "Fase 1 = normale; fase 2 = l'operazione corre oltre +3 ATR. Ogni operazione e' nel file [registro.csv](registro.csv).", "",
          "<details><summary>Note tecniche</summary>", "", __doc__.strip().replace("\n", "  \n"), "</details>", ""]
    with open(CRUSCOTTO, "w") as f: f.write("\n".join(L))

# ------------------------- AVVIO -------------------------
def main():
    s = carica_stato(); prima = json.dumps(s, sort_keys=True)
    s.setdefault("ordini", []); s.setdefault("scaduti", 0)
    ora = int(time.time())
    prezzi = ticker()
    aggiorna_posizioni(s, ora, prezzi)
    esegui_ordini(s, ora, prezzi)
    cerca_segnale(s, ora, prezzi)
    esegui_ordini(s, ora, prezzi)
    dopo = json.dumps(s, sort_keys=True)
    vecchio = open(CRUSCOTTO).read() if os.path.exists(CRUSCOTTO) else ""
    if dopo != prima or SOTTOTITOLO not in vecchio:
        with open(STATO, "w") as f: json.dump(s, f, indent=1)
        cruscotto(s, ora, prezzi)
        print("aggiornato")
    else:
        print("nessuna novita'")

if __name__ == "__main__":
    main()
