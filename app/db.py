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
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

