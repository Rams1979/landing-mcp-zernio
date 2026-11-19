from contextlib import contextmanager
from datetime import date, datetime

from sqlalchemy import (Date, DateTime, ForeignKey, Integer, String,
                        UniqueConstraint, create_engine, func, select)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import (DeclarativeBase, Mapped, Session, mapped_column,
                            sessionmaker)

from . import campana
from .config import database_url, hoy


class Base(DeclarativeBase):
    pass


class Dia(Base):
    __tablename__ = "dias"
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    cupos: Mapped[int] = mapped_column(Integer, nullable=False)


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("whatsapp", "dia", name="uq_lead_whatsapp_dia"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    whatsapp: Mapped[str] = mapped_column(String(8), nullable=False)
    dia: Mapped[date] = mapped_column(ForeignKey("dias.fecha"), nullable=False, index=True)
    espacio: Mapped[str] = mapped_column(String(20), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


_url = database_url()
engine = create_engine(_url, pool_pre_ping=True,
                       connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {})
SessionLocal = sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session() -> Session:
    with SessionLocal() as s:
        yield s


def init_db() -> None:
    """Crea tablas y días de retiro. Idempotente; tolera el arranque simultáneo de dos servicios."""
    for intento in (1, 2):
        try:
            Base.metadata.create_all(engine)
            break
        except DBAPIError:
            if intento == 2:
                raise
    with session() as s:
        existentes = set(s.scalars(select(Dia.fecha)))
        d = campana.FECHA_INICIO
        while d <= campana.FECHA_LIMITE:
            if d.weekday() in campana.DIAS_RETIRO and d not in existentes:
                s.add(Dia(fecha=d, cupos=campana.CUPOS_POR_DIA))
            d = date.fromordinal(d.toordinal() + 1)
        s.commit()
