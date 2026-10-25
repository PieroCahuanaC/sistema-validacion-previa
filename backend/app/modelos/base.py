from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa. El esquema lo define la migración 0001, no el ORM."""
