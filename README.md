# Trading

- **[Cruscotto del bot simulato](bot/README.md)** · aggiornato ogni giorno alle 00:20 UTC
- **[Ultimo risultato dei test](test/risultati/ultimo.txt)**

## Struttura

| Cartella | Contenuto |
|---|---|
| `bot/` | Bot trend (Canale 55/20, candele giornaliere) in modalità simulata: nessun ordine reale, nessuna chiave API |
| `test/` | Script di verifica delle strategie sui dati storici di Kraken |
| `test/comando.txt` | Quali test eseguire: modificandolo, GitHub li lancia e salva l'output in `test/risultati/` |
