# 🎯 Cecchino 29 Stop
**BTC guida · versione D · Rev 11 · SIMULATO** (nessun ordine reale)

In attesa del primo controllo: il cruscotto si riempie al primo giro del bot (ogni 15 minuti, workflow `bot_btc_guida.yml`).

Regola: come [Cecchino 29](../rev8/README.md), ma invece di comprare subito alla chiusura della candela da 4 ore mette un **ordine stop 0,1 ATR sopra la chiusura, valido 4 ore**: compra solo se la moneta continua a salire. Stop a 1 ATR sotto il prezzo pagato, uscite identiche.
