from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from analysis import run_analysis

Path('outputs').mkdir(exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

app.mount('/outputs', StaticFiles(directory='outputs'), name='outputs')

class AnalysisRequest(BaseModel):
    city: str
    state: str
    zipcode: str

@app.get('/health')
def health():
    return {'ok': True}

@app.post('/analyze')
def analyze(payload: AnalysisRequest):
    result = run_analysis(payload.city, payload.state, payload.zipcode)
    if result is None:
        raise HTTPException(status_code=404, detail='No listings found')
    return result