import google.generativeai as genai
from models import Fact, ClusterAnalysis
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

model = genai.GenerativeModel('gemini-3.5-flash-lite')

def reconcile_facts(facts: List[Fact]) -> ClusterAnalysis:
    """Analyzes a list of similar facts to determine their relationship."""
    if not facts or len(facts) < 2:
        return None
        
    facts_str = "\n\n".join([f"Fact {i+1} (Source: {f.source_document}): {f.fact_statement} | Evidence: {f.evidence_quote}" for i, f in enumerate(facts)])
    
    prompt = f"""
    You are an expert fact-checker analyzing a cluster of potentially related facts extracted from different documents.
    
    Here are the facts:
    {facts_str}
    
    Your task is to determine the relationship between these facts. The relationship MUST be exactly one of the following three:
    1. "Corroboration": The facts agree with each other or state the same thing (even if worded differently).
    2. "Contradiction": The facts genuinely conflict with each other.
    3. "Contextual Contradiction": The facts appear to contradict, but can be explained by context (e.g., different timeframes, different scopes, different units).
    
    Return the response ONLY as a JSON object with this exact schema:
    {{
      "relationship_type": "string",
      "summary": "string explaining reasoning"
    }}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        import json
        import uuid
        data = json.loads(response.text)
        
        # Override cluster_id and facts to ensure consistency
        data["cluster_id"] = str(uuid.uuid4())
        data["facts"] = [f.model_dump() for f in facts]
        
        return ClusterAnalysis(**data)
    except Exception as e:
        print(f"Error during reconciliation: {e}")
        return None
