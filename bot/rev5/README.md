# Bot BTC guida · Rev 5 · versione B (scatto BTC oltre +1,25 %) · SIMULATO

## ➡️ 2.000,00 $   (+0,00 %)

Capitale di partenza 2.000 $ simulati · attivo da 0 giorni · ultimo controllo 2026-11-24 22:35 UTC

| Posizioni aperte | Operazioni chiuse | Vinte | Risultato medio | Scatti di BTC |
|:-:|:-:|:-:|:-:|:-:|
| **0** | **0** | **0 %** | **+0,00 R** | **0** |

**BTC adesso:** ultima candela 4h chiusa alle 2026-11-24 20:00: **-0,09 % (serve oltre 1,25 %)**

<details><summary>Come funziona e come leggere</summary>

BOT "BTC GUIDA" - Rev 5 (versione B) - MODALITA' SIMULATA (nessun ordine, nessuna chiave API)  
  
Regola (perpetui Kraken, solo long, candele da 4 ore):  
  SEGNALE    una candela da 4 ore di BTC chiude in salita di oltre l'1,25 %  
  COSA COMPRA le monete liquide salite di oltre 1,7 ATR nella stessa candela (al massimo 5, le piu' forti),  
             subito dopo la chiusura della candela (se il controllo arriva oltre 45 minuti dopo, il segnale si salta)  
  STOP       1,0 ATR sotto l'ingresso; a pareggio quando il prezzo sale di 1 ATR; poi segue il massimo a 1,5 ATR  
  FASE 1     se dopo 16 ore dalla chiusura del segnale la posizione non ha superato +3 ATR, si chiude  
  FASE 2     sopra +3 ATR: niente limite di tempo, lo stop segue il massimo a 1,5 + 0,10 x (guadagno - 3) ATR  
  RISCHIO    0,75 % del capitale per operazione (se scatta lo stop iniziale si perde lo 0,75 %);  
             al massimo 5 posizioni aperte e posizioni totali al massimo 3 volte il capitale  
Costi simulati: acquisto al prezzo "ask", vendita al "bid" (spread vero), 0,07 % di commissione per ordine,  
funding 0,01 % ogni 8 ore. Lo stop si controlla sulle candele da 15 minuti, come nel test.  
  
Gira ogni 15 minuti su GitHub. File aggiornati:  
  stato.json    memoria del bot      registro.csv  operazioni simulate      README.md  cruscotto

**R** = risultato diviso il rischio: −1 R = stop iniziale pieno (−0,75 % del capitale); +2 R = guadagno doppio del rischio.  
Ogni operazione è anche nel file [registro.csv](registro.csv).
</details>
