# Stato del progetto (aggiornato al 25/11/2026)

File da leggere all'inizio di ogni nuova chat: riassume cosa è stato provato, cosa funziona e cosa gira adesso.

## Obiettivo e vincoli
- Bot automatico su Kraken che guadagni in modo costante; calo massimo accettato **−20 %**.
- Capitale di prova: 2.000 (su 10.000 disponibili). Chiavi API solo con permesso ordini, mai prelievo, in GitHub Secrets.
- Per ora **solo simulazione**: nessun ordine reale, nessuna chiave API.
- Risposte in italiano, concise e oneste. Ogni nuova versione di un file → numero di revisione incrementato.

## Cosa gira adesso (bot simulati)
| Bot | Cartella | Regola | Frequenza |
|---|---|---|---|
| 🎯 **Cecchino** (Rev 6) | `bot/rev6` | BTC guida, scatto BTC oltre 2 ATR | ogni 15 min (`bot_btc_guida.yml`) |
| 🐕 **Segugio** (Rev 7) | `bot/rev7` | BTC guida, scatto BTC oltre +1,25 % | ogni 15 min (`bot_btc_guida.yml`) |
| Trend Rev 2 | `bot/rev2` | Canale 55/20 giornaliero, 30 monete spot EUR | ogni giorno 00:20 UTC (`bot.yml`) |
| Trend Rev 3 | `bot/rev3` | come Rev 2 + filtro forza vs BTC +10 % | ogni giorno 00:20 UTC (`bot.yml`) |

Cecchino e Segugio sono partiti il 24/11/2026; servono 3-4 mesi di dati dal vivo per un giudizio.

### Regola "BTC guida" (Cecchino / Segugio) — perpetui Kraken, solo long, candele 4h
- **Segnale:** candela 4h di BTC in salita oltre 2 ATR (Cecchino) o oltre +1,25 % (Segugio). ATR = 14 candele, Wilder.
- **Monete:** tra le 12 liquide (AAVE ADA DOGE DOT ETH LINK LTC NEAR SOL TRX UNI XRP) quelle salite oltre 1,7 ATR nella stessa candela; max 5, le più forti. Ingresso entro 45 min dalla chiusura, altrimenti si salta.
- **Uscita:** stop 1,0 ATR; pareggio a +1 ATR; trailing 1,5 ATR dal massimo; se dopo 16 h non ha superato +3 ATR si chiude; oltre +3 ATR (fase 2) niente limite di tempo e trailing 1,5 + 0,10 × (guadagno − 3) ATR.
- **Rischio:** 0,75 % del capitale per operazione, max 5 posizioni, leva max 3.
- **Test (2022-2026, costi + spread, ottimizzato quindi ottimista):** Cecchino +26 %/anno, calo −13 %, ~80 operazioni/anno; Segugio +34 %/anno, calo −16 %, ~160 operazioni/anno. Prima dell'ottimizzazione la regola base dava +11-13 %/anno con calo −15/−19 %.

## Cosa è stato provato (sintesi)
| Idea | Esito | Perché |
|---|---|---|
| Pattern grafici (testa-spalle, doppi minimi…) | ❌ | nessun vantaggio |
| Coppie / statistica | ❌ | 4-5 %/anno, instabile |
| Rotazione monete → accumulo BTC | ❌ | perde BTC su ogni timeframe |
| Trend giornaliero 55/20, 30 monete spot | ⚠️ | ×1,9 ma calo −30/−38 %, vantaggio da 2023-24 e monete illiquide; sulle sole liquide ≈ 0 |
| Grid, ritorno alla media, combo | ❌ | |
| Rottura S/R con e senza retest, trendline oblique 1h | ❌ / ⚠️ | solo rottura orizzontale 1h appena positiva |
| Funding come segnale | ❌ | storico disponibile solo da 11/2025, nessun segnale |
| Compressione, caccia agli stop | ❌ | |
| 7 indicatori classici su BTC (RSI, MACD, Bollinger, ADX, volatilità, media 200, rendimento 24h) | ❌ | descrivono il movimento, non lo anticipano |
| Genetico "BTC guida" su tutte le monete | ❌ | trovava rimbalzi su monete illiquide, spariti nel 2025-26 |
| Genetico rotture/trend su monete liquide | ❌ | nessuna regola regge in verifica |
| **BTC guida 4h** (monete già partite dopo scatto BTC) | ✅ | unica regola che regge a tutti i controlli |
| BTC guida su 1h, 2h, 15 min | ❌ | troppo rumore e costi |
| Trailing in % fisso (metodo "trader TikTok") | ❌ | troppo stretto, preso dal rumore |
| Trailing in ATR / due fasi | ✅ | calo più basso, piccolo miglioramento |
| Trailing che si allarga senza fasi / senza limite di tempo | ❌ | dipende da pochi colpi enormi |
| BTC guida su spot | ❌ | costi spot troppo alti |
| BTC guida / trend contro BTC (accumulo BTC su spot) | ❌ | le monete non battono BTC: perde BTC sempre |

**Lezioni ricorrenti:** i risultati belli spesso vengono da monete illiquide o dal 2023-24; controllare sempre ritardo d'ingresso (dati al minuto), spread reale, monete liquide e "senza le 10 operazioni migliori".
**Per accumulare BTC:** tenere i BTC fermi e convertire periodicamente in BTC i guadagni del bot sui perpetui.

## Come si lavora
- La sandbox di Claude non raggiunge Kraken: **i test girano su GitHub**. Si scrive il nome dello script in `test/comando.txt` e si fa push; il risultato arriva in `test/risultati/ultimo.txt` (workflow `test.yml`, dati in cache in `test/dati`).
- Metodo: **prova** = primo 60 % dei dati, **verifica** = ultimo 40 %; si sceglie guardando solo la prova.
- Costi modellati: perpetui 0,07 % per ordine + funding 0,01 %/8h + spread reale (`SPREAD.json`) + ritardo; spot 0,25-0,40 % per ordine.
- Dati disponibili in cache: 1h di 30 perpetui `PF_*_1h.csv` (da 05/2022), 15 min delle 13 monete liquide `PF_*_15m.csv`, finestre da 1 minuto `MINUTI_4h.json`.
- Script utili da riusare: `genetico_btc_guida_rev1.py` (classe Dati, portafoglio, voto), `ottimizza_btc_guida_rev1.py` (simulazione BTC guida con 15 min), `trailing_btc_guida_rev1.py` (scarica 15 min).
- I bot GitHub che scrivono nel repository usano il gruppo di concorrenza `scrittura-repository`; per avviarli a mano: `gh api repos/giovanninirta/trading/actions/workflows/<file>.yml/dispatches -f ref=main`.

## Idee aperte
- Aggiungere ai cruscotti di Cecchino e Segugio la riga "guadagno convertito in BTC".
- Notifiche sul telefono a ogni operazione (es. app ntfy).
- Fase 2 del progetto: dopo qualche mese dal vivo, analizzare le operazioni in perdita (con verifica fuori campione di ogni filtro).
- Eventuale passaggio a soldi veri solo dopo il confronto dal vivo Cecchino/Segugio.
