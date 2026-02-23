from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from typing import List
from .database import get_session, create_db_and_tables, engine
from .models import Keyword, Channel, ScanLog, KeywordStatus, WordFrequency
from .scanner import scan_keyword
from pydantic import BaseModel
from datetime import datetime
import os

app = FastAPI(title="TKCS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Template setup
templates = Jinja2Templates(directory="backend/templates")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# Pydantic models for API
class KeywordCreate(BaseModel):
    keyword: str

class KeywordUpdate(BaseModel):
    status: KeywordStatus

# --- WEB UI ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: Session = Depends(get_session)):
    total_keywords = session.exec(select(func.count(Keyword.id))).one()
    total_channels = session.exec(select(func.count(Channel.id))).one()
    channels_with_phone = session.exec(select(func.count(Channel.id)).where(Channel.phone_number != None)).one()
    channels_with_location = session.exec(select(func.count(Channel.id)).where(Channel.location != None)).one()
    
    recent_logs = session.exec(select(ScanLog).order_by(ScanLog.created_at.desc()).limit(5)).all()
    
    # Fetch top 10 most frequent words
    top_words = session.exec(select(WordFrequency).order_by(WordFrequency.count.desc()).limit(10)).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": {
            "total_keywords": total_keywords,
            "total_channels": total_channels,
            "channels_with_phone": channels_with_phone,
            "channels_with_location": channels_with_location
        },
        "recent_logs": recent_logs,
        "top_words": top_words
    })

@app.get("/keywords", response_class=HTMLResponse)
async def keywords_page(request: Request, session: Session = Depends(get_session)):
    keywords = session.exec(select(Keyword)).all()
    return templates.TemplateResponse("keywords.html", {"request": request, "keywords": keywords})

@app.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request, session: Session = Depends(get_session)):
    channels = session.exec(select(Channel)).all()
    return templates.TemplateResponse("channels.html", {"request": request, "channels": channels})

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = "", session: Session = Depends(get_session)):
    messages = []
    channels = []
    if q:
        # Search messages
        messages = session.exec(select(Message).where(Message.text.contains(q)).order_by(Message.date.desc()).limit(50)).all()
        # Search channels
        channels = session.exec(select(Channel).where(Channel.channel_name.contains(q) | Channel.description.contains(q)).limit(20)).all()
    
    return templates.TemplateResponse("search.html", {"request": request, "messages": messages, "channels": channels, "query": q})

@app.get("/stats/words", response_class=HTMLResponse)
async def word_stats_page(request: Request, session: Session = Depends(get_session)):
    words = session.exec(select(WordFrequency).order_by(WordFrequency.count.desc()).limit(100)).all()
    return templates.TemplateResponse("word_stats.html", {"request": request, "words": words})

# --- API ENDPOINTS ---
@app.post("/api/keywords", response_model=Keyword)
def create_keyword(keyword_data: KeywordCreate, session: Session = Depends(get_session)):
    db_keyword = Keyword(keyword=keyword_data.keyword)
    session.add(db_keyword)
    session.commit()
    session.refresh(db_keyword)
    return db_keyword

@app.get("/api/keywords", response_model=List[Keyword])
def list_keywords(session: Session = Depends(get_session)):
    return session.exec(select(Keyword)).all()

@app.delete("/api/keywords/{id}")
def delete_keyword(id: int, session: Session = Depends(get_session)):
    keyword = session.get(Keyword, id)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    session.delete(keyword)
    session.commit()
    return {"ok": True}

@app.get("/api/stats/word-frequency")
def api_word_frequency(session: Session = Depends(get_session)):
    return session.exec(select(WordFrequency).order_by(WordFrequency.count.desc()).limit(20)).all()

async def run_scan_process():
    with Session(engine) as session:
        active_keywords = session.exec(select(Keyword).where(Keyword.status == KeywordStatus.ACTIVE)).all()
        for kw in active_keywords:
            await scan_keyword(kw, session)

@app.post("/api/scan/start")
async def start_scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scan_process)
    return {"message": "Scan started"}
