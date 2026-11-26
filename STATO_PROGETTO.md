# Stato del progetto (aggiornato al 26/11/2026)

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
| 🐕 **Segugio Short** (Rev 9) | `bot/rev9` | short dopo i crolli di BTC (8 h, < −1,5 %, BTC sotto media 160), genetico n. 1 | ogni 15 min (`bot_btc_guida.yml`) |
| 🎯 **Cecchino + Short** (Rev 10) | `bot/rev10` | Cecchino 29 + Segugio Short nello stesso conto (5 long + 8 short, leva 3) | ogni 15 min (`bot_btc_guida.yml`) |
| 🎯 **Cecchino 29 Stop** (Rev 11) | `bot/rev11` | come Cecchino 29 ma ingresso con ordine stop 0,1 ATR sopra la chiusura, valido 4 h; stop 1 ATR sotto il prezzo pagato | ogni 15 min (`bot_btc_guida.yml`) |
| Trend Rev 2 | `bot/rev2` | Canale 55/20 giornaliero, 30 monete spot EUR | ogni giorno 00:20 UTC (`bot.yml`) |
| Trend Rev 3 | `bot/rev3` | come Rev 2 + filtro forza vs BTC +10 % | ogni giorno 00:20 UTC (`bot.yml`) |

Cecchino e Segugio sono partiti il 24/11/2026 (Cecchino 29, Segugio Short e Cecchino + Short dal 26/11/2026); servono 3-4 mesi di dati dal vivo per un giudizio.

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
| Rottura con ingresso adattivo su **4 ore** (`test_rottura_ritest_rev3.py`) | ⚠️ | costi scesi a ~0,15 R. Formalmente PROMOSSA (short, 3 tocchi, adattivo 0,40: sulle 17 nuove netto +0,10 R, senza le 10 migliori +0,04, +15 %/anno) MA: sulle 13 liquide è negativa anche in prova (−0,01) e in tutto (−0,02 R, −11 %/anno); calo −42 % sulle nuove; tutti gli short positivi sulle nuove e negativi sulle liquide → probabile effetto del calo strutturale delle alt meno liquide (2022-2026), da verificare con ingressi short a caso. Long sempre negativi |
| **BTC guida al ribasso (short)**, idee di "Segugio v2" (`test_btc_guida_short_rev1.py`) | ❌ | tutte le 12 varianti negative al netto sulle 12 liquide (−0,03/−0,10 R), anche in prova; scelta (BTC < −2 ATR, sotto la media 50, uscita a specchio di Cecchino): netto −0,05 R sulle 17 nuove, calo −51 %, solo +0,03/+0,04 R meglio di short a caso. Lo short dopo il crollo di BTC non ha il vantaggio che ha il long dopo lo scatto. Uscita "v2" peggiore dello specchio di Cecchino |
| **Algoritmo genetico su tutti i 18 parametri di Cecchino** (`genetico_cecchino_rev1.py`) | ❌ | classico eccesso di adattamento: la migliore (BTC > 2,75 ATR, ATR 10, RSI ≤ 75, BTC sopra media 190-200, max 8, stop 1,3, fase 1 8 h) in prova +0,64 R e +22 %/anno, in verifica −0,11 R e −3 %/anno; sulle 17 nuove +9,5 %/anno contro +19,4 % di Cecchino. Parametri vicini stabili (23/27) ma non basta. **Si tiene Cecchino com'è** |
| **Algoritmo genetico SHORT** (`genetico_short_rev1.py`) | 🟡 | PROMOSSA dal criterio. Migliore: BTC < −1,5 % su candele **8 h**, ATR 20, monete scese > 1,8 ATR **saltando le 2 più deboli**, **RSI ≥ 25**, max 8, stop 0,9 ATR, pareggio 1,75, trailing 2,0, fase 1 8 h, fase 2 2,5 (+0,10), solo con BTC sotto la media 160 (+5 %). Prova +0,62 R → verifica +0,10 R (forte calo) ; 17 nuove +0,22 R, senza le 10 migliori +0,04, +7 %/anno, calo −9 %, contro −0,07 R degli short a caso. Solo 26-50 op/anno. Tratto comune dei 3 semi: evitare le monete più crollate (rimbalzano). **Anno per anno e insieme a Cecchino 29** (`cecchino_piu_short_rev1.py`): short su 29 monete +8,7 %/anno, calo −10 %, anni +21/−8/+7/+31/−8 % (2026 negativo); Cecchino 29 + short nello stesso portafoglio +40 %/anno contro +29 %, ma calo −19 % contro −14 %: rendimento/calo quasi uguale (2,1 contro 2,1) → gli short aggiungono rendimento come farebbe più rischio, non migliorano il rapporto |
| Momento intraday per fascia oraria (salita dall'apertura UTC → tenuta fino a fine giornata) | ⚠️ | solo long con salite forti (≥0,5-0,8 ATR giornalieri, ore 8 e 16 UTC) appena positivo, più in verifica che in prova; senza le 10 migliori ≈ 0; short sempre negativo |
| **Cecchino tutto su 5 minuti** (`cecchino_5m_rev1.py`): scatto BTC oltre ZB ATR su candela 5m, monete oltre ZM ATR, uscita Cecchino in ATR 5m; griglia ZB 2-5, ZM 1,5-3,5, ST 1-2, TR 1,5-3, F1 1-4 h, long e short | ❌ (taker) / ⚠️ (maker) | lordo positivo in tutte le 192 varianti (+0,25/+0,73 R, effetto di continuazione nei 10-20 min dopo lo scatto) ma costi taker 0,55-0,79 R: **0 varianti su 192 positive al netto taker**. Con ingresso maker (ipotesi ottimista: limite sempre eseguito all'apertura) long ZB 5 / ZM 2,5 / ST 1 / TR 3: 17 nuove +0,75 R ma senza le 10 migliori −0,19, liquide negative, calo −24 % → bocciata; short ZB 4 / ZM 3,5 / ST 2 / TR 1,5: 17 nuove +0,31 R, senza 10 +0,12, +45 %/anno ma calo −39 % (2024 −35 %) → bocciata per il calo. Il maker qui è sopravvalutato: in un movimento che continua il limite non viene eseguito (selezione avversa). Prossimo passo: simulare il limite eseguito solo se il prezzo lo attraversa |
| Statistiche Cecchino 5m short maker (`statistiche_cecchino_5m_rev1.py`, curva in `test/risultati/curva_cecchino_5m_short.png`) | ⚠️ | 880 op in 4,4 anni (0,55/giorno), vinte 39 % (+2,53 R), perse 61 % (−1,10 R). **Le 30 migliori valgono +319 R su +285 R totali**: senza di loro perde. Guadagno quasi tutto nei crolli 2022 (lug-nov +15/+40 % al mese), 2024 sempre in perdita (calo −37 %). Il 72 % delle perse non arriva mai a +0,25 R e prende lo stop in 10 min: il problema è l'ingresso, non l'uscita. 20 uscite alternative: trailing/pareggio/fase 2 cambiano quasi nulla (±0,02 R); obiettivi fissi e uscite a tempo peggiorano (il vantaggio sta nelle code). Unica idea d'uscita da provare: chiudere subito se dopo 1-2 candele non è a favore |
| **Cecchino 5m Rev 2** (`cecchino_5m_rev2.py`, solo 2023-2026, crollo 2022 escluso): ordini stop/limite d'ingresso, uscita rapida, analisi ingressi sbagliati, portafogli piu' larghi | ❌ | **Ingresso con ordine STOP** (si entra solo se il prezzo va oltre di 0,25-1 ATR nel verso, entro 1-3 candele) alza il netto per operazione di circa +0,5 R rispetto al mercato (short ZB 4/ZM 3,5: da −0,13 a +0,42 R; long da −0,20 a +0,16 R). **Limite realistico** (eseguito solo se attraversato) sempre negativo (−0,25/−0,55 R): il maker della Rev 1 era un'illusione (selezione avversa). **Uscita rapida** 5-15 min peggiora sempre. MA nel portafoglio la media per operazione crolla (short +0,42 → −0,19 R): il vantaggio sta nei grandi eventi in cui scattano 20-29 monete insieme, e il portafoglio ne prende solo poche. Tutte bocciate sulle 17 nuove (calo −28/−66 %). 5 operazioni al giorno: i segnali ci sono (10-24/giorno, ma solo nel 40-70 % dei giorni) ma con stop 5m la leva 3 limita a ~5 posizioni; long+short frequenti a 0,25 % = 4,9 op/giorno, −18 %/anno, calo −87 %. Ingressi sbagliati: unico elemento coerente in prova e verifica = fascia 11-19 UTC (peggiore per long e short); nessuna caratteristica separa da sola. Dati: alcune monete hanno candele ferme (ATR ~0, z enormi) da filtrare |
| **Cecchino 5m Rev 3** (`cecchino_5m_rev3.py`, 2023-2026): stop fisso 1 % e leva massima 10 | ❌ | Stop 1 %: costi da ~0,6 a 0,27 R ma anche il lordo scende in proporzione (da +0,9 a +0,33 R): in denaro per operazione circa uguale, netto +0,04/+0,08 R. Leva 10: le 5 operazioni al giorno si raggiungono (long+short stop 1 %, 0,5 %/20 pos: 7,9/giorno; 0,25 %/30: 8,3/giorno) ma con **cali da −71 a −98 %** (2024 −80/−86 %): tutte le posizioni sono legate a BTC e perdono insieme. Anni estremi (+858 % nel 2023, poi −81 %). Tutte bocciate sulle 17 nuove (calo −28/−77 %). La meno peggio: long stop 1 %, 0,25 %/30/leva 10 → 17 nuove +13 %/anno calo −15 %, ma 29 monete +12 % calo −37 %, 2026 −27 %. Le 17 nuove vanno sempre meglio delle 12 liquide. **Linea 5 minuti: chiusa come bot principale; da tenere l'ordine STOP d'ingresso (+0,5 R per operazione) da provare su Cecchino 4h** |
| **Cecchino 29 con ordine STOP d'ingresso** (`cecchino_29_stop_ingresso_rev1.py`, solo 2023-2026) | 🟡 | Si compra solo se il prezzo sale ancora di X ATR 4h oltre la chiusura del segnale entro W ore. Attuale (dal 2023): +29,7 %/anno, calo −14 %, netto +0,40 R. **STOP 0,1 ATR / 1 h PROMOSSA** (+32,3 %, calo −13 %, netto +0,46, prova e verifica meglio, nuove +0,40 / senza 10 +0,12) ma sulle 12 liquide leggermente peggio (+19,2 contro +20,5 %). **STOP 0,1 ATR / 4 h PROMOSSA** e migliore in tutti e tre gli universi (29: +29,9 % calo −12 %; 12 liquide +22,4 contro +20,5 %, calo −14 contro −16; 17 nuove +22,2 contro +18,8 %, calo −15 contro −19). Soglie 0,25-0,75 ATR peggiori: saltano anche le buone. A 4 ore l'ordine stop non da' il +0,5 R visto a 5 minuti: miglioramento piccolo (~+0,02/+0,06 R), soprattutto meno calo. Da provare dal vivo in parallelo, non sostituire subito |
| **Trend 15 minuti con stop largo e guadagno messo al sicuro** (`trend_15m_rev1.py`, 2023-2026, 13 liquide con BTC + 17 nuove) | ❌ | Trend EMA 50/200 su 1h o 4h; ingresso su media 50 / RSI 35 / ritracciamento 2 % / a caso; uscita '1-2' (pareggio a +1 %, a +2 % stop +1 % e trailing 1 %), '2-4', obiettivo fisso 1 % o 2 %; stop largo 3/5/10 %. **Spot: 0 varianti su 96 positive** (costi ~0,68 % per operazione contro un lordo di +0,1/+0,3 %). Perpetui long: 8/96 appena positive in prova, migliore (4h, a caso, 2-4, stop 10 %) −30 %/anno, calo −90 % sulle 30. Short: 0/96. Ipotesi 'raramente si compra sul massimo' falsa: con obiettivo fisso 1 % e stop 10 % si vince l'89 % delle volte ma l'11 % di stop a −10 % cancella tutto (servirebbe meno del 9 %). Il 'buon punto' d'ingresso non batte l'ingresso a caso (media −0,75/−0,64 % contro −0,60 %) |

**Lezioni ricorrenti:** ottimizzare tanti parametri insieme peggiora fuori campione (genetico su 18 parametri: prova ottima, verifica negativa).  una regola che funziona su 13 monete va sempre verificata su monete mai usate (le altre 17 dei 30 perpetui), con criterio fissato prima.  i risultati belli spesso vengono da monete illiquide o dal 2023-24; controllare sempre ritardo d'ingresso (dati al minuto), spread reale, monete liquide e "senza le 10 operazioni migliori".
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
