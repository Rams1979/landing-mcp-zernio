"""Carga leads ficticios para la demo. Uso: python -m scripts.seed  (no pisa datos existentes)."""
import random
from datetime import date, timedelta

from common import campana
from common.config import hoy
from common.db import Lead, init_db, session
from common.service import cupos_por_dia

NOMBRES = ["Ana Mora", "Luis Campos", "Marta Solano", "José Araya", "Sofía Vargas", "Diego Rojas", "Laura Jiménez",
           "Carlos Brenes", "Paula Ureña", "Andrés Chaves", "Elena Quesada", "Mateo Salas", "Valeria Cordero", "Rafael Mena"]


def main(n: int = 40, semilla: int = 7):
    rnd = random.Random(semilla)
    init_db()
    with session() as s:
        dias = [d for d in cupos_por_dia(s, desde=hoy()) if d["libres"] > 0][:12]
        creados = 0
        for i in range(n):
            d = rnd.choice(dias)
            s.add(Lead(nombre=rnd.choice(NOMBRES), whatsapp=f"8{rnd.randint(0, 9999999):07d}",
                       dia=d["fecha"], espacio=rnd.choice(list(campana.ESPACIOS))))
            d["libres"] -= 1
            creados += 1
            if d["libres"] <= 0:
                dias.remove(d)
            if not dias:
                break
        s.commit()
    print(f"Leads ficticios creados: {creados}")


if __name__ == "__main__":
    main()
