# 🐕 Segugio Short
**BTC guida al ribasso · Rev 9 · SIMULATO** (nessun ordine reale)

## ➡️ 2.000,00 $   (+0,00 %)

Capitale di partenza 2.000 $ simulati · attivo da 1 giorni · ultimo controllo 2026-11-28 02:14 UTC

| Posizioni aperte | Operazioni chiuse | Vinte | Risultato medio | Segnali di BTC |
|:-:|:-:|:-:|:-:|:-:|
| **0** | **0** | **0 %** | **+0,00 R** | **short 1** |

**BTC adesso:**
- short: candela 8 h chiusa alle 2026-11-28 00:00 UTC: **-0,29 % (serve sotto -1,50 %), BTC sotto la media 160**

**Ultimo segnale short:** 2026-11-27 16:00 UTC, BTC -2,49 % (-0,9 ATR) → nessuna moneta abbastanza mossa · saltato: controllo arrivato 75 minuti dopo la chiusura

---

## Come agisce

**Carattere:** lavora quando BTC e' debole: vende le monete che crollano con BTC, ma non le piu' crollate.

### Lato SHORT (regola Segugio Short)
1. **Segnale:** la candela da 8 ore di BTC (chiude alle 00, 08, 16 UTC) scende di oltre **1,5 %**, e BTC e' **sotto la sua media di 160 candele** da 8 ore (tolleranza +5 %): si vende solo quando il mercato e' debole.
2. **Vende allo scoperto** le monete scese di oltre **1,8 ATR** (20 candele) nella stessa candela, con RSI non sotto 25; **salta le 2 piu' deboli** (le piu' crollate tendono a rimbalzare); al massimo **8** posizioni short.
3. **Stop** 0,9 ATR sopra l'ingresso; **pareggio** quando guadagna 1,75 ATR; poi segue il minimo a 2,0 ATR.
4. Se dopo **8 ore** non ha guadagnato +2,5 ATR si chiude; oltre (**fase 2**) niente limite di tempo e la distanza si allarga di 0,10 ATR per ogni ATR in piu'.

**Rischio:** ogni operazione rischia lo **0,75 % del capitale** (quanto si perde se tocca lo stop iniziale); la somma delle posizioni non supera 3 volte il capitale; mai due posizioni sulla stessa moneta.

**Costi simulati:** spread vero (si entra e si esce al prezzo peggiore tra bid e ask), 0,07 % di commissione per ordine, funding 0,01 % ogni 8 ore.

**Cosa aspettarsi (test):** circa 70 operazioni all'anno, +9 % all'anno, calo massimo -10 % (test 2022-2026 su 29 monete). Numeri da regole scelte guardando il passato: **dal vivo e' normale che siano piu' bassi**. Questo bot serve a scoprirlo senza rischiare soldi.

**Come leggere:** R = risultato diviso il rischio (−1 R = stop iniziale pieno). Ogni operazione e' nel file [registro.csv](registro.csv).

<details><summary>Note tecniche</summary>

BOT "SEGUGIO SHORT" (BTC guida al ribasso) - Rev 9 - MODALITA' SIMULATA (nessun ordine, nessuna chiave API)  
Motore unico long/short: la Rev 10 (Cecchino + Short) usa lo stesso codice con anche il lato long attivo.  
  
Regola SHORT (scelta dall'algoritmo genetico, genetico_short_rev1.py, n. 1; perpetui Kraken, 29 monete):  
  CANDELE    da 8 ore (00, 08, 16 UTC), costruite da due candele da 4 ore  
  SEGNALE    la candela da 8 ore di BTC chiude in DISCESA di oltre l'1,5 %, e BTC e' sotto la sua media di 160  
             candele da 8 ore (al massimo +5 % sopra: tolleranza)  
  COSA VENDE le monete scese di oltre 1,8 ATR (ATR 20 candele) nella stessa candela, con RSI 14 non sotto 25;  
             si saltano le 2 piu' deboli (tendono a rimbalzare) e si vendono le successive, max 8 posizioni short  
  STOP       0,9 ATR sopra l'ingresso; a pareggio quando il guadagno arriva a 1,75 ATR; poi segue il minimo a 2,0 ATR  
  FASE 1     se dopo 8 ore dalla chiusura del segnale non ha superato +2,5 ATR di guadagno, si chiude  
  FASE 2     oltre +2,5 ATR: niente limite di tempo, distanza 2,0 + 0,10 x (guadagno - 2,5) ATR  
  RISCHIO    0,75 % del capitale per operazione; posizioni totali al massimo 3 volte il capitale;  
             mai due posizioni (long o short) sulla stessa moneta  
Costi simulati: vendita al "bid", riacquisto all'"ask" (spread vero), 0,07 % di commissione per ordine,  
funding 0,01 % ogni 8 ore (pagato sempre, per prudenza). Stop controllati sulle candele da 15 minuti.  
  
Gira ogni 15 minuti su GitHub. File: stato.json (memoria), registro.csv (operazioni), README.md (cruscotto).
</details>
