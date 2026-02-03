from enum import StrEnum

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import String


class Base(DeclarativeBase):
    pass


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    given_name: Mapped[str] = mapped_column(String(50), nullable=True)
    family_name: Mapped[str] = mapped_column(String(50), nullable=True)
    picture: Mapped[str] = mapped_column(String(500), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        String(20), default=UserRole.USER, server_default=str(UserRole.USER)
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(500), nullable=True)
