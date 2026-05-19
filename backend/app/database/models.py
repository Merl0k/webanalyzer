"""
app/database/models.py — SQLAlchemy ORM models v3
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean,
    ForeignKey, Table
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Many-to-many: searches <-> tags
search_tags = Table(
    "search_tags", Base.metadata,
    Column("search_id", Integer, ForeignKey("searches.id",    ondelete="CASCADE")),
    Column("tag_id",    Integer, ForeignKey("tags.id",        ondelete="CASCADE")),
)

# Many-to-many: searches <-> collections
search_collections = Table(
    "search_collections", Base.metadata,
    Column("search_id",     Integer, ForeignKey("searches.id",     ondelete="CASCADE")),
    Column("collection_id", Integer, ForeignKey("collections.id",  ondelete="CASCADE")),
)


class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    email         = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active     = Column(Boolean, default=True)
    theme         = Column(String(32), default="dark")
    created_at    = Column(DateTime, default=datetime.utcnow)

    api_keys    = relationship("ApiKey",     back_populates="user", cascade="all, delete-orphan")
    searches    = relationship("Search",     back_populates="user", cascade="all, delete-orphan")
    tags        = relationship("Tag",        back_populates="user", cascade="all, delete-orphan")
    collections = relationship("Collection", back_populates="user", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"
    id       = Column(Integer, primary_key=True, autoincrement=True)
    user_id  = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(32),  nullable=False)
    key_enc  = Column(Text,        nullable=False)
    model    = Column(String(128), default="")

    user = relationship("User", back_populates="api_keys")


class Search(Base):
    __tablename__ = "searches"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    query       = Column(String(500), nullable=False)
    summary     = Column(Text)
    sentiment   = Column(Text)
    key_facts   = Column(Text)
    sources     = Column(Text)
    pos_score   = Column(Float, default=0.0)
    neg_score   = Column(Float, default=0.0)
    neu_score   = Column(Float, default=0.0)
    overall     = Column(String(20), default="neutral")
    sources_cnt = Column(Integer, default=0)
    depth       = Column(String(16), default="standard")
    lang        = Column(String(16), default="auto")
    share_token   = Column(String(64), unique=True, nullable=True)
    share_expires = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    user        = relationship("User",       back_populates="searches")
    tags        = relationship("Tag",        secondary=search_tags,       back_populates="searches")
    collections = relationship("Collection", secondary=search_collections, back_populates="searches")

    def __repr__(self):
        return f"<Search id={self.id} query='{self.query[:30]}'>"


class Tag(Base):
    __tablename__ = "tags"
    id      = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name    = Column(String(64),  nullable=False)
    color   = Column(String(16),  default="#4fffb0")

    user     = relationship("User",   back_populates="tags")
    searches = relationship("Search", secondary=search_tags, back_populates="tags")


class Collection(Base):
    __tablename__ = "collections"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(128), nullable=False)
    description = Column(Text, default="")

    user     = relationship("User",   back_populates="collections")
    searches = relationship("Search", secondary=search_collections, back_populates="collections")
