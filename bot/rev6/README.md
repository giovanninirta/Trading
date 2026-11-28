# 🎯 Cecchino
**BTC guida · versione A · Rev 6 · SIMULATO** (nessun ordine reale)

## ➡️ 2.000,00 $   (+0,00 %)

Capitale di partenza 2.000 $ simulati · attivo da 4 giorni · ultimo controllo 2026-11-28 10:37 UTC

| Posizioni aperte | Operazioni chiuse | Vinte | Risultato medio | Scatti di BTC |
|:-:|:-:|:-:|:-:|:-:|
| **0** | **0** | **0 %** | **+0,00 R** | **0** |

**BTC adesso:** ultima candela 4h chiusa alle 2026-11-28 08:00: **-0,2 ATR (serve oltre 2,0)**

---

## Come agisce

**In una frase:** quando Bitcoin fa uno scatto forte verso l'alto, il bot compra per qualche ora le monete che lo hanno seguito con piu' forza, e le rivende quando lo slancio finisce.

**Carattere:** pochi colpi, mirati: entra solo sugli scatti di BTC piu' forti.

### 1 · Aspetta lo scatto di BTC
Ogni 4 ore, alla chiusura della candela (01, 05, 09, 13, 17, 21 ora italiana d'inverno; un'ora dopo d'estate), il bot guarda quanto e' salita BTC.
C'e' uno **scatto** quando BTC chiude la candela da 4 ore **in salita di oltre 2,0 volte il suo ATR**. L'ATR e' l'oscillazione media di BTC nelle ultime 14 candele da 4 ore: la soglia si adatta da sola, piu' alta quando il mercato e' agitato, piu' bassa quando e' calmo. Con i prezzi di oggi (ATR di BTC circa 1.087 $) vuol dire una salita di almeno **2.173 $**, cioe' circa **3,6 %** in 4 ore.
Le candele rosse non contano: il bot compra soltanto (solo long).

### 2 · Sceglie le monete
Guarda 12 monete molto scambiate (spread basso): AAVE, ADA, DOGE, DOT, ETH, LINK, LTC, NEAR, SOL, TRX, UNI, XRP.
Compra quelle che **nella stessa candela sono salite di oltre 1,7 volte il loro ATR**, cioe' che hanno seguito BTC con forza.
Se sono di piu', prende le **5 piu' forti**. Non compra due volte la stessa moneta, non tiene mai piu' di 5 posizioni insieme,
e la somma delle posizioni non supera 3 volte il capitale.
Entra al primo controllo dopo la chiusura (entro 15-20 minuti). Se il controllo arriva oltre 45 minuti dopo, il segnale si salta: entrare tardi non conviene.

### 3 · Quanto compra
Ogni operazione rischia lo **0,75 % del capitale** (15 $ su 2.000 $): e' quanto si perde se il prezzo tocca lo stop iniziale.
La quantita' si calcola cosi': rischio diviso la distanza dello stop. *Esempio:* ETH a 3.000 $ con ATR di 60 $ → stop 1,0 ATR sotto = 2.940 $;
15 $ / 60 $ = 0,25 ETH, cioe' una posizione da circa 750 $.
Il rischio si ricalcola sul capitale del momento (interesse composto).

### 4 · Come esce
| Situazione | Cosa fa lo stop |
|---|---|
| Subito dopo l'ingresso | **1,0 ATR sotto** il prezzo d'ingresso (se lo tocca: −1 R = −0,75 % del capitale) |
| Il prezzo sale di 1,0 ATR | lo stop va al **pareggio** (prezzo d'ingresso): da qui l'operazione non puo' piu' perdere, a parte i costi |
| Il prezzo continua a salire | lo stop **segue il massimo** raggiunto a 1,5 ATR di distanza, e puo' solo salire |
| Passano 16 ore senza superare +3 ATR | **chiude** al prezzo del momento: lo slancio dello scatto e' finito |
| Supera +3 ATR (**fase 2**) | niente piu' limite di tempo; la distanza dello stop si allarga di 0,10 ATR per ogni ATR oltre 3 (es. a +5 ATR: 1,7 ATR) per lasciarla correre |

Lo stop si controlla ogni 15 minuti sulle candele da 15 minuti.

### 5 · Costi simulati
Compra al prezzo di vendita del mercato (*ask*) e vende a quello di acquisto (*bid*): lo spread vero e' pagato.
In piu' 0,07 % di commissione per ordine e il funding dei perpetui (0,01 % ogni 8 ore).

### Cosa aspettarsi (test sul 2022-2026)
circa 2 scatti di BTC al mese, circa 80 operazioni all'anno, rendimento **+26 % all'anno**, calo massimo **-13 %**.
Questi numeri vengono da un'ottimizzazione sugli stessi dati del passato: **dal vivo e' normale che siano piu' bassi**. Questo bot serve a scoprirlo senza rischiare soldi.
I mesi senza scatti di BTC sono normali: il bot resta fermo.


**Come leggere il cruscotto:** R = risultato diviso il rischio (−1 R = stop iniziale pieno; +2 R = guadagno doppio del rischio). Fase 1 = normale; fase 2 = l'operazione corre oltre +3 ATR. Ogni operazione e' nel file [registro.csv](registro.csv).

<details><summary>Note tecniche</summary>

BOT "CECCHINO" (BTC guida, versione A) - Rev 6 - MODALITA' SIMULATA (nessun ordine, nessuna chiave API)  
Rev 6: nome identificativo e spiegazione completa nel cruscotto (regola identica alla Rev 4).  
  
Regola (perpetui Kraken, solo long, candele da 4 ore):  
  SEGNALE    una candela da 4 ore di BTC chiude in salita di oltre 2 ATR (ATR 14 candele)  
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
</details>
