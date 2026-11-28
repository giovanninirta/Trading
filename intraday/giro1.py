import itertools,numpy as np,pandas as pd
from backtest import *
D=load();sp=split(D["BTCUSDT"].index);F={s:feats(D[s],D["BTCUSDT"]) for s in D}
days={k:pd.date_range(*v,inclusive="left") for k,v in sp.items()}
def mk(name,z,vr=1.5):
    S={}
    for s,f in F.items():
        if name=="dip":sg=((f.r12<-z)&(f.vr>vr)).astype(int)
        elif name=="vwap":sg=((f.dvw<-z).astype(int)-(f.dvw>z).astype(int))
        elif name=="brk":sg=((f.c_>f.dh)&(f.vr>vr)).astype(int) if False else ((D[s].c>f.dh)&(D[s].c.shift(1)<=f.dh)&(f.vr>vr)).astype(int)
        elif name=="lead":
            sg=pd.Series(0,f.index) if s=="BTCUSDT" else ((f.bl>z).astype(int)-(f.bl<-z).astype(int))*((f.r6.abs()<0.5)).astype(int)
        S[s]=sg
    return S
R=[]
for name,zs,hs in [("dip",[3,3.5,4],[36,72]),("vwap",[5,6,7],[36,72]),("brk",[1,2,3],[72,144]),("lead",[1.5,2,2.5],[72,144])]:
    for z,h in itertools.product(zs,hs):
        for sl,tp in [(2,4),(3,6)]:
            S=mk(name,z,2 if name=="brk" else 1.5)
            tr=run(D,S,sl,tp,h,lo=sp["TRAIN"][0],hi=sp["TRAIN"][1]);va=run(D,S,sl,tp,h,lo=sp["VALID"][0],hi=sp["VALID"][1])
            R.append((name,z,h,sl,tp,stats(tr,days=days["TRAIN"]),stats(va,days=days["VALID"])))
R.sort(key=lambda r:-r[5]["pf"] if r[5]["n"]>150 else 0)
for r in R[:8]:print(fmt(f"{r[0]} z{r[1]} h{r[2]} {r[3]}/{r[4]} TR",r[5]));print(fmt("   VALID",r[6]))
