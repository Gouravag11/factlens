import google.generativeai as genai
from models import ExtractedFacts
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# Use flash for speed and cost-effectiveness as requested
model = genai.GenerativeModel('gemini-3.5-flash-lite')
embed_model = 'models/gemini-embedding-2'

def extract_facts_from_document(pages: list, source_document: str) -> ExtractedFacts:
    """Extracts facts from the entire document in one go using Gemini."""
    if not API_KEY:
        print("Warning: GEMINI_API_KEY not set. Returning empty facts.")
        return ExtractedFacts(facts=[])

    # Combine all pages into a single formatted string
    full_text = ""
    for page in pages:
        full_text += f"\n\n--- Page {page['page_number']} ---\n{page['text']}"

    prompt = f"""
    Analyze the following text from a document named '{source_document}'. The text contains multiple pages separated by '--- Page X ---' markers.
    Extract AS MANY meaningful numerical or semantic facts AS POSSIBLE. Be highly exhaustive. Do not summarize; extract at least 25-50 distinct facts if the document is long enough. 
    Focus on all available metrics, dates, financial data, strategic goals, risks, entity mentions, and factual statements. Leave no stone unturned.
    For each fact, you MUST extract the exact quote from the text that serves as evidence, and the page number it was found on.
    
    Return the response ONLY as a JSON object with this exact schema:
    {{
      "facts": [
        {{
          "fact_statement": "string",
          "metric_or_subject": "string",
          "value": "string or null",
          "timeframe": "string or null",
          "evidence_quote": "string",
          "page_number": 1
        }}
      ]
    }}
    
    Document Text:
    {full_text}
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
        import re
        raw_text = response.text
        
        # 1. Pre-clean trailing commas (common LLM error)
        raw_text = re.sub(r',\s*]', ']', raw_text)
        
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as jde:
            print(f"Initial JSON parse failed: {jde}. Using bulletproof object extractor...")
            # 2. Extract individual valid objects ignoring surrounding array/syntax errors
            salvaged_facts = []
            depth = 0
            start = -1
            in_string = False
            escape = False
            
            for i, char in enumerate(raw_text):
                if escape:
                    escape = False
                    continue
                if char == '\\':
                    escape = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                    
                if not in_string:
                    if char == '{':
                        if depth == 0:
                            start = i
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0 and start != -1:
                            obj_str = raw_text[start:i+1]
                            try:
                                # Clean trailing commas in object
                                obj_str = re.sub(r',\s*}', '}', obj_str)
                                obj = json.loads(obj_str)
                                if "fact_statement" in obj:
                                    salvaged_facts.append(obj)
                            except:
                                pass # Skip only this broken object
                            start = -1
                            
            if salvaged_facts:
                print(f"Successfully rescued {len(salvaged_facts)} facts from malformed JSON!")
                data = {"facts": salvaged_facts}
            else:
                print("Total JSON failure. Could not salvage any facts.")
                data = {"facts": []}
        
        valid_facts = []
        failures = []
        import re
        norm_full_text = re.sub(r'\s+', '', full_text).lower()
        
        # Verify and add source_document to all facts
        for fact in data.get("facts", []):
            quote = fact.get("evidence_quote", "")
            norm_quote = re.sub(r'\s+', '', quote).lower()
            
            if norm_quote and norm_quote in norm_full_text:
                fact["source_document"] = source_document
                if "page_number" not in fact:
                    fact["page_number"] = 1
                valid_facts.append(fact)
            else:
                failures.append({
                    "fact_statement": fact.get("fact_statement", "Unknown fact"),
                    "evidence_quote": quote,
                    "source_document": source_document,
                    "reason": "Evidence quote hallucinated or altered by LLM."
                })
            
        print(f"Verified {len(valid_facts)} valid facts. Caught {len(failures)} hallucinations.")
        return ExtractedFacts(facts=valid_facts, failures=failures)
    except Exception as e:
        print(f"Error during extraction: {e}")
        return ExtractedFacts(facts=[], failures=[])

import time

def get_embeddings(texts: list) -> list:
    """Gets embeddings for a list of texts using the new Gemini API."""
    if not API_KEY or not texts:
        return [None] * len(texts)
        
    max_retries = 3
    base_delay = 5
    
    for attempt in range(max_retries):
        try:
            result = genai.embed_content(
                model=embed_model,
                content=texts,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            if "429" in str(e) or "exhausted" in str(e).lower():
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    print(f"Rate limit hit during embedding. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    print(f"Error getting embeddings after {max_retries} attempts: {e}")
                    return [None] * len(texts)
            else:
                print(f"Error getting embeddings: {e}")
                return [None] * len(texts)
