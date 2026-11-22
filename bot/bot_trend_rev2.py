#!/usr/bin/env python3
"""
BOT TREND - Rev 2 - MODALITA' SIMULATA (non manda nessun ordine, non usa chiavi API)

Regola (Canale 55/20, solo long, una volta al giorno sulla chiusura giornaliera):
  - se una moneta chiude sopra il massimo delle 55 chiusure precedenti -> compra
  - se e' dentro e chiude sotto il minimo delle 20 chiusure precedenti -> vende tutto
Capitale simulato diviso in parti uguali tra le monete; ogni parte lavora da sola.
Rev 2: 30 monete, in euro, quota fissa di 1/30 del capitale per moneta.
Prezzi: spot Kraken contro EUR (dati pubblici). Commissione simulata: 0,40 % per ordine.
Il bot lavora solo con la cifra indicata in CAPITALE: il resto del conto non lo considera.

File che il bot aggiorna a ogni esecuzione:
  stato.json    memoria del bot (cassa, posizioni, ultimo giorno elaborato)
  registro.csv  elenco delle operazioni simulate
  README.md     cruscotto leggibile, visibile aprendo il repository su GitHub
"""
import csv, json, os, sys, time, urllib.request
from datetime import datetime, timezone

# ------------------------- IMPOSTAZIONI -------------------------
CAPITALE = 2000.0          # cifra affidata al bot (simulata), nella valuta qui sotto
VALUTA = "EUR"
INGRESSO, USCITA = 55, 20  # giorni del canale
COMMISSIONE = 0.004        # 0,40 % per ordine (spot Kraken Pro, ordine limite)
MONETE = {                 # nome -> nome della coppia su Kraken
    "BTC": ["XBTEUR"], "ETH": ["ETHEUR"], "SOL": ["SOLEUR"], "XRP": ["XRPEUR"], "ADA": ["ADAEUR"],
    "DOGE": ["XDGEUR"], "LTC": ["LTCEUR"], "LINK": ["LINKEUR"], "AVAX": ["AVAXEUR"], "DOT": ["DOTEUR"],
    "BCH": ["BCHEUR"], "ATOM": ["ATOMEUR"], "UNI": ["UNIEUR"], "XLM": ["XLMEUR"], "ETC": ["ETCEUR"],
    "FIL": ["FILEUR"], "AAVE": ["AAVEEUR"], "ALGO": ["ALGOEUR"], "TRX": ["TRXEUR"], "NEAR": ["NEAREUR"],
    "APE": ["APEEUR"], "SAND": ["SANDEUR"], "MANA": ["MANAEUR"], "AXS": ["AXSEUR"], "CRV": ["CRVEUR"],
    "COMP": ["COMPEUR"], "OP": ["OPEUR"], "ARB": ["ARBEUR"], "INJ": ["INJEUR"], "XTZ": ["XTZEUR"],
}
API = "https://api.kraken.com/0/public/OHLC?pair={}&interval=1440"
STATO, REGISTRO, CRUSCOTTO = "stato.json", "registro.csv", "README.md"

# ------------------------- DATI -------------------------
def candele(nomi):
    """Ritorna [(timestamp, chiusura)] delle candele giornaliere CHIUSE, dalla piu' vecchia."""
    errore = None
    for nome in nomi:
        try:
            req = urllib.request.Request(API.format(nome), headers={"User-Agent": "bot-trend"})
            with urllib.request.urlopen(req, timeout=30) as r:
                js = json.load(r)
            if js.get("error"):
                errore = js["error"]; continue
            chiave = [k for k in js["result"] if k != "last"][0]
            righe = [(int(x[0]), float(x[4])) for x in js["result"][chiave]]
            return righe[:-1]              # l'ultima candela e' quella di oggi, ancora aperta
        except Exception as e:
            errore = e
    raise RuntimeError(f"dati non disponibili per {nomi}: {errore}")

# ------------------------- FORMATI -------------------------
def eur(x, dec=2):
    s = f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s
def prezzo(x):
    return eur(x, 0) if x >= 1000 else eur(x, 2) if x >= 1 else eur(x, 4)
def pct(x):
    return f"{'▲' if x > 0 else '▼' if x < 0 else '■'} {x * 100:+.1f} %".replace(".", ",")
def giorno(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")

# ------------------------- LOGICA -------------------------
def carica_stato():
    if os.path.exists(STATO):
        with open(STATO) as f:
            return json.load(f)
    parte = CAPITALE / len(MONETE)
    return {"creato": giorno(time.time()), "capitale_iniziale": CAPITALE,
            "monete": {m: {"cassa": parte, "quantita": 0.0, "prezzo_in": None, "data_in": None, "ultimo": None} for m in MONETE}}

def registra(riga):
    nuovo = not os.path.exists(REGISTRO)
    with open(REGISTRO, "a", newline="") as f:
        w = csv.writer(f)
        if nuovo: w.writerow(["data", "moneta", "azione", "prezzo", "quantita", "valore", "risultato_pct"])
        w.writerow(riga)

def elabora(moneta, s, dati):
    """Applica la regola a ogni giorno chiuso non ancora elaborato. Ritorna le informazioni per il cruscotto."""
    ts = [d[0] for d in dati]; c = [d[1] for d in dati]
    if len(c) <= INGRESSO:
        raise RuntimeError("storico troppo corto")
    if s["ultimo"] is None or s["ultimo"] not in ts:
        primo = len(c) - 1                           # prima esecuzione: solo l'ultimo giorno chiuso
    else:
        primo = ts.index(s["ultimo"]) + 1            # recupera anche eventuali giorni saltati
    for t in range(max(primo, INGRESSO), len(c)):
        dentro = s["quantita"] > 0
        if not dentro and c[t] > max(c[t - INGRESSO:t]):
            q = s["cassa"] * (1 - COMMISSIONE) / c[t]
            registra([giorno(ts[t]), moneta, "COMPRA", c[t], q, round(s["cassa"], 2), ""])
            s.update(quantita=q, prezzo_in=c[t], data_in=giorno(ts[t]), cassa_in=s["cassa"], cassa=0.0)
        elif dentro and c[t] < min(c[t - USCITA:t]):
            incasso = s["quantita"] * c[t] * (1 - COMMISSIONE)
            ris = incasso / s.get("cassa_in", incasso) - 1
            registra([giorno(ts[t]), moneta, "VENDE", c[t], s["quantita"], round(incasso, 2), round(ris * 100, 2)])
            s.update(cassa=incasso, quantita=0.0, prezzo_in=None, data_in=None)
    s["ultimo"] = ts[-1]
    t = len(c)                                        # livelli validi per la PROSSIMA chiusura
    return dict(prezzo=c[-1], entra=max(c[t - INGRESSO:t]), esce=min(c[t - USCITA:t]), data=ts[-1])

def cruscotto(stato, info, errori):
    righe, valore, investito = [], 0.0, 0.0
    def ordine(kv):
        m, s = kv; i = info.get(m)
        if not i: return (2, 0)
        if s["quantita"] > 0: return (0, i["esce"] / i["prezzo"])
        return (1, i["entra"] / i["prezzo"])
    for m, s in sorted(stato["monete"].items(), key=ordine):
        i = info.get(m)
        p = i["prezzo"] if i else (s["prezzo_in"] or 0)
        v = s["cassa"] + s["quantita"] * p
        valore += v; investito += s["quantita"] * p
        if not i:
            righe.append(f"| ⚠️ | {m} | dati non disponibili | | | | |"); continue
        if s["quantita"] > 0:
            ris = p * (1 - COMMISSIONE) * s["quantita"] / s.get("cassa_in", v) - 1
            righe.append(f"| 🟢 | **{m}** | Dentro dal {s['data_in']} | {prezzo(p)} | Esce sotto {prezzo(i['esce'])} | {pct(i['esce'] / p - 1)} | {pct(ris)} |")
        else:
            righe.append(f"| ⚪ | {m} | Fuori | {prezzo(p)} | Entra sopra {prezzo(i['entra'])} | {pct(i['entra'] / p - 1)} | |")
    chiuse, vinte, ultime = 0, 0, []
    if os.path.exists(REGISTRO):
        with open(REGISTRO) as f:
            tutte = list(csv.DictReader(f))
        for r in tutte:
            if r["azione"] == "VENDE":
                chiuse += 1; vinte += float(r["risultato_pct"]) > 0
        for r in tutte[-8:][::-1]:
            esito = f" ({pct(float(r['risultato_pct']) / 100)})" if r["risultato_pct"] else ""
            ultime.append(f"- {r['data']} · {r['azione']} {r['moneta']} a {prezzo(float(r['prezzo']))}{esito}")
    ini = stato["capitale_iniziale"]
    data = giorno(max(i["data"] for i in info.values())) if info else "-"
    out = [
        "# Bot trend · SIMULATO",
        "",
        "Nessun ordine reale: il bot segue i prezzi veri di Kraken e registra cosa avrebbe fatto.",
        "",
        f"## Conto simulato: {eur(valore)} {VALUTA}  {pct(valore / ini - 1)}",
        "",
        f"Partenza {eur(ini)} {VALUTA} il {stato['creato']} · Investito {investito / valore * 100:.0f} % · "
        f"Operazioni chiuse {chiuse} ({vinte} in guadagno) · Dati al {data}",
        "",
        f"| | Moneta | Stato | Prezzo {VALUTA} | Prossima mossa | Distanza | Risultato |",
        "|---|---|---|---|---|---|---|",
        *righe,
        "",
        "Distanza: di quanto deve muoversi il prezzo perche' il bot agisca alla prossima chiusura giornaliera.",
        "",
        "## Ultime operazioni",
        "",
        *(ultime or ["Nessuna operazione finora. E' normale: il bot aspetta che una moneta superi il massimo degli ultimi 55 giorni."]),
        "",
        f"Regola: compra sopra il massimo di {INGRESSO} giorni, vende sotto il minimo di {USCITA} giorni. "
        + f"Commissione simulata {COMMISSIONE * 100:.2f} % per ordine.".replace("0.", "0,"),
    ]
    if errori:
        out += ["", "⚠️ Problemi nell'ultima esecuzione:", *[f"- {e}" for e in errori]]
    with open(CRUSCOTTO, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return valore

def main():
    stato = carica_stato()
    info, errori = {}, []
    for m, nomi in MONETE.items():
        try:
            info[m] = elabora(m, stato["monete"][m], candele(nomi))
        except Exception as e:
            errori.append(f"{m}: {e}")
        time.sleep(1)                                 # rispetta i limiti dell'API pubblica
    with open(STATO, "w") as f:
        json.dump(stato, f, indent=1)
    valore = cruscotto(stato, info, errori)
    print(f"Conto simulato: {eur(valore)} {VALUTA} - monete aggiornate: {len(info)}/{len(MONETE)}")
    for e in errori: print("ERRORE", e)
    if not info: sys.exit(1)                          # nessun dato: segnala l'esecuzione come fallita

if __name__ == "__main__":
    main()
