"""Solo en Postgres: 20 clientes simultáneos compiten por el mismo día; nunca deben pasar de los cupos."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from common import campana, service
from common.config import hoy
from common.db import Base, Lead, engine, init_db, session

pytestmark = pytest.mark.skipif(engine.dialect.name != "postgresql", reason="requiere Postgres")


def test_no_se_sobrevende():
    Base.metadata.drop_all(engine)
    init_db()
    d = hoy() + timedelta(days=1)
    while d.weekday() not in campana.DIAS_RETIRO:
        d += timedelta(days=1)

    def intento(i):
        try:
            with session() as s:
                service.registrar_lead(s, f"Cliente {i}", f"80000{i:03d}", d.isoformat(), "luz_media")
            return True
        except service.ErrorRegistro:
            return False

    with ThreadPoolExecutor(20) as ex:
        ok = sum(ex.map(intento, range(20)))
    with session() as s:
        assert s.query(Lead).count() == ok == campana.CUPOS_POR_DIA
