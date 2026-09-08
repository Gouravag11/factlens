from pydantic import BaseModel
from typing import List, Optional

class Fact(BaseModel):
    fact_statement: str
    metric_or_subject: str
    value: Optional[str] = None
    timeframe: Optional[str] = None
    evidence_quote: str
    page_number: int
    source_document: str

class FactFailure(BaseModel):
    fact_statement: str
    evidence_quote: str
    source_document: str
    reason: str

class ExtractedFacts(BaseModel):
    facts: List[Fact]
    failures: Optional[List[FactFailure]] = []

class DocumentMetadata(BaseModel):
    filename: str
    page_count: int
    
class ClusterAnalysis(BaseModel):
    cluster_id: str
    relationship_type: str  # "Corroboration", "Contradiction", "Contextual Reconciliation"
    summary: str
    facts: List[Fact]
