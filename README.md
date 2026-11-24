# Trading

## Bot simulati "BTC guida" (perpetui, candele 4h, controllo ogni 15 minuti)

- **[Rev 4 · versione A: scatto di BTC oltre 2 ATR](bot/rev4/README.md)**
- **[Rev 5 · versione B: scatto di BTC oltre +1,25 %](bot/rev5/README.md)**

Quando una candela da 4 ore di BTC scatta in salita, comprano le monete liquide che l'hanno seguita
(stop 1 ATR, pareggio, trailing, 16 ore o fase 2). 2.000 $ simulati ciascuno, rischio 0,75 % per operazione.

## Bot simulati trend giornaliero (aggiornati ogni giorno alle 00:20 UTC)

- **[Rev 2 · senza filtro](bot/rev2/README.md)**
- **[Rev 3 · con filtro "forza contro BTC"](bot/rev3/README.md)**

Stessa regola (Canale 55/20, 30 monete in EUR, 2.000 EUR simulati): girano in parallelo per vedere sui prezzi reali se il filtro aiuta.

## Test

- **[Ultimo risultato](test/risultati/ultimo.txt)**
- Per lanciare un test: modificare `test/comando.txt` (una riga per script). GitHub lo esegue e salva l'output in `test/risultati/`.

| Cartella | Contenuto |
|---|---|
| `bot/rev4`, `bot/rev5` | Bot simulati BTC guida: nessun ordine reale, nessuna chiave API |
| `bot/rev2`, `bot/rev3` | Bot simulati trend giornaliero: nessun ordine reale, nessuna chiave API |
| `bot/archivio_rev1` | Prima versione (10 monete in USDT), non piu' attiva |
| `test/` | Script di verifica delle strategie sui dati storici |
