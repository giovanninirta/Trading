import io,zipfile,requests,pandas as pd
S=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","ADAUSDT"]
for s in S:
    fr=[]
    for m in pd.period_range("2024-10","2026-10",freq="M"):
        r=requests.get(f"https://data.binance.vision/data/spot/monthly/klines/{s}/5m/{s}-5m-{m}.zip",timeout=60)
        if r.status_code!=200: continue
        z=zipfile.ZipFile(io.BytesIO(r.content))
        fr.append(pd.read_csv(z.open(z.namelist()[0]),header=None,usecols=[0,1,2,3,4,5]))
    if not fr: print(s,"nodata");continue
    d=pd.concat(fr);d.columns=["t","o","h","l","c","v"]
    t=d.t.astype("int64");d["t"]=pd.to_datetime(t.where(t<10**14,t//1000),unit="ms")
    d=d.drop_duplicates("t").set_index("t").astype("float32");d.to_parquet(f"data/{s}.parquet");print(s,len(d),d.index.min(),d.index.max())
