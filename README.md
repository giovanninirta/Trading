# Trading

📌 **[Stato del progetto](STATO_PROGETTO.md)**: cosa è stato provato, cosa funziona, cosa gira adesso.

Tutti i bot sono **simulati**: seguono i prezzi veri di Kraken e registrano cosa avrebbero fatto, senza ordini reali e senza chiavi API. Ognuno parte con 2.000 simulati.

## 🚀 Bot "BTC guida": dopo uno scatto forte di BTC
Perpetui Kraken, controllo ogni 15 minuti ([esecuzioni](https://github.com/giovanninirta/Trading/actions/workflows/bot_btc_guida.yml)).

| Bot | Cosa fa | Monete | Dal | Test 2022-2026 |
|---|---|---|---|---|
| **[🎯 Cecchino](bot/rev6/README.md)** | **Long** quando BTC sale di oltre 2 ATR in 4 ore: compra le monete che l'hanno seguito con più forza | 12 liquide | 24/11/2026 | ≈ +26 %/anno, calo −13 % |
| **[🐕 Segugio](bot/rev7/README.md)** | **Long** come Cecchino, ma basta un +1,25 % di BTC: circa il doppio delle operazioni | 12 liquide | 24/11/2026 | ≈ +34 %/anno, calo −16 % |
| **[🎯 Cecchino 29](bot/rev8/README.md)** | **Long**, stessa regola di Cecchino ma sceglie tra più monete | 29 | 25/11/2026 | ≈ +31 %/anno, calo −14 % |
| **[🐕 Segugio Short](bot/rev9/README.md)** | **Short** quando BTC scende di oltre l'1,5 % in 8 ore ed è sotto la sua media: vende le monete che crollano con lui (non le più crollate) | 29 | 26/11/2026 | ≈ +9 %/anno, calo −10 % |
| **[🎯 Cecchino + Short](bot/rev10/README.md)** | **Long e short insieme** sullo stesso conto: Cecchino 29 + Segugio Short | 29 | 26/11/2026 | ≈ +40 %/anno, calo −19 % |
| **[🎯 Cecchino 29 Stop](bot/rev11/README.md)** | **Long**, come Cecchino 29 ma non compra subito: ordine stop 0,1 ATR sopra la chiusura, valido 4 ore (compra solo se la moneta continua a salire) | 29 | 27/11/2026 | 2023-2026: ≈ +30 %/anno, calo −12 % (Cecchino 29 nello stesso periodo +30 %, −14 %) |

Rischio 0,75 % del capitale per operazione, leva massima 3. I numeri dei test sono ottimisti (regole scelte guardando il passato): dal vivo è normale fare meno. Il confronto dal vivo dirà quale regge.

## 📈 Bot "trend giornaliero": seguono i trend di settimane
Canale 55/20 giornaliero su 30 monete spot in EUR, aggiornati ogni giorno alle 00:20 UTC ([esecuzioni](https://github.com/giovanninirta/Trading/actions/workflows/bot.yml)).

| Bot | Cosa fa |
|---|---|
| **[📈 Trend semplice](bot/rev2/README.md)** | Compra quando una moneta rompe il massimo di 55 giorni, vende sotto il minimo di 20 |
| **[📈 Trend più forte di BTC](bot/rev3/README.md)** | Come il semplice, ma solo se la moneta sta facendo almeno il 10 % meglio di BTC |

Girano in parallelo per vedere sui prezzi reali se il filtro "più forte di BTC" aiuta.

## 🧪 Test
- **[Ultimo risultato](test/risultati/ultimo.txt)** · [tutti i risultati](test/risultati/) · [esecuzioni](https://github.com/giovanninirta/Trading/actions/workflows/test.yml)
- Per lanciare un test: scrivere il nome dello script in `test/comando.txt` (una riga per script). GitHub lo esegue e salva l'output in `test/risultati/`.

## 📁 Cartelle
| Cartella | Contenuto |
|---|---|
| [`bot/rev6`](bot/rev6) · [`rev7`](bot/rev7) · [`rev8`](bot/rev8) | Cecchino, Segugio, Cecchino 29 (BTC guida, solo long) |
| [`bot/rev9`](bot/rev9) · [`rev10`](bot/rev10) | Segugio Short, Cecchino + Short (motore long/short) |
| [`bot/rev11`](bot/rev11) | Cecchino 29 Stop (ingresso con ordine stop) |
| [`bot/rev2`](bot/rev2) · [`rev3`](bot/rev3) | Trend semplice, Trend più forte di BTC |
| [`bot/archivio_rev1`](bot/archivio_rev1) | Prima versione (10 monete in USDT), non più attiva |
| [`test/`](test) | Script di verifica delle strategie sui dati storici |

In ogni cartella dei bot: `README.md` = cruscotto, `registro.csv` = tutte le operazioni (compare alla prima operazione), `stato.json` = memoria del bot.
