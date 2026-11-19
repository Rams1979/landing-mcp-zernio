"""Lógica de negocio compartida por la landing y el MCP."""
import re
from collections import Counter
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from . import campana
from .config import hoy
from .db import Dia, Lead


class ErrorRegistro(Exception):
    """Error de validación o de cupo, con mensaje apto para mostrar al cliente."""


def cupos_por_dia(s, desde: date | None = None, hasta: date | None = None) -> list[dict]:
    desde = desde or hoy()
    ocupados = (select(Lead.dia, func.count(Lead.id).label("n")).group_by(Lead.dia)).subquery()
    q = (select(Dia.fecha, Dia.cupos, func.coalesce(ocupados.c.n, 0))
         .outerjoin(ocupados, ocupados.c.dia == Dia.fecha)
         .where(Dia.fecha >= desde).order_by(Dia.fecha))
    if hasta:
        q = q.where(Dia.fecha <= hasta)
    return [{"fecha": f, "total": t, "ocupados": o, "libres": max(t - o, 0)} for f, t, o in s.execute(q)]


def estado(s) -> dict:
    h = hoy()
    dias = cupos_por_dia(s, desde=campana.FECHA_INICIO)
    total = sum(d["total"] for d in dias)
    ocupados = sum(d["ocupados"] for d in dias)
    futuros = [d for d in dias if d["fecha"] >= h]
    return {
        "oferta_vigente": h <= campana.FECHA_LIMITE,
        "dias_restantes": max((campana.FECHA_LIMITE - h).days, 0),
        "cupos_totales": total,
        "cupos_ocupados": ocupados,
        "cupos_libres_desde_hoy": sum(d["libres"] for d in futuros),
        "ocupacion_pct": round(100 * ocupados / total, 1) if total else 0.0,
        "leads_totales": s.scalar(select(func.count(Lead.id))) or 0,
    }


def normalizar_whatsapp(valor: str) -> str:
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) == 11 and digitos.startswith("506"):
        digitos = digitos[3:]
    if not re.fullmatch(r"[2-8]\d{7}", digitos):
        raise ErrorRegistro("Escriba un número de WhatsApp de 8 dígitos, por ejemplo 8888 0000.")
    return digitos


def registrar_lead(s, nombre: str, whatsapp: str, dia: str, espacio: str) -> date:
    nombre = " ".join((nombre or "").split())
    if not 2 <= len(nombre) <= 80:
        raise ErrorRegistro("Escriba su nombre (entre 2 y 80 caracteres).")
    wa = normalizar_whatsapp(whatsapp)
    if espacio not in campana.ESPACIOS:
        raise ErrorRegistro("Elija el tipo de espacio donde pondrá sus plantas.")
    try:
        fecha = date.fromisoformat(dia)
    except (TypeError, ValueError):
        raise ErrorRegistro("Elija un día de retiro.")
    h = hoy()
    if h > campana.FECHA_LIMITE:
        raise ErrorRegistro("La oferta ya terminó.")
    if fecha < h:
        raise ErrorRegistro("Ese día ya pasó. Elija otro día de retiro.")
    # Bloquea la fila del día para que dos clientes no tomen el último cupo a la vez (Postgres).
    fila = s.execute(select(Dia).where(Dia.fecha == fecha).with_for_update()).scalar_one_or_none()
    if fila is None:
        raise ErrorRegistro("Ese día no tiene retiro disponible.")
    ocupados = s.scalar(select(func.count(Lead.id)).where(Lead.dia == fecha)) or 0
    if ocupados >= fila.cupos:
        s.rollback()
        raise ErrorRegistro("Ese día se llenó. Elija otro día de retiro.")
    s.add(Lead(nombre=nombre, whatsapp=wa, dia=fecha, espacio=espacio))
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        raise ErrorRegistro("Ya tiene un cupo reservado para ese día con este WhatsApp.")
    return fecha


def enmascarar_nombre(n: str) -> str:
    partes = n.split()
    return partes[0] + (f" {partes[1][0]}." if len(partes) > 1 else "")


def enmascarar_whatsapp(w: str) -> str:
    return "****" + w[-4:]


def listar_leads(s, limite: int = 20, dia: date | None = None) -> list[dict]:
    q = select(Lead).order_by(Lead.creado_en.desc(), Lead.id.desc()).limit(max(1, min(limite, 100)))
    if dia:
        q = q.where(Lead.dia == dia)
    return [{"id": l.id, "nombre": enmascarar_nombre(l.nombre), "whatsapp": enmascarar_whatsapp(l.whatsapp),
             "dia_retiro": l.dia.isoformat(), "espacio": campana.ESPACIOS.get(l.espacio, l.espacio),
             "creado_en": l.creado_en.isoformat()} for l in s.scalars(q)]


def distribucion_espacios(s) -> dict:
    c = Counter(s.scalars(select(Lead.espacio)))
    return {campana.ESPACIOS.get(k, k): v for k, v in c.most_common()}
