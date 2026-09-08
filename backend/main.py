from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
import database
from pdf_parser import extract_text_from_pdf
from extractor import extract_facts_from_document, get_embeddings
from reconciler import reconcile_facts
from models import ClusterAnalysis, Fact, FactFailure
from typing import List

app = FastAPI(title="Fact Lens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def process_pdf_background(file_bytes: bytes, filename: str):
    print(f"Starting processing for {filename}")
    pages = extract_text_from_pdf(file_bytes, filename)
    
    all_extracted_facts = []
    
    print(f"Extracting facts from entire document: {filename}...")
    extracted = extract_facts_from_document(pages, filename)
    
    if extracted.facts:
        statements = [fact.fact_statement for fact in extracted.facts]
        print(f"Batch embedding {len(statements)} facts...")
        embeddings = get_embeddings(statements)
        
        for fact, embedding in zip(extracted.facts, embeddings):
            fact_id = str(uuid.uuid4())
            database.save_fact(fact, fact_id)
            all_extracted_facts.append((fact_id, fact))
            
            if embedding:
                database.save_fact_embedding(fact_id, embedding, fact.model_dump())
                
    if extracted.failures:
        print(f"Saving {len(extracted.failures)} extraction failures...")
        for failure in extracted.failures:
            database.save_failure(str(uuid.uuid4()), failure.fact_statement, failure.evidence_quote, failure.source_document, failure.reason)
    
    print(f"Finished extracting {len(all_extracted_facts)} valid facts and caught {len(extracted.failures)} failures from {filename}.")

@app.post("/reconcile")
async def trigger_reconciliation():
    run_reconciliation_pass()
    return {"message": "Reconciliation complete."}

def run_reconciliation_pass():
    print("Running reconciliation pass over all facts...")
    # Very simple clustering for prototype: 
    # For every fact, find similar ones. Group them.
    import sqlite3
    conn = sqlite3.connect(database.DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, fact_statement FROM facts")
    all_facts_db = c.fetchall()
    
    c.execute("SELECT fact_ids FROM clusters")
    existing_clusters = c.fetchall()
    conn.close()
    
    # Cap total clusters to 10 to save massive API costs (Assignment only needs 3-4 examples)
    if len(existing_clusters) >= 10:
        print("Max clusters limit (10) reached. Skipping further reconciliation to save LLM costs.")
        return
        
    # Pre-populate processed_ids with facts already inside a cluster! 
    # This prevents re-evaluating the exact same clusters over and over.
    processed_ids = set()
    for row in existing_clusters:
        if row[0]:
            processed_ids.update(row[0].split(","))
            
    clusters = []
    
    for fact_id, statement in all_facts_db:
        if fact_id in processed_ids:
            continue
            
        embedding = database.get_fact_embedding(fact_id)
        if not embedding:
            continue
            
        # Search Qdrant
        results = database.search_similar_facts(embedding, limit=5)
        
        # Filter matches (cosine similarity > 0.8 is a good threshold usually, but depends on model)
        # qdrant score for cosine is between 0 and 1
        similar_facts = []
        for res in results:
            if res.score > 0.75: # arbitrary threshold for prototype
                similar_facts.append(res)
                processed_ids.add(res.id)
                
        if len(similar_facts) > 1:
            # We found a cluster! Let's reconcile it.
            from models import Fact
            facts_to_reconcile = [Fact(**res.payload) for res in similar_facts]
            # Allow intra-document and cross-document relationships to fulfill assignment goals
            analysis = reconcile_facts(facts_to_reconcile)
            if analysis:
                clusters.append(analysis)
                
                # Save cluster to DB
                conn = sqlite3.connect(database.DB_NAME)
                c = conn.cursor()
                fact_ids_str = ",".join([res.id for res in similar_facts])
                c.execute('''
                    INSERT INTO clusters (id, relationship_type, summary, fact_ids)
                    VALUES (?, ?, ?, ?)
                ''', (analysis.cluster_id, analysis.relationship_type, analysis.summary, fact_ids_str))
                conn.commit()
                conn.close()
    
    print(f"Reconciliation pass complete. Formed {len(clusters)} clusters.")

@app.post("/reset")
async def reset_database_endpoint():
    import sqlite3
    conn = sqlite3.connect(database.DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM facts")
    c.execute("DELETE FROM clusters")
    c.execute("DELETE FROM failures")
    conn.commit()
    conn.close()
    
    database.reset_qdrant()
    return {"message": "Database reset successful."}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    contents = await file.read()
    process_pdf_background(contents, file.filename)
    return {"message": "File processing successful.", "filename": file.filename}

@app.get("/clusters", response_model=List[ClusterAnalysis])
async def get_clusters():
    import sqlite3
    from models import Fact
    conn = sqlite3.connect(database.DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, relationship_type, summary, fact_ids FROM clusters")
    cluster_rows = c.fetchall()
    
    clusters = []
    for row in cluster_rows:
        cluster_id, rel_type, summary, fact_ids_str = row
        fact_ids = fact_ids_str.split(",")
        
        facts = []
        for fid in fact_ids:
            c.execute("SELECT fact_statement, metric_or_subject, value, timeframe, evidence_quote, page_number, source_document FROM facts WHERE id=?", (fid,))
            f_row = c.fetchone()
            if f_row:
                facts.append(Fact(
                    fact_statement=f_row[0],
                    metric_or_subject=f_row[1],
                    value=f_row[2],
                    timeframe=f_row[3],
                    evidence_quote=f_row[4],
                    page_number=f_row[5],
                    source_document=f_row[6]
                ))
                
        clusters.append(ClusterAnalysis(
            cluster_id=cluster_id,
            relationship_type=rel_type,
            summary=summary,
            facts=facts
        ))
        
    conn.close()
    return clusters

@app.get("/facts", response_model=List[Fact])
async def get_all_facts():
    import sqlite3
    conn = sqlite3.connect(database.DB_NAME)
    c = conn.cursor()
    c.execute("SELECT fact_statement, metric_or_subject, value, timeframe, evidence_quote, page_number, source_document FROM facts")
    rows = c.fetchall()
    
    facts = []
    for f_row in rows:
        facts.append(Fact(
            fact_statement=f_row[0],
            metric_or_subject=f_row[1],
            value=f_row[2],
            timeframe=f_row[3],
            evidence_quote=f_row[4],
            page_number=f_row[5],
            source_document=f_row[6]
        ))
        
    conn.close()
    return facts

@app.get("/failures", response_model=List[FactFailure])
async def get_failures():
    import sqlite3
    from models import FactFailure
    conn = sqlite3.connect(database.DB_NAME)
    c = conn.cursor()
    c.execute("SELECT fact_statement, evidence_quote, source_document, reason FROM failures")
    rows = c.fetchall()
    
    failures = []
    for r in rows:
        failures.append(FactFailure(
            fact_statement=r[0],
            evidence_quote=r[1],
            source_document=r[2],
            reason=r[3]
        ))
    conn.close()
    return failures

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
