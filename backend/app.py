from datetime import datetime
from os import getenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from kiwoom import KiwoomClient

app=FastAPI(title='Stock Radar Live API')
app.add_middleware(CORSMiddleware,allow_origins=[x for x in getenv('ALLOWED_ORIGINS','').split(',') if x],allow_methods=['GET'],allow_headers=['*'])
client=KiwoomClient()

@app.get('/health')
def health(): return {'ok':True,'provider':'kiwoom','configured':client.configured}

@app.get('/api/market')
def market():
    if not client.configured: raise HTTPException(503,'Kiwoom API keys are not configured')
    return client.market_indices()

@app.get('/api/investors')
def investors():
    if not client.configured: raise HTTPException(503,'Kiwoom API keys are not configured')
    return client.investor_rankings()
