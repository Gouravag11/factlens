import sqlite3
import json
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from models import Fact
import uuid

# SQLite setup
DB_NAME = "factlens.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS facts (
            id TEXT PRIMARY KEY,
            fact_statement TEXT,
            metric_or_subject TEXT,
            value TEXT,
            timeframe TEXT,
            evidence_quote TEXT,
            page_number INTEGER,
            source_document TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS clusters (
            id TEXT PRIMARY KEY,
            relationship_type TEXT,
            summary TEXT,
            fact_ids TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS failures (
            id TEXT PRIMARY KEY,
            fact_statement TEXT,
            evidence_quote TEXT,
            source_document TEXT,
            reason TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_fact(fact: Fact, fact_id: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO facts (id, fact_statement, metric_or_subject, value, timeframe, evidence_quote, page_number, source_document)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (fact_id, fact.fact_statement, fact.metric_or_subject, fact.value, fact.timeframe, fact.evidence_quote, fact.page_number, fact.source_document))
    conn.commit()
    conn.close()

def save_failure(failure_id: str, fact_statement: str, evidence_quote: str, source_document: str, reason: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO failures (id, fact_statement, evidence_quote, source_document, reason)
        VALUES (?, ?, ?, ?, ?)
    ''', (failure_id, fact_statement, evidence_quote, source_document, reason))
    conn.commit()
    conn.close()

# Qdrant setup
qdrant = QdrantClient(":memory:")  # In-memory vector DB for fast prototyping
COLLECTION_NAME = "facts"

def init_qdrant():
    if not qdrant.collection_exists(COLLECTION_NAME):
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
        )

def reset_qdrant():
    if qdrant.collection_exists(COLLECTION_NAME):
        qdrant.delete_collection(collection_name=COLLECTION_NAME)
    init_qdrant()

def save_fact_embedding(fact_id: str, embedding: list, payload: dict):
    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=fact_id,
                vector=embedding,
                payload=payload
            )
        ]
    )

def search_similar_facts(embedding: list, limit: int = 5):
    if not qdrant.collection_exists(COLLECTION_NAME):
        return []
    res = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding,
        limit=limit
    )
    return res.points

def get_fact_embedding(fact_id: str) -> list:
    if not qdrant.collection_exists(COLLECTION_NAME):
        return None
    res = qdrant.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[fact_id],
        with_vectors=True
    )
    if res and len(res) > 0 and res[0].vector is not None:
        return res[0].vector
    return None

init_db()
init_qdrant()
