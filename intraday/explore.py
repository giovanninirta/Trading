import numpy as np,pandas as pd
from backtest import *
D=load();sp=split(D["BTCUSDT"].index);a,b=sp["TRAIN"];COST=2*(FEE+SLIP);H=12
rows=[]
for s,df in D.items():
    f=feats(df,D["BTCUSDT"]);fw=(df.c.shift(-H)/df.o.shift(-1)-1);same=(f.day==f.day.shift(-H-1))
    f["fw"]=fw.where(same);f["sym"]=s;rows.append(f[(f.index>=a)&(f.index<b)].dropna(subset=["fw","vol","r12","dvw"]))
X=pd.concat(rows);X["yr"]=X.index.year;X["sess"]=pd.cut(X.hour,[-1,6,12,21,24],labels=["Asia","EU","US","late"])
X["dhd"]=(X.index.map(lambda t:0)) if False else 0
def bins(name,col,q=None,cats=None):
    k=pd.qcut(X[col],q,duplicates="drop") if q else X[col]
    for v,g in X.groupby(k,observed=True):
        yield f"{name}={v}",g
P=[]
for nm,col,q in [("hour","hour",None),("dow","dow",None),("sess","sess",None),("r12","r12",8),("r36","r36",8),("vr","vr",8),("dvw","dvw",8),("gap","gap",8),("btclead","bl",8)]:
    for n,g in bins(nm,col,q):
        if len(g)<3000:continue
        m=g.fw.mean();d=np.sign(m);net=d*m-COST
        ys=g.groupby("yr").fw.mean();stab=(np.sign(ys)==d).mean()
        P.append((n,int(d),net*1e4,len(g),stab,m/(g.fw.std()/np.sqrt(len(g)/H))))
P=pd.DataFrame(P,columns=["pattern","dir","net_bp","n","stab","t"]).sort_values("net_bp",ascending=False)
print(f"cost={COST*1e4:.0f}bp/trade, horizon 1h; top10 by net edge (bp):");print(P.head(10).to_string(index=False,float_format=lambda x:f"{x:.2f}"))
