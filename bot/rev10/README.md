# 🎯 Cecchino + Short
**BTC guida long + short · Rev 10 · SIMULATO** (nessun ordine reale)

## ➡️ 2.000,00 $   (+0,00 %)

Capitale di partenza 2.000 $ simulati · attivo da 1 giorni · ultimo controllo 2026-11-27 10:45 UTC

| Posizioni aperte | Operazioni chiuse | Vinte | Risultato medio | Segnali di BTC |
|:-:|:-:|:-:|:-:|:-:|
| **0** | **0** | **0 %** | **+0,00 R** | **long 0 / short 0** |

**BTC adesso:**
- long: candela 4 h chiusa alle 2026-11-27 08:00 UTC: **+0,2 ATR (serve oltre 2,0)**
- short: candela 8 h chiusa alle 2026-11-27 08:00 UTC: **+1,78 % (serve sotto -1,50 %), BTC sotto la media 160**

---

## Come agisce

**Carattere:** compra dopo gli scatti di BTC (Cecchino 29) e vende allo scoperto dopo i crolli quando BTC e' debole (Segugio Short), sullo stesso capitale.

### Lato LONG (regola Cecchino 29)
1. **Segnale:** la candela da 4 ore di BTC chiude in salita di oltre **2,0 volte il suo ATR** (14 candele).
2. **Compra** le monete salite di oltre **1,7 ATR** nella stessa candela, le piu' forti, al massimo **5** posizioni long.
3. **Stop** 1,0 ATR sotto; **pareggio** a +1,00 ATR; poi segue il massimo a 1,5 ATR.
4. Se dopo **16 ore** non ha superato +3,0 ATR si chiude; oltre (**fase 2**) niente limite di tempo e la distanza si allarga di 0,10 ATR per ogni ATR in piu'.

### Lato SHORT (regola Segugio Short)
1. **Segnale:** la candela da 8 ore di BTC (chiude alle 00, 08, 16 UTC) scende di oltre **1,5 %**, e BTC e' **sotto la sua media di 160 candele** da 8 ore (tolleranza +5 %): si vende solo quando il mercato e' debole.
2. **Vende allo scoperto** le monete scese di oltre **1,8 ATR** (20 candele) nella stessa candela, con RSI non sotto 25; **salta le 2 piu' deboli** (le piu' crollate tendono a rimbalzare); al massimo **8** posizioni short.
3. **Stop** 0,9 ATR sopra l'ingresso; **pareggio** quando guadagna 1,75 ATR; poi segue il minimo a 2,0 ATR.
4. Se dopo **8 ore** non ha guadagnato +2,5 ATR si chiude; oltre (**fase 2**) niente limite di tempo e la distanza si allarga di 0,10 ATR per ogni ATR in piu'.

**Rischio:** ogni operazione rischia lo **0,75 % del capitale** (quanto si perde se tocca lo stop iniziale); la somma delle posizioni non supera 3 volte il capitale; mai due posizioni sulla stessa moneta.

**Costi simulati:** spread vero (si entra e si esce al prezzo peggiore tra bid e ask), 0,07 % di commissione per ordine, funding 0,01 % ogni 8 ore.

**Cosa aspettarsi (test):** circa 165 operazioni all'anno (95 long, 70 short), +40 % all'anno, calo massimo -19 % (test 2022-2026 su 29 monete). Numeri da regole scelte guardando il passato: **dal vivo e' normale che siano piu' bassi**. Questo bot serve a scoprirlo senza rischiare soldi.

**Come leggere:** R = risultato diviso il rischio (−1 R = stop iniziale pieno). Ogni operazione e' nel file [registro.csv](registro.csv).

<details><summary>Note tecniche</summary>

BOT "CECCHINO + SHORT" - Rev 10 - MODALITA' SIMULATA (nessun ordine, nessuna chiave API)  
Un solo conto con due regole insieme: lato LONG = Cecchino 29 (Rev 8), lato SHORT = Segugio Short (Rev 9).  
Stesso motore della Rev 9 con il lato long attivo. Max 5 long + 8 short, leva totale 3, mai long e short sulla stessa moneta.  
  
Regola LONG (Cecchino 29): candela 4 ore di BTC in salita di oltre 2 ATR (ATR 14); compra le monete salite di oltre 1,7 ATR  
nella stessa candela, le piu' forti, max 5; stop 1,0 ATR, pareggio a +1 ATR, trailing 1,5 ATR, chiusura dopo 16 ore se  
sotto +3 ATR, oltre +3 ATR trailing 1,5 + 0,10 x (guadagno - 3).  
  
  
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
