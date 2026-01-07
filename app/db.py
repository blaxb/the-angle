import os
from sqlalchemy.engine.url import make_url
from sqlmodel import SQLModel, create_engine, Session
from .settings import settings

connect_args = {}
if settings.db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.db_url,
    echo=False,
    connect_args=connect_args,
)

def init_db() -> None:
    if settings.db_url.startswith("sqlite"):
        url = make_url(settings.db_url)
        db_path = url.database
        if db_path and db_path != ":memory:":
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
