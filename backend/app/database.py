from sqlalchemy import inspect, text
from sqlmodel import SQLModel, Session, create_engine
from app.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)


def _migrate_existing_tables() -> None:
    """Migración mínima a mano (no usamos Alembic acá). SQLModel.metadata.create_all()
    sólo crea tablas que todavía no existen; si una tabla ya existía de antes (como la
    base sqlite que Roberto ya viene usando) y le agregamos una columna nueva al modelo,
    create_all() no la agrega sola. Esto chequea y agrega las columnas que falten."""
    inspector = inspect(engine)
    if "zone" not in inspector.get_table_names():
        return
    existing_cols = {c["name"] for c in inspector.get_columns("zone")}
    with engine.begin() as conn:
        if "vehicle_stop_seconds" not in existing_cols:
            conn.execute(text("ALTER TABLE zone ADD COLUMN vehicle_stop_seconds INTEGER DEFAULT 60"))
        if "blocks_exit" not in existing_cols:
            conn.execute(text("ALTER TABLE zone ADD COLUMN blocks_exit BOOLEAN DEFAULT 0"))


def init_db() -> None:
    # Importa los modelos para que SQLModel los registre antes de crear las tablas
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate_existing_tables()


def get_session():
    with Session(engine) as session:
        yield session
