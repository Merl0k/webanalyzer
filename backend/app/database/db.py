"""
app/database/db.py — PostgreSQL / SQLite persistence layer v3
"""
import json, os, secrets
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from loguru import logger

from app.database.models import Base, User, ApiKey, Search, Tag, Collection

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///searches.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

_connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine  = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True, pool_recycle=300)
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
    logger.info(f"DB ready: {'PostgreSQL' if 'postgresql' in DATABASE_URL else 'SQLite'}")

def create_user(email, password_hash):
    with Session() as s:
        u = User(email=email, password_hash=password_hash)
        s.add(u); s.commit(); s.refresh(u)
        return {"id": u.id, "email": u.email}

def get_user_by_email(email):
    with Session() as s:
        u = s.query(User).filter(User.email == email).first()
        if not u: return None
        return {"id": u.id, "email": u.email, "password_hash": u.password_hash,
                "is_active": u.is_active, "theme": u.theme}

def get_user_by_id(user_id):
    with Session() as s:
        u = s.query(User).filter(User.id == user_id).first()
        if not u: return None
        return {"id": u.id, "email": u.email, "is_active": u.is_active, "theme": u.theme}

def update_user_theme(user_id, theme):
    with Session() as s:
        s.query(User).filter(User.id == user_id).update({"theme": theme})
        s.commit()

def save_api_key(user_id, provider, key_enc, model=""):
    with Session() as s:
        existing = s.query(ApiKey).filter(ApiKey.user_id == user_id, ApiKey.provider == provider).first()
        if existing:
            existing.key_enc = key_enc; existing.model = model; s.commit()
            return {"id": existing.id, "provider": provider, "model": model}
        k = ApiKey(user_id=user_id, provider=provider, key_enc=key_enc, model=model)
        s.add(k); s.commit(); s.refresh(k)
        return {"id": k.id, "provider": provider, "model": model}

def get_api_keys(user_id):
    with Session() as s:
        keys = s.query(ApiKey).filter(ApiKey.user_id == user_id).all()
        return [{"id": k.id, "provider": k.provider, "model": k.model} for k in keys]

def get_api_key_enc(user_id, provider):
    with Session() as s:
        k = s.query(ApiKey).filter(ApiKey.user_id == user_id, ApiKey.provider == provider).first()
        return k.key_enc if k else None

def get_api_key_record(user_id, provider):
    with Session() as s:
        k = (
            s.query(ApiKey)
            .filter(ApiKey.user_id == user_id, ApiKey.provider == provider)
            .first()
        )

        if not k:
            return None

        return {
            "provider": k.provider,
            "key_enc": k.key_enc,
            "model": k.model,
        }   

def delete_api_key(user_id, provider):
    with Session() as s:
        s.query(ApiKey).filter(ApiKey.user_id == user_id, ApiKey.provider == provider).delete()
        s.commit()

def save_search(query, result, user_id=None, depth="standard", lang="auto"):
    sent = result.get("sentiment", {}); sources = result.get("sources", [])
    with Session() as s:
        r = Search(user_id=user_id, query=query, summary=result.get("summary",""),
            sentiment=json.dumps(sent, ensure_ascii=False),
            key_facts=json.dumps(result.get("key_facts",[]), ensure_ascii=False),
            sources=json.dumps(sources, ensure_ascii=False),
            pos_score=sent.get("positive",0), neg_score=sent.get("negative",0),
            neu_score=sent.get("neutral",0),  overall=sent.get("overall","neutral"),
            sources_cnt=len(sources), depth=depth, lang=lang, created_at=datetime.now())
        s.add(r); s.commit(); s.refresh(r); return r.id

def get_history(limit=20, offset=0, user_id=None, tag_id=None, collection_id=None):
    with Session() as s:
        q = s.query(
            Search.id,
            Search.query,
            Search.summary,
            Search.overall,
            Search.sources_cnt,
            Search.depth,
            Search.created_at,
        )

        if user_id is not None:
            q = q.filter(Search.user_id == user_id)

        if tag_id:
            q = q.join(Search.tags).filter(Tag.id == tag_id)

            if user_id is not None:
                q = q.filter(Tag.user_id == user_id)

        if collection_id:
            q = q.join(Search.collections).filter(Collection.id == collection_id)

            if user_id is not None:
                q = q.filter(Collection.user_id == user_id)

        rows = q.order_by(Search.id.desc()).limit(limit).offset(offset).all()

    return [
        {
            "id": r.id,
            "query": r.query,
            "summary": r.summary,
            "overall": r.overall,
            "sources_cnt": r.sources_cnt,
            "depth": r.depth,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if r.created_at
            else "",
        }
        for r in rows
    ]

def get_search_by_id(search_id, user_id=None):
    with Session() as s:
        q = s.query(Search).filter(Search.id == search_id)

        if user_id is not None:
            q = q.filter(Search.user_id == user_id)

        r = q.first()

        if not r:
            return None

        tags = [{"id": t.id, "name": t.name, "color": t.color} for t in r.tags]

        collections = [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
            }
            for c in r.collections
        ]
        return {
            "id": r.id,
            "user_id": r.user_id,
            "query": r.query,
            "summary": r.summary,
            "sentiment": json.loads(r.sentiment or "{}"),
            "key_facts": json.loads(r.key_facts or "[]"),
            "sources": json.loads(r.sources or "[]"),
            "overall": r.overall,
            "sources_cnt": r.sources_cnt,
            "depth": r.depth,
            "lang": r.lang,
            "tags": tags,
            "collections": collections,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if r.created_at
            else "",
        }


def get_search_by_share_token(token):
    with Session() as s:
        r = s.query(Search).filter(Search.share_token == token).first()

        if not r:
            return None

        if r.share_expires and r.share_expires < datetime.utcnow():
            return None

        return get_search_by_id(r.id)


def create_share_link(search_id, user_id=None):
    token = secrets.token_hex(16)
    expires = datetime.utcnow() + timedelta(days=7)

    with Session() as s:
        q = s.query(Search).filter(Search.id == search_id)

        if user_id is not None:
            q = q.filter(Search.user_id == user_id)

        search = q.first()

        if not search:
            return None

        search.share_token = token
        search.share_expires = expires
        s.commit()

    return token


def delete_search(search_id, user_id=None):
    with Session() as s:
        q = s.query(Search).filter(Search.id == search_id)

        if user_id is not None:
            q = q.filter(Search.user_id == user_id)

        deleted = q.delete()
        s.commit()

        return deleted > 0


def get_tags(user_id):
    with Session() as s:
        return [
            {"id": t.id, "name": t.name, "color": t.color}
            for t in s.query(Tag).filter(Tag.user_id == user_id).all()
        ]


def create_tag(user_id, name, color="#4fffb0"):
    with Session() as s:
        t = Tag(user_id=user_id, name=name, color=color)
        s.add(t)
        s.commit()
        s.refresh(t)

        return {"id": t.id, "name": t.name, "color": t.color}


def delete_tag(user_id, tag_id):
    with Session() as s:
        deleted = (
            s.query(Tag)
            .filter(Tag.id == tag_id, Tag.user_id == user_id)
            .delete()
        )
        s.commit()

        return deleted > 0


def add_tag_to_search(search_id, tag_id, user_id):
    with Session() as s:
        search = (
            s.query(Search)
            .filter(Search.id == search_id, Search.user_id == user_id)
            .first()
        )

        tag = (
            s.query(Tag)
            .filter(Tag.id == tag_id, Tag.user_id == user_id)
            .first()
        )

        if not search or not tag:
            return False

        if tag not in search.tags:
            search.tags.append(tag)
            s.commit()

        return True


def remove_tag_from_search(search_id, tag_id, user_id):
    with Session() as s:
        search = (
            s.query(Search)
            .filter(Search.id == search_id, Search.user_id == user_id)
            .first()
        )

        tag = (
            s.query(Tag)
            .filter(Tag.id == tag_id, Tag.user_id == user_id)
            .first()
        )

        if not search or not tag:
            return False

        if tag in search.tags:
            search.tags.remove(tag)
            s.commit()

        return True


def get_collections(user_id):
    with Session() as s:
        return [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "count": len(c.searches),
            }
            for c in s.query(Collection).filter(Collection.user_id == user_id).all()
        ]


def create_collection(user_id, name, description=""):
    with Session() as s:
        c = Collection(user_id=user_id, name=name, description=description)
        s.add(c)
        s.commit()
        s.refresh(c)

        return {"id": c.id, "name": c.name, "description": c.description}


def add_to_collection(search_id, collection_id, user_id):
    with Session() as s:
        search = (
            s.query(Search)
            .filter(Search.id == search_id, Search.user_id == user_id)
            .first()
        )

        col = (
            s.query(Collection)
            .filter(Collection.id == collection_id, Collection.user_id == user_id)
            .first()
        )

        if not search or not col:
            return False

        if search not in col.searches:
            col.searches.append(search)
            s.commit()

        return True
    
def remove_from_collection(search_id, collection_id, user_id):
    with Session() as s:
        search = (
            s.query(Search)
            .filter(Search.id == search_id, Search.user_id == user_id)
            .first()
        )

        col = (
            s.query(Collection)
            .filter(Collection.id == collection_id, Collection.user_id == user_id)
            .first()
        )

        if not search or not col:
            return False

        if search in col.searches:
            col.searches.remove(search)
            s.commit()

        return True


def delete_collection(user_id, collection_id):
    with Session() as s:
        col = (
            s.query(Collection)
            .filter(Collection.id == collection_id, Collection.user_id == user_id)
            .first()
        )

        if not col:
            return False

        s.delete(col)
        s.commit()

        return True

def get_stats(user_id=None):
    with Session() as s:
        q = s.query(Search)
        if user_id: q = q.filter(Search.user_id==user_id)
        total = q.count()
        pg = "postgresql" in DATABASE_URL
        uid_filter = f"WHERE user_id = {user_id}" if user_id else ""
        sent_rows  = s.execute(text(f"SELECT overall, COUNT(*) as cnt FROM searches {uid_filter} GROUP BY overall")).fetchall()
        day_sql = (f"SELECT DATE(created_at) as day, COUNT(*) as cnt FROM searches {uid_filter} GROUP BY day ORDER BY day DESC LIMIT 14"
                   if pg else
                   f"SELECT substr(created_at,1,10) as day, COUNT(*) as cnt FROM searches {uid_filter} GROUP BY day ORDER BY day DESC LIMIT 14")
        daily_rows = s.execute(text(day_sql)).fetchall()
        top_rows   = s.execute(text(f"SELECT query, COUNT(*) as cnt FROM searches {uid_filter} GROUP BY query ORDER BY cnt DESC LIMIT 10")).fetchall()
        avg_row    = s.execute(text(f"SELECT AVG(pos_score) as pos, AVG(neg_score) as neg, AVG(neu_score) as neu, AVG(sources_cnt) as src FROM searches {uid_filter}")).fetchone()
    return {"total":total,"avg_sources":round(avg_row.src or 0,1),
            "sentiment_dist":[{"overall":r.overall,"cnt":r.cnt} for r in sent_rows],
            "daily":list(reversed([{"day":r.day,"cnt":r.cnt} for r in daily_rows])),
            "top_queries":[{"query":r.query,"cnt":r.cnt} for r in top_rows],
            "avg_sentiment":{"pos":round(avg_row.pos or 0,3),"neg":round(avg_row.neg or 0,3),"neu":round(avg_row.neu or 0,3)}}
