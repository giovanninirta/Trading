# Trading

## Bot simulati (aggiornati ogni giorno alle 00:20 UTC)

- **[Rev 2 · senza filtro](bot/rev2/README.md)**
- **[Rev 3 · con filtro "forza contro BTC"](bot/rev3/README.md)**

Stessa regola (Canale 55/20, 30 monete in EUR, 2.000 EUR simulati): girano in parallelo per vedere sui prezzi reali se il filtro aiuta.

## Test

- **[Ultimo risultato](test/risultati/ultimo.txt)**
- Per lanciare un test: modificare `test/comando.txt` (una riga per script). GitHub lo esegue e salva l'output in `test/risultati/`.

| Cartella | Contenuto |
|---|---|
| `bot/rev2`, `bot/rev3` | I due bot simulati: nessun ordine reale, nessuna chiave API |
| `bot/archivio_rev1` | Prima versione (10 monete in USDT), non piu' attiva |
| `test/` | Script di verifica delle strategie sui dati storici |
