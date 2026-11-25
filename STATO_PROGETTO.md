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
| 🎯 **Cecchino 29** (Rev 8) | `bot/rev8` | regola Cecchino, sceglie tra 29 monete (max 5 posizioni) | ogni 15 min (`bot_btc_guida.yml`) |
| Trend Rev 2 | `bot/rev2` | Canale 55/20 giornaliero, 30 monete spot EUR | ogni giorno 00:20 UTC (`bot.yml`) |
| Trend Rev 3 | `bot/rev3` | come Rev 2 + filtro forza vs BTC +10 % | ogni giorno 00:20 UTC (`bot.yml`) |

Cecchino e Segugio sono partiti il 24/11/2026 (Cecchino 29 appena unito a main); servono 3-4 mesi di dati dal vivo per un giudizio.

**Verifica sulle 17 monete mai usate (25/11/2026, `verifica_monete_nuove_btc_guida_rev1.py`, criterio fissato prima: netto > +0,05 R, senza le 10 migliori > 0, annuo > 0):**
- 🎯 Cecchino **PROMOSSO in modo netto**: netto +0,36 R (come sulle 12 d'origine), prova +0,36 / verifica +0,36, senza le 10 migliori +0,09 R, +22 %/anno, calo −19 %; 12 monete su 17 positive; anni +22/+48/+6/+41/−11 %.
- 🐕 Segugio **promosso al limite**: netto +0,14 R, senza le 10 migliori +0,03 R, +22 %/anno ma **calo −35 %** (oltre il limite del −20 %), anni +70/+41/−14/+35/−15 %. Più fragile del Cecchino.
- **Cecchino su 29 monete** (12 liquide + 17 nuove, regola identica, `cecchino_29_monete_rev1.py`): netto +0,40 R, senza le 10 migliori +0,20 R, prova +0,33 / verifica +0,55, **+31 %/anno, calo −14 %, tutti gli anni positivi** (+18/+45/+16/+51/+8 %), 98 op/anno (60 % su monete nuove). Togliere APE e XTZ (spread > 0,2 %) non cambia nulla. Con 10 posizioni (`cecchino_29_posizioni_rev1.py`): rischio 0,75 % → +29 %/anno ma calo −23 %; rischio 0,50 % → 158 op/anno, +26 %, calo −18 %; scelto 5 posizioni a 0,75 %. Segugio a 29: +37 %/anno ma calo −24 % e R per operazione più basso.
- Controllo: sulle 12 d'origine lo stesso script riproduce i test (Cecchino +22 %/anno, Segugio +33 %).

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
| Pullback 1h dentro il trend giornaliero 55/20 (`test_intraday_rev1.py`) | ❌ | vantaggio lordo ≈ 0, perde i costi (−0,11/−0,19 R); il filtro di trend non aiuta |
| Pullback 1h con trend ORARIO + minimo su supporto (`test_intraday_rev2.py`) | ⚠️ | EMA 50/200 oraria e supporto da soli peggiorano; solo struttura (massimi e minimi crescenti) + minimo su vecchio minimo alza il lordo (fino a +0,09/+0,13 R, crescente con la profondità) ma i costi (~0,2 R) lo superano: netto in prova −0,10/−0,12 R |
| Pullback Rev 3 (`test_intraday_rev3.py`): struttura + supporto + uscita Cecchino in R senza limite di tempo | 🟡 | l'uscita Cecchino alza molto il lordo (fino a +0,3/+0,4 R). Migliore: mercato, supporto toccato 2 volte, P 4-5 → netto prova +0,02/+0,08, verifica +0,36/+0,44, +8 %/anno, calo −11/−19 %, ma solo 50-75 op/anno e negativo senza le 10 migliori. Trailing 1,0 R peggio di 1,5 R. Ordine limite sul supporto peggio (esecuzioni sfavorevoli) |
| Pullback Rev 4: chiusura di metà posizione a 2R o 3R (`test_intraday_rev4.py`) | ❌ | toglie circa 0,1 R lordo a tutte le varianti, il calo non scende. Senza parziale, P 5 + 2 tocchi è positivo in ogni anno 2022-2026 (+5, +2, +8, +12, +13 %) |
| Pullback su 15 min (`test_pullback_15m_rev1.py`, stessa forma e stessa durata) | ❌ | lordo ≈ 0 e costi 0,24-0,30 R: nessun vantaggio nemmeno prima dei costi |
| Pullback 1h: rientri sullo stesso pullback dopo uno stop (`studio_falsa_rottura_rev1.py`) | ⚠️ | P 5: 36 rientri, media +1,07 R ma mediana 0 e senza i 3 migliori (NEAR +16,4, BTC +8,7, +6,5) ≈ +0,2 R come i primi ingressi: nessun vantaggio speciale, solo 3 colpi fortunati. Anche i primi ingressi: senza i 3 migliori il lordo scende da +0,26 a ≈ +0,11 R |
| Falsa rottura del supporto come regola a sé (stesso script) | ❌ | senza T4 lordo ≈ 0; con T4 lordo +0,1/+0,23 ma netto in prova ≈ 0 e anni incoerenti |
| **Verifica finale pullback Rev 3 sulle 17 monete mai usate** (`verifica_monete_nuove_pullback_rev1.py`, criterio fissato prima) | ❌ | BOCCIATA: lordo +0,05 R, netto −0,18 R, mediana −1 R, 11 monete su 17 negative, anni −14/+10/−9/−15 %. Anche sulle 13 d'origine il lordo senza le 10 migliori è solo +0,03 R. **Linea del pullback orario chiusa.** |
| Rottura + ritest su 1h, long e short, con falsa rottura precedente (`test_rottura_ritest_rev1.py`) | ❌ | 32 varianti tutte negative al netto (−0,12/−0,26 R) su liquide e nuove; lordo solo +0,0/+0,16 R contro costi ~0,25 R; la falsa rottura precedente non aggiunge nulla, il ritest è peggio dell'ingresso alla rottura, la struttura peggiora |
| Rottura con ingresso adattivo (subito se coda lunga, ritest se chiusura sull'estremo; `test_rottura_ritest_rev2.py`) | ❌ | 48 varianti tutte negative al netto (−0,08/−0,25 R). La parte "subito con coda lunga" ha il lordo migliore (fino a +0,22 R), la parte "ritest dopo chiusura sull'estremo" è la più debole; costi ~0,25-0,3 R |
| Momento intraday per fascia oraria (salita dall'apertura UTC → tenuta fino a fine giornata) | ⚠️ | solo long con salite forti (≥0,5-0,8 ATR giornalieri, ore 8 e 16 UTC) appena positivo, più in verifica che in prova; senza le 10 migliori ≈ 0; short sempre negativo |

**Lezioni ricorrenti:** una regola che funziona su 13 monete va sempre verificata su monete mai usate (le altre 17 dei 30 perpetui), con criterio fissato prima.  i risultati belli spesso vengono da monete illiquide o dal 2023-24; controllare sempre ritardo d'ingresso (dati al minuto), spread reale, monete liquide e "senza le 10 operazioni migliori".
**Per accumulare BTC:** tenere i BTC fermi e convertire periodicamente in BTC i guadagni del bot sui perpetui.

## Come si lavora
- I test si possono lanciare anche da un ramo di lavoro con `workflow_dispatch` di `test.yml` sul ramo (il risultato viene salvato sul ramo).
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
