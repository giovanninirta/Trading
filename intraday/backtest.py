import numpy as np,pandas as pd
SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","ADAUSDT"]
FEE=0.0005   # Kraken Futures perp taker 0.05% per side (maker 0.02%)
SLIP=0.0002  # slippage per side
def load():
    D={s:pd.read_parquet(f"data/{s}.parquet").astype("float64") for s in SYMS}
    return D
def split(idx):
    d=np.array(sorted(set(idx.normalize())));n=len(d)
    return {"TRAIN":(d[0],d[int(n*.6)]),"VALID":(d[int(n*.6)],d[int(n*.8)]),"TEST":(d[int(n*.8)],d[-1]+pd.Timedelta(days=1))}
def feats(df,btc=None):
    c=df.c;r=c.pct_change();f=pd.DataFrame(index=df.index)
    f["day"]=df.index.normalize();f["hour"]=df.index.hour;f["dow"]=df.index.dayofweek
    f["vol"]=r.rolling(288).std();f["atr"]=(df.h-df.l).rolling(48).mean()/c
    for k in (6,12,36):f[f"r{k}"]=c.pct_change(k)/(f.vol*np.sqrt(k))
    f["vr"]=df.v/df.v.rolling(288).mean()
    g=df.groupby(f.day);dh=g.h.max().shift(1);dl=g.l.min().shift(1);dc=g.c.last().shift(1)
    f["dh"]=f.day.map(dh);f["dl"]=f.day.map(dl);f["dc"]=f.day.map(dc)
    tp=(df.h+df.l+df.c)/3*df.v;f["vwap"]=tp.groupby(f.day).cumsum()/df.v.groupby(f.day).cumsum()
    f["dvw"]=(c/f.vwap-1)/f.vol/np.sqrt(12)
    f["gap"]=(c/f.dc-1)/f.vol/np.sqrt(100)
    if btc is not None:f["bl"]=btc.c.pct_change(6)/(btc.c.pct_change().rolling(288).std()*np.sqrt(6))
    return f
def run(D,sig,sl=1.5,tp=3.0,hold=24,cap=10,fee=FEE,slip=SLIP,lo=None,hi=None):
    """sig: dict sym->Series(+1/-1/0) at bar close; entry next bar open. sl/tp in ATR units; returns trades DataFrame"""
    T=[]
    for s,df in D.items():
        sg=sig[s];sg=sg.reindex(df.index).fillna(0).values;o,h,l,c=df.o.values,df.h.values,df.l.values,df.c.values
        day=np.asarray((df.index.normalize()-pd.Timestamp("1970-01-01")).days)
        atr=((df.h-df.l).rolling(48).mean()).values
        ts=df.index
        idx=np.nonzero(sg)[0];free=0;cnt={}
        for i in idx:
            if i<free or i+2>=len(df) or day[i+1]!=day[i]:continue
            t=ts[i]
            if lo is not None and not(lo<=t<hi):continue
            if cnt.get(day[i],0)>=cap or np.isnan(atr[i]):continue
            d=sg[i];e=o[i+1]*(1+d*slip);a=atr[i];slp=e-d*sl*a;tpp=e+d*tp*a;x=None
            for j in range(i+1,min(i+1+hold,len(df))):
                if day[j]!=day[i]:break
                last=j
                if d>0:
                    if l[j]<=slp:x=slp;break
                    if h[j]>=tpp:x=tpp;break
                else:
                    if h[j]>=slp:x=slp;break
                    if l[j]<=tpp:x=tpp;break
            if x is None:x=c[last]
            x=x*(1-d*slip);pnl=d*(x/e-1)-2*fee
            T.append((ts[i+1],s,d,pnl));free=last+1;cnt[day[i]]=cnt.get(day[i],0)+1
    return pd.DataFrame(T,columns=["t","s","d","pnl"]).sort_values("t").reset_index(drop=True)
def stats(T,w=0.2,days=None):
    if len(T)==0:return dict(n=0,pf=0,pos=0,dd=1,ret=-1,tpd=0)
    dr=(T.pnl*w).groupby(T.t.dt.normalize()).sum()
    if days is not None:dr=dr.reindex(days,fill_value=0)
    eq=(1+dr).cumprod();dd=(1-eq/eq.cummax()).max()
    g=T.pnl[T.pnl>0].sum();b=-T.pnl[T.pnl<0].sum()
    act=(dr!=0)
    return dict(n=len(T),pf=g/b if b>0 else 9,pos=(dr[act]>0).mean(),dd=dd,ret=eq.iloc[-1]-1,tpd=len(T)/max(act.sum(),1))
def fmt(n,s):return f"{n:<28}n={s['n']:>5} tpd={s['tpd']:.1f} PF={s['pf']:.2f} pos={s['pos']:.0%} DD={s['dd']:.0%} ret={s['ret']:+.0%}"
