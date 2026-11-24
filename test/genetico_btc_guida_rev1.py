#!/usr/bin/env python3
"""
ALGORITMO GENETICO "BTC GUIDA" - Rev 1  (perpetui Kraken, solo long, 30 monete)
Regola di base: BTC fa una candela forte al rialzo -> si comprano le monete scelte in base a come si sono
mosse nella stessa candela, si esce dopo un certo numero di candele (o allo stop / all'obiettivo).

Geni (parametri che l'algoritmo fa evolvere):
  ore        durata della candela: 1, 2, 4, 6, 8, 12 ore
  btc        forza minima della candela di BTC, in ATR (1,0 - 3,5)
  tipo       "partite" = monete salite almeno quanto la soglia, "ritardo" = monete salite al massimo la soglia
  soglia     movimento della moneta nella stessa candela, in ATR (-1,0 - 3,0)
  tenuta     candele di permanenza (1 - 12)
  stop       distanza dello stop in ATR (0,75 - 3,0)
  obiettivo  uscita anticipata a +X R (nessuno, 1, 1,5, 2, 3)
  filtro     compra solo se BTC e' sopra la media di 200 candele (si/no)
Ingresso alla chiusura della candela del segnale + 0,10 % di costo per il ritardo di qualche minuto;
costi 0,07 % per ordine + funding 0,01 % ogni 8 ore.

Contro l'eccesso di adattamento:
  - l'algoritmo vede SOLO la prova (primo 60 % del periodo); la verifica (ultimo 40 %) si guarda alla fine
  - il voto non e' il guadagno ma la COSTANZA: media del risultato per scatto di BTC diviso la sua
    dispersione, per la radice del numero di scatti (le monete dello stesso scatto contano come uno)
  - servono almeno 40 scatti in prova
  - per ogni scatto si comprano al massimo 5 monete (le piu' forti o le piu' indietro, secondo il tipo):
    e il voto si calcola solo sulle operazioni che il portafoglio riesce davvero a prendere
    (con 5 posti e leva massima 3, quando i posti sono pieni il segnale si salta)
  - due corse con semi diversi: se arrivano a soluzioni simili, la soluzione e' piu' credibile
  - per la migliore: prova dei parametri vicini (ogni gene di un passo in piu' e in meno)

Uso (nella cartella dati):  python ../genetico_btc_guida_rev1.py
Solo libreria standard Python 3.8+.
"""
import math, os, random, sys, time, calendar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from misuratore_ritest_rev1 import carica, atr, MONETE, COSTO, FUNDING_ORA

GENI = {
    "ore":       [1, 2, 4, 6, 8, 12],
    "btc":       [1.0 + 0.25 * k for k in range(11)],
    "tipo":      ["partite", "ritardo"],
    "soglia":    [-1.0 + 0.25 * k for k in range(17)],
    "tenuta":    list(range(1, 13)),
    "stop":      [0.75 + 0.25 * k for k in range(10)],
    "obiettivo": [None, 1.0, 1.5, 2.0, 3.0],
    "filtro":    [False, True],
}
RITARDO = 0.001
MIN_SCATTI = 40
POP, GENERAZIONI, ELITE = 60, 30, 4
MAX_POS = 5

def aggrega(barre, ore):
    out, g = [], []
    for b in barre:
        if g and g[0][0] // (ore * 3600) != b[0] // (ore * 3600):
            out.append((g[0][0], g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4])); g = []
        g.append(b)
    return out

class Dati:
    def __init__(self):
        uno = {m: carica(m, 1) for m in MONETE}
        self.uno = {m: b for m, b in uno.items() if b and len(b) > 5000}
        self.cache = {}
        b = self.uno["XBT"]
        self.t0, self.t1 = b[0][0], b[-1][0]
        self.taglio = self.t0 + (self.t1 - self.t0) * 0.6

    def serie(self, ore):
        if ore not in self.cache:
            s = {}
            for m, b in self.uno.items():
                bb = b if ore == 1 else aggrega(b, ore)
                T = [x[0] for x in bb]; H = [x[2] for x in bb]; L = [x[3] for x in bb]; C = [x[4] for x in bb]
                A = atr(H, L, C)
                m200 = [None] * len(C); acc = 0.0
                for i in range(len(C)):
                    acc += C[i]
                    if i >= 200: acc -= C[i - 200]
                    if i >= 199: m200[i] = acc / 200
                s[m] = (T, H, L, C, A, m200, {t: i for i, t in enumerate(T)})
            self.cache[ore] = s
        return self.cache[ore]

def operazioni(D, g):
    """Lista di operazioni (inizio, fine, moneta, z, rischio %, R)."""
    S = D.serie(g["ore"]); ore = g["ore"]
    Tb, Hb, Lb, Cb, Ab, Mb, _ = S["XBT"]
    ops = []
    for i in range(200, len(Cb) - 1):
        if not Ab[i - 1] or (Cb[i] - Cb[i - 1]) / Ab[i - 1] <= g["btc"]: continue
        if g["filtro"] and not (Mb[i] and Cb[i] > Mb[i]): continue
        t = Tb[i]; scatto = []
        for m, (T, H, L, C, A, _, idx) in S.items():
            if m == "XBT": continue
            j = idx.get(t)
            if j is None or j < 30 or j >= len(C) - 1 or not A[j - 1] or H[j] == L[j]: continue
            z = (C[j] - C[j - 1]) / A[j - 1]
            if (g["tipo"] == "partite" and z < g["soglia"]) or (g["tipo"] == "ritardo" and z > g["soglia"]): continue
            e = C[j]; rischio = g["stop"] * A[j]; pct = rischio / e
            if pct < 0.002 or pct > 0.15: continue
            stop = e - rischio; tp = e + g["obiettivo"] * rischio if g["obiettivo"] else None
            r = None; k = j
            while k < min(j + g["tenuta"], len(C) - 1):
                k += 1
                if L[k] <= stop: r = -1.0; break
                if tp and H[k] >= tp: r = g["obiettivo"]; break
            if r is None: r = (C[k] - e) / rischio
            r -= (2 * COSTO + RITARDO + FUNDING_ORA * ore * (k - j)) / pct
            scatto.append((T[j] + ore * 3600, T[k] + ore * 3600, m, z, pct, r))
        # si prendono al massimo MAX_POS monete per scatto: le piu' forti (partite) o le piu' indietro (ritardo)
        scatto.sort(key=lambda o: -o[3] if g["tipo"] == "partite" else o[3])
        ops += scatto[:MAX_POS]
    return ops

def voto(ops, D, periodo):
    """Costanza per scatto di BTC nel periodo ('prova' o 'verifica')."""
    scatti = {}
    for o in ops:
        if (o[0] < D.taglio) == (periodo == "prova"): scatti.setdefault(o[0], []).append(o[5])
    v = [sum(x) / len(x) for x in scatti.values()]
    if len(v) < (MIN_SCATTI if periodo == "prova" else 10): return -9.0, len(v), 0.0
    mu = sum(v) / len(v); sd = math.sqrt(sum((x - mu) ** 2 for x in v) / len(v)) or 1e-9
    return mu / sd * math.sqrt(len(v)), len(v), mu

def prese(ops, max_pos=MAX_POS, leva=3.0, rischio=0.5):
    """Operazioni che il portafoglio riesce davvero a prendere (posti liberi e leva)."""
    return portafoglio(ops, rischio, max_pos, leva)[3]

def portafoglio(ops, rischio=0.5, max_pos=MAX_POS, leva=3.0):
    cap, picco, calo = 1.0, 1.0, 0.0
    aperte, curva, fatte = [], [], []
    for o in sorted(ops):
        for p in sorted(p for p in aperte if p[0] <= o[0]):
            cap += p[1] * p[3]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p[0], cap))
        aperte = [p for p in aperte if p[0] > o[0]]
        importo = cap * rischio / 100; noz = importo / o[4]
        if len(aperte) >= max_pos or sum(p[2] for p in aperte) + noz > leva * cap: continue
        aperte.append((o[1], importo, noz, o[5])); fatte.append(o)
    for p in sorted(aperte):
        cap += p[1] * p[3]; picco = max(picco, cap); calo = min(calo, cap / picco - 1); curva.append((p[0], cap))
    return cap, calo, curva, fatte

def casuale(rng): return {k: rng.choice(v) for k, v in GENI.items()}
def chiave(g): return tuple(g[k] for k in GENI)

def evolvi(D, seme, memo):
    rng = random.Random(seme)
    def valuta(g):
        c = chiave(g)
        if c not in memo: memo[c] = voto(prese(operazioni(D, g)), D, "prova")[0]
        return memo[c]
    pop = [casuale(rng) for _ in range(POP)]
    for gen in range(GENERAZIONI):
        pop.sort(key=valuta, reverse=True)
        if gen % 10 == 0 or gen == GENERAZIONI - 1:
            print(f"   seme {seme}  generazione {gen + 1:>2}: miglior voto in prova {valuta(pop[0]):+.2f}", flush=True)
        nuova = [dict(x) for x in pop[:ELITE]]
        while len(nuova) < POP:
            a = max(rng.sample(pop, 3), key=valuta); b = max(rng.sample(pop, 3), key=valuta)
            figlio = {k: (a[k] if rng.random() < 0.5 else b[k]) for k in GENI}
            for k, valori in GENI.items():
                if rng.random() < 0.15:
                    i = valori.index(figlio[k])
                    figlio[k] = valori[max(0, min(len(valori) - 1, i + rng.choice((-2, -1, 1, 2))))] if rng.random() < 0.7 else rng.choice(valori)
            nuova.append(figlio)
        pop = nuova
    pop.sort(key=valuta, reverse=True)
    return pop

def descrivi(g):
    tipo = f"moneta {'>=' if g['tipo'] == 'partite' else '<='} {g['soglia']:+.2f} ATR"
    ob = f"obiettivo {g['obiettivo']:.1f}R" if g["obiettivo"] else "senza obiettivo"
    return (f"{g['ore']:>2}h | BTC > {g['btc']:.2f} ATR | {tipo} | {g['tenuta']:>2} candele | stop {g['stop']:.2f} ATR | "
            f"{ob} | {'solo BTC sopra media 200' if g['filtro'] else 'sempre'}").replace(".", ",")

def scheda(D, g, anni, durata):
    ops = operazioni(D, g)
    cap, calo, curva, fatte = portafoglio(ops)
    vp, np_, mp = voto(fatte, D, "prova"); vv, nv, mv = voto(fatte, D, "verifica")
    def valore(t):
        v = 1.0
        for tt, c in curva:
            if tt <= t: v = c
            else: break
        return v
    celle = "".join(f"{(valore(calendar.timegm((a + 1, 1, 1, 0, 0, 0))) / valore(calendar.timegm((a, 1, 1, 0, 0, 0))) - 1) * 100:>+6.0f}%" for a in anni)
    annuo = cap ** (1 / durata) - 1 if cap > 0 else -1
    verde = "🟢" if vp > 2 and vv > 1.5 and mv > 0.05 else ("🟡" if mp > 0 and mv > 0 else "🔴")
    return verde, f"{vp:>+6.1f}{vv:>+7.1f}{mp:>+8.2f}{mv:>+8.2f}{(np_ + nv) / durata:>8.0f}{annuo * 100:>+7.0f}%{calo * 100:>+7.0f}%{celle}", mv

def main():
    D = Dati()
    anni = list(range(time.gmtime(D.t0).tm_year, time.gmtime(D.t1).tm_year + 1))
    durata = (D.t1 - D.t0) / (365 * 86400)
    d = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))
    print(f"\n{len(D.uno)} monete, dal {d(D.t0)} al {d(D.t1)}. L'algoritmo vede solo la prova (fino al {d(D.taglio)}).\n")
    memo, finali = {}, []
    for seme in (1, 2):
        pop = evolvi(D, seme, memo)
        finali += pop
    print(f"   combinazioni provate: {len(memo)}\n")
    # le 10 migliori diverse tra loro (per voto in prova)
    viste, migliori = set(), []
    for g in sorted(finali, key=lambda g: memo[chiave(g)], reverse=True):
        if chiave(g) in viste: continue
        viste.add(chiave(g)); migliori.append(g)
        if len(migliori) == 10: break
    testa = (f"   {'Voto prova':>8}{'verif.':>7}{'R prova':>8}{'R verif':>8}{'Scatti/a':>8}{'Annuo':>8}{'Calo':>8}"
             + "".join(f"{a:>7}" for a in anni))
    print("LE 10 MIGLIORI COMBINAZIONI (scelte guardando solo la prova)")
    print("Annuo, calo e anni: portafoglio con rischio 0,5 % per operazione, massimo 5 posizioni, interesse composto.\n")
    print(testa)
    for n, g in enumerate(migliori, 1):
        s, riga, _ = scheda(D, g, anni, durata)
        print(f"{n:>2}. {descrivi(g)}")
        print(f"{s} {riga}")

    # robustezza della prima
    g0 = migliori[0]
    print(f"\nPARAMETRI VICINI ALLA MIGLIORE (ogni gene un passo in piu' e in meno)")
    print(f"   {'Cambio':28}{'Voto prova':>11}{'Voto verif.':>12}{'R verif':>9}")
    for k, valori in GENI.items():
        i = valori.index(g0[k])
        for j in (i - 1, i + 1):
            if not 0 <= j < len(valori): continue
            g = dict(g0); g[k] = valori[j]
            ops = prese(operazioni(D, g))
            vp, _, _ = voto(ops, D, "prova"); vv, _, mv = voto(ops, D, "verifica")
            val = valori[j] if valori[j] is not None else "nessuno"
            print(f"   {k + ' = ' + str(val):28}{vp:>+11.1f}{vv:>+12.1f}{mv:>+9.2f}")
    print("""
Voto: costanza del risultato per scatto di BTC (sopra +2 = netto, sotto +1 = probabilmente fortuna).
R: risultato medio per scatto, in multipli del rischio, costi inclusi.   Scatti/a: scatti di BTC all'anno.
🟢 voto netto in prova E in verifica   🟡 positivo in entrambi ma non netto   🔴 negativo in verifica
Se le prime 10 sono tutte simili tra loro e i parametri vicini restano positivi, la regola e' robusta.
Se sono tutte diverse e i vicini crollano, l'algoritmo ha trovato solo coincidenze del passato.""")

if __name__ == "__main__":
    main()
