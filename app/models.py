from sqlmodel import SQLModel, Field, Column
from datetime import datetime
from typing import Optional

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str

    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    is_active_subscriber: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)

class Post(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    source: str  # reddit | x | linkedin
    source_id: str = Field(index=True)
    category: str = Field(index=True, default="misc")

    title: str
    url: str
    author: Optional[str] = None
    created_utc: int

    score: int = 0
    num_comments: int = 0
    heat_score: float = 0.0

    fetched_at: datetime = Field(default_factory=datetime.utcnow)

class CategorySummary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str = Field(index=True, unique=True)
    summary: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ConversationSummary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str = Field(index=True)
    post_url: str
    summary: str
    position: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserTopic(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    topic: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
