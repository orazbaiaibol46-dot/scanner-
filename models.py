from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime
from enum import Enum

class KeywordStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class Keyword(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    keyword: str = Field(index=True, unique=True)
    status: KeywordStatus = Field(default=KeywordStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    channels: List["Channel"] = Relationship(back_populates="keyword_ref")

class Channel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    keyword_id: int = Field(foreign_key="keyword.id")
    telegram_id: int = Field(index=True)
    channel_name: str
    username: Optional[str] = Field(default=None, index=True)
    description: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None)
    phone_number: Optional[str] = Field(default=None)
    subscribers_count: int = Field(default=0)
    channel_url: str
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    keyword_ref: Keyword = Relationship(back_populates="channels")
    messages: List["Message"] = Relationship(back_populates="channel_ref")

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    channel_id: int = Field(foreign_key="channel.id")
    telegram_id: int = Field(index=True)
    text: str
    date: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

    channel_ref: Channel = Relationship(back_populates="messages")

class ScanLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    keyword_id: Optional[int] = Field(default=None, foreign_key="keyword.id")
    status: str
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WordFrequency(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    keyword_id: int = Field(foreign_key="keyword.id")
    word: str = Field(index=True)
    count: int = Field(default=0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
