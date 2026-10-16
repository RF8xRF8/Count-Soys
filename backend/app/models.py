from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core.clock import beijing_now
from .database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")
    status: Mapped[int] = mapped_column(Integer, default=1)
    daily_quota: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(16), default="pills")
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    original_path: Mapped[str] = mapped_column(String(255))
    annotated_path: Mapped[str] = mapped_column(String(255))
    count: Mapped[int] = mapped_column(Integer, default=0)
    instances_json: Mapped[str] = mapped_column(Text, default="[]")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="success")
    error_msg: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now, index=True)
    user: Mapped[User] = relationship(back_populates="tasks")
