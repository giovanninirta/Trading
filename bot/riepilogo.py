#!/usr/bin/env python3
"""
RIEPILOGO DAL VIVO dei bot "BTC guida" (Rev 6-11) - scrive nel README principale, tra i segni
<!-- RIEPILOGO --> e <!-- /RIEPILOGO -->, una tabella aggiornata ogni 15 minuti con:
  - quanto manca al prossimo segnale: movimento di BTC nella candela IN CORSO contro la soglia (ATR o %),
    prezzo di BTC che servirebbe alla chiusura, quanto manca in $ e in %, quando chiude la candela
  - per ogni bot: capitale (equity, comprese le posizioni aperte ai prezzi di adesso), risultato, operazioni chiuse,
    vinte, posizioni aperte, ordini in attesa, scatti di BTC visti
Il segnale conta solo alla CHIUSURA della candela: un movimento a meta' candela non basta.
Uso (dalla cartella principale):  python bot/riepilogo.py
"""
import json, os, sys, time
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "rev8"))
import bot_btc_guida_rev8 as B

README = "README.md"
INIZIO, FINE = "<!-- RIEPILOGO -->", "<!-- /RIEPILOGO -->"
BOT = [("rev6", "🎯 Cecchino"), ("rev7", "🐕 Segugio"), ("rev8", "🎯 Cecchino 29"), ("rev11", "🎯 Cecchino 29 Stop"),
       ("rev9", "🐕 Segugio Short"), ("rev10", "🎯 Cecchino + Short")]
H4, H8 = 4 * 3600, 8 * 3600

def num(x, d=0): return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
def segno(x, d=2): return ("+" if x >= 0 else "−") + num(abs(x), d)
def hm(t): return datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M")
def durata(sec):
    m = max(0, int(sec // 60)); return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"

def main():
    ora = int(time.time())
    prezzi = B.ticker()
    bid, ask = prezzi["XBT"]; btc = (bid + ask) / 2
    # ---- candela 4h in corso (segnali long) ----
    b4 = B.candele("BTC", "4h", ora - 80 * H4, ora)
    chiuse4 = [b for b in b4 if b[0] + H4 <= ora]
    A = B.atr([b[2] for b in chiuse4], [b[3] for b in chiuse4], [b[4] for b in chiuse4])
    c4, a4 = chiuse4[-1][4], A[-1]; inizio4 = chiuse4[-1][0] + H4; fine4 = inizio4 + H4
    z_ora = (btc - c4) / a4; pct4 = btc / c4 - 1
    serve_atr = c4 + 2.0 * a4; serve_pct = c4 * 1.0125
    # ---- candela 8h in corso (segnali short) ----
    s9 = json.load(open("bot/rev9/stato.json")) if os.path.exists("bot/rev9/stato.json") else {}
    sh = (s9.get("btc_ultima") or {}).get("short") or {}
    righe_seg = []
    righe_seg.append(f"| **Long, BTC oltre 2 ATR** (Cecchino, Cecchino 29, Cecchino 29 Stop, Cecchino + Short) | 4 h dalle {hm(inizio4)} | "
                     f"**{segno(z_ora, 1)} ATR** ({segno(pct4 * 100)} %) | oltre +2,0 ATR → BTC sopra **{num(serve_atr)} $** | "
                     f"{'✅ ci siamo' if btc >= serve_atr else f'**{segno((serve_atr - btc) / a4, 1)} ATR** = {segno(serve_atr - btc, 0)} $ ({segno((serve_atr / btc - 1) * 100)} %)'} | "
                     f"{hm(fine4)} UTC (tra {durata(fine4 - ora)}) |")
    righe_seg.append(f"| **Long, BTC oltre +1,25 %** (Segugio) | 4 h dalle {hm(inizio4)} | **{segno(pct4 * 100)} %** | "
                     f"oltre +1,25 % → BTC sopra **{num(serve_pct)} $** | "
                     f"{'✅ ci siamo' if btc >= serve_pct else f'**{segno((serve_pct / btc - 1) * 100)} %** = {segno(serve_pct - btc, 0)} $'} | "
                     f"{hm(fine4)} UTC (tra {durata(fine4 - ora)}) |")
    if sh.get("prezzo"):
        c8 = sh["prezzo"]; inizio8 = sh["t"] + H8; fine8 = inizio8 + H8; pct8 = btc / c8 - 1; serve8 = c8 * 0.985
        sma = sh.get("sma"); filtro = sma * 1.05 if sma else None
        cond = (f"e BTC sotto {num(filtro)} $ (media 160 × 1,05): {'✅ sì' if btc < filtro else '❌ no'}") if filtro else ""
        righe_seg.append(f"| **Short, BTC sotto −1,5 %** (Segugio Short, Cecchino + Short) | 8 h dalle {hm(inizio8)} | **{segno(pct8 * 100)} %** | "
                         f"sotto −1,5 % → BTC sotto **{num(serve8)} $** {cond} | "
                         f"{'✅ ci siamo' if btc <= serve8 else f'**{segno((serve8 / btc - 1) * 100)} %** = {segno(serve8 - btc, 0)} $'} | "
                         f"{hm(fine8)} UTC (tra {durata(fine8 - ora)}) |")
    # ---- bot ----
    righe_bot = []
    for cartella, nome in BOT:
        f = f"bot/{cartella}/stato.json"
        if not os.path.exists(f): continue
        s = json.load(open(f))
        aperto = 0.0
        for p in s.get("posizioni", []):
            ba = prezzi.get(p["moneta"])
            if not ba: continue
            if p.get("lato", "long") == "long": aperto += (ba[0] - p["prezzo"]) * p["quantita"]
            else: aperto += (p["prezzo"] - ba[1]) * p["quantita"]
        eq = s["capitale"] + aperto; ris = eq / 2000.0 - 1
        segnali = s.get("segnali", 0)
        if isinstance(segnali, dict): segnali = sum(segnali.values())
        vinte = f"{s['vinte'] / s['chiuse'] * 100:.0f} %" if s.get("chiuse") else "–"
        r_medio = f"{s['somma_r'] / s['chiuse']:+.2f} R".replace(".", ",") if s.get("chiuse") else "–"
        ordini = len(s.get("ordini", [])) if "ordini" in s else "–"
        freccia = "🟢" if ris > 0.0005 else ("🔴" if ris < -0.0005 else "⚪")
        righe_bot.append(f"| [{nome}](bot/{cartella}/README.md) | {freccia} **{num(eq, 2)} $** | {segno(ris * 100)} % | "
                         f"**{s.get('chiuse', 0)}** | {vinte} | {r_medio} | {len(s.get('posizioni', []))} | {ordini} | {segnali} |")
    L = [INIZIO, f"## 📡 Situazione adesso", "",
         f"BTC **{num(btc)} $** · aggiornato alle **{hm(ora)} UTC** del {datetime.fromtimestamp(ora, timezone.utc).strftime('%d/%m/%Y')} "
         f"(ogni 15 minuti) · ATR 4 h di BTC {num(a4)} $", "",
         "### Quanto manca al prossimo segnale",
         "Il segnale conta solo **alla chiusura della candela**: guarda il movimento della candela in corso rispetto alla chiusura precedente.", "",
         "| Segnale (bot) | Candela in corso | Movimento adesso | Serve alla chiusura | Manca | Chiude |", "|---|---|--:|---|--:|---|"]
    L += righe_seg + ["", "### Bot", "",
                      "| Bot | Capitale (equity) | Risultato | Operazioni chiuse | Vinte | Risultato medio | Aperte | Ordini in attesa | Scatti BTC visti |",
                      "|---|--:|--:|:-:|:-:|:-:|:-:|:-:|:-:|"] + righe_bot
    L += ["", "Capitale di partenza 2.000 $ simulati per bot; l'equity comprende le posizioni aperte ai prezzi di adesso.", FINE]
    testo = open(README).read()
    blocco = "\n".join(L)
    if INIZIO in testo and FINE in testo:
        testo = testo[:testo.index(INIZIO)] + blocco + testo[testo.index(FINE) + len(FINE):]
    else:
        a = testo.index("\n## ")
        testo = testo[:a] + "\n\n" + blocco + "\n" + testo[a:]
    open(README, "w").write(testo)
    print("riepilogo aggiornato")

if __name__ == "__main__":
    main()
