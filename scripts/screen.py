from __future__ import annotations
import json, math, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from pykrx import stock
from tenacity import retry, stop_after_attempt, wait_exponential

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'/'data'/'results.json'
CHECKPOINT=ROOT/'checkpoint.json'
KST=pd.Timestamp.now(tz='Asia/Seoul')

def clean_number(v):
    v=float(v)
    return None if math.isnan(v) or math.isinf(v) else round(v,4)

def rsi(close, period=14):
    delta=close.diff(); gain=delta.clip(lower=0).rolling(period).mean(); loss=(-delta.clip(upper=0)).rolling(period).mean()
    return 100-(100/(1+gain/loss.replace(0,np.nan)))

@retry(stop=stop_after_attempt(4),wait=wait_exponential(min=2,max=20))
def fetch(ticker,start,end):
    df=stock.get_market_ohlcv_by_date(start,end,ticker)
    if len(df)<65: raise ValueError('insufficient history')
    return df

def analyze(ticker,name,market,start,end,cfg):
    try:
        df=fetch(ticker,start,end).rename(columns={'종가':'close','거래량':'volume','거래대금':'value'})
        c=df.close.astype(float); v=df.volume.astype(float); value=df.value.astype(float)
        ma5=c.rolling(5).mean();ma20=c.rolling(20).mean();ma60=c.rolling(60).mean();rv=v/v.rolling(20).mean();rs=rsi(c);disp=c/ma20*100
        pts=cfg['scoring']; matched=[]
        def hit(ok,key,label):
            if bool(ok): matched.append({'key':key,'label':label,'points':pts[key]})
        hit(ma5.iloc[-1]>ma20.iloc[-1]>ma60.iloc[-1],'ma_alignment','정배열')
        hit(ma20.iloc[-1]>ma20.iloc[-3],'ma20_rising','MA20 상승')
        hit(ma60.iloc[-1]>ma60.iloc[-3],'ma60_rising','MA60 상승')
        hit(35<=rs.iloc[-1]<=50,'rsi_35_50','RSI 35~50')
        hit(rs.iloc[-1]>rs.iloc[-2]<=rs.iloc[-3],'rsi_turn_up','RSI 상승전환')
        hit(disp.iloc[-1]>disp.iloc[-2] and disp.iloc[-2]<=disp.iloc[-3],'disparity_rebound','이격도 반등')
        hit(rv.iloc[-1]>=2,'rvol_2x','RVOL≥2')
        hit(value.iloc[-1]>value.iloc[-2],'trading_value_increase','거래대금 증가')
        change=(c.iloc[-1]/c.iloc[-2]-1)*100
        return {'code':ticker,'name':name,'market':market,'score':sum(x['points'] for x in matched),'matched':matched,'close':clean_number(c.iloc[-1]),'change_pct':clean_number(change),'rsi':clean_number(rs.iloc[-1]),'rvol':clean_number(rv.iloc[-1])}
    except Exception as e:
        return {'code':ticker,'name':name,'market':market,'error':str(e)[:120]}

def main():
    cfg=yaml.safe_load((ROOT/'config.yml').read_text(encoding='utf-8'))
    end=KST.strftime('%Y%m%d');start=(KST-timedelta(days=cfg.get('history_days',90)*2)).strftime('%Y%m%d')
    universe=[]
    for market in cfg['markets']:
        for ticker in stock.get_market_ticker_list(end,market=market): universe.append((ticker,stock.get_market_ticker_name(ticker),market))
    results=[];errors=[]
    with ThreadPoolExecutor(max_workers=cfg.get('workers',5)) as pool:
        futures={pool.submit(analyze,*item,start,end,cfg):item for item in universe}
        for i,f in enumerate(as_completed(futures),1):
            row=f.result(); (errors if 'error' in row else results).append(row)
            if i%100==0: CHECKPOINT.write_text(json.dumps({'completed':i,'total':len(universe),'at':datetime.now().isoformat()},ensure_ascii=False),encoding='utf-8')
            time.sleep(.03)
    results.sort(key=lambda x:(-x['score'],-(x.get('change_pct') or -999)))
    payload={'status':'ok' if len(results)>=len(universe)*.85 else 'partial','generated_at':datetime.now().astimezone().isoformat(),'base_date':end,'scanned_count':len(universe),'successful_count':len(results),'error_count':len(errors),'stocks':results,'errors':errors[:50]}
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(OUT)
    if CHECKPOINT.exists(): CHECKPOINT.unlink()
    print(json.dumps({k:payload[k] for k in ['status','scanned_count','successful_count','error_count']},ensure_ascii=False))

if __name__=='__main__': main()
