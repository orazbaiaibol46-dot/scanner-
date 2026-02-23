import re
import asyncio
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel as TelethonChannel
from .models import Channel, Keyword, ScanLog, WordFrequency, Message
from sqlmodel import Session, select
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Extraction Logic
PHONE_REGEX = r'(\+?\d[\d\s\-\(\)]{7,15})'
KAZAKHSTAN_CITIES = [
    "Almaty", "Astana", "Shymkent", "Karaganda", "Aktobe", "Taraz", "Pavlodar", "Ust-Kamenogorsk", "Semey", "Atyrau", "Kostanay", "Kyzylorda", "Uralsk", "Petropavl", "Aktau", "Temirtau", "Turkistan", "Kokshetau", "Zhanaozen", "Ekibastuz", "Taldykorgan",
    "Алматы", "Астана", "Шымкент", "Караганда", "Актобе", "Тараз", "Павлодар", "Өскемен", "Семей", "Атырау", "Қостанай", "Қызылорда", "Орал", "Петропавл", "Ақтау", "Теміртау", "Түркістан", "Көкшетау", "Жаңаөзен", "Екібастұз", "Талдықорған"
]

def extract_phone(text):
    if not text: return None
    match = re.search(PHONE_REGEX, text)
    return match.group(0) if match else None

def extract_location(text):
    if not text: return None
    for city in KAZAKHSTAN_CITIES:
        if city.lower() in text.lower():
            return city
    return None

def clean_text(text):
    # Remove punctuation and lowercase
    text = re.sub(r'[^\w\s]', '', text.lower())
    # Split into words and filter by length
    words = [w for w in text.split() if len(w) > 3]
    return words

async def update_word_frequency(keyword_id: int, text: str, session: Session):
    words = clean_text(text)
    for word in words:
        statement = select(WordFrequency).where(WordFrequency.keyword_id == keyword_id, WordFrequency.word == word)
        existing = session.exec(statement).first()
        if existing:
            existing.count += 1
            existing.updated_at = datetime.utcnow()
            session.add(existing)
        else:
            new_freq = WordFrequency(keyword_id=keyword_id, word=word, count=1)
            session.add(new_freq)

async def scan_keyword(keyword: Keyword, session: Session):
    api_id = int(os.getenv("API_ID"))
    api_hash = os.getenv("API_HASH")
    data_dir = os.getenv("DATA_DIR", ".")
    session_name = os.path.join(data_dir, 'scanner_session')
    
    # Use a shared session file for all keywords
    client = TelegramClient(session_name, api_id, api_hash)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            # If not authorized, we record a log but in real world we'd need a way to login
            log = ScanLog(keyword_id=keyword.id, status="error", message="Telegram client not authorized")
            session.add(log)
            session.commit()
            return

        result = await client(SearchRequest(
            q=keyword.keyword,
            limit=50
        ))

        found_count = 0
        for chat in result.chats:
            if isinstance(chat, TelethonChannel):
                # Check if already exists
                statement = select(Channel).where(Channel.telegram_id == chat.id)
                existing = session.exec(statement).first()
                
                full_chat = await client.get_entity(chat)
                description = getattr(full_chat, 'about', '') or ""
                title = chat.title or ""
                
                # Extract from both title and description
                search_text = f"{title}\n{description}"
                location = extract_location(search_text)
                phone = extract_phone(search_text)
                
                if not existing:
                    new_channel = Channel(
                        keyword_id=keyword.id,
                        telegram_id=chat.id,
                        channel_name=chat.title,
                        username=chat.username,
                        description=description,
                        location=location,
                        phone_number=phone,
                        subscribers_count=chat.participants_count or 0,
                        channel_url=f"https://t.me/{chat.username}" if chat.username else f"https://t.me/c/{chat.id}/1"
                    )
                    session.add(new_channel)
                    found_count += 1
                else:
                    existing.subscribers_count = chat.participants_count or 0
                    existing.description = description
                    existing.location = location
                    existing.phone_number = phone
                    existing.scanned_at = datetime.utcnow()
                    session.add(existing)

                # Word Frequency Analysis: get last 50 messages
                try:
                    async for message in client.iter_messages(chat, limit=50):
                        if message.text:
                            # Save message to database
                            msg_stmt = select(Message).where(Message.channel_id == (existing.id if existing else None), Message.telegram_id == message.id)
                            # Note: if existing is None, we need the new_channel.id, but it's not committed yet.
                            # So we need to commit the channel first if it's new.
                            
                            if not existing:
                                session.commit()
                                session.refresh(new_channel)
                                channel_id = new_channel.id
                                existing = new_channel # set existing to new_channel to avoid re-committing
                            else:
                                channel_id = existing.id

                            msg_stmt = select(Message).where(Message.channel_id == channel_id, Message.telegram_id == message.id)
                            existing_msg = session.exec(msg_stmt).first()
                            
                            if not existing_msg:
                                new_msg = Message(
                                    channel_id=channel_id,
                                    telegram_id=message.id,
                                    text=message.text,
                                    date=message.date
                                )
                                session.add(new_msg)

                            await update_word_frequency(keyword.id, message.text, session)
                except Exception as msg_e:
                    print(f"Error fetching messages for {chat.id}: {msg_e}")

        log = ScanLog(keyword_id=keyword.id, status="success", message=f"Found {found_count} new channels")
        session.add(log)
        session.commit()

    except Exception as e:
        log = ScanLog(keyword_id=keyword.id, status="error", message=str(e))
        session.add(log)
        session.commit()
    finally:
        await client.disconnect()
