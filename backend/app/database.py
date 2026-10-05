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
    table_names = inspector.get_table_names()

    if "zone" in table_names:
        existing_cols = {c["name"] for c in inspector.get_columns("zone")}
        with engine.begin() as conn:
            if "vehicle_stop_seconds" not in existing_cols:
                conn.execute(text("ALTER TABLE zone ADD COLUMN vehicle_stop_seconds INTEGER DEFAULT 60"))
            if "blocks_exit" not in existing_cols:
                conn.execute(text("ALTER TABLE zone ADD COLUMN blocks_exit BOOLEAN DEFAULT 0"))

    if "user" in table_names:
        existing_user_cols = {c["name"] for c in inspector.get_columns("user")}
        if "role" not in existing_user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR DEFAULT 'cliente'"))
                # Primera vez que agregamos esta columna: el usuario más antiguo de la
                # instalación (normalmente el único, el dueño) pasa a admin solo, para
                # no dejar la instalación sin nadie que pueda ver "Admin".
                conn.execute(
                    text("UPDATE user SET role = 'admin' WHERE id = (SELECT MIN(id) FROM user)")
                )
        if "trial_ends_at" not in existing_user_cols:
            is_sqlite = settings.DATABASE_URL.startswith("sqlite")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN trial_ends_at TIMESTAMP"))
                # Cuentas que ya existían antes de este campo: les damos 30 días de
                # prueba a partir de ahora, para no cortarles el servicio de golpe con
                # el deploy. Las cuentas nuevas ya nacen con esto (ver auth.py). La
                # función de fecha cambia según el motor (SQLite local vs Postgres
                # en la nube).
                if is_sqlite:
                    conn.execute(
                        text(
                            "UPDATE user SET trial_ends_at = datetime('now', '+30 days') "
                            "WHERE trial_ends_at IS NULL"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "UPDATE user SET trial_ends_at = NOW() + INTERVAL '30 days' "
                            "WHERE trial_ends_at IS NULL"
                        )
                    )
        if "account_mode" not in existing_user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE user ADD COLUMN account_mode VARCHAR DEFAULT 'hogar'"))

    if "agenttoken" in table_names:
        existing_agenttoken_cols = {c["name"] for c in inspector.get_columns("agenttoken")}
        if "last_seen_ip" not in existing_agenttoken_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE agenttoken ADD COLUMN last_seen_ip VARCHAR"))


def init_db() -> None:
    # Importa los modelos para que SQLModel los registre antes de crear las tablas
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate_existing_tables()


def get_session():
    with Session(engine) as session:
        yield session
