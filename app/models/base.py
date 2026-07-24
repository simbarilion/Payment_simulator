"""Базовый класс для моделей БД"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс ORM-моделей SQLAlchemy"""
