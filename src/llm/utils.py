import os
import sys
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.azure_client.config import github_ex_client, model
from typing import List, Dict, Any
import re

from src.llm.client import LLMClient

client = LLMClient()

def normalize_query(query: str) -> str:
    query = query.strip().lower()
    return re.sub(r'\s+', ' ', query) 

def github_text_search(query: str, top_k: int = 3) -> List[Dict[str,Any]]:
    results = github_ex_client.search(search_text=normalize_query(query), top=top_k)
    example_result =[]
    for result in results:
        example_result.append(result)
    return example_result

def format_example_for_prompt(examples: List[Dict[str, Any]]) -> str:
    prompt_blocks = []
    
    for i, ex in enumerate(examples, start=1):
        llm_output = ex.get("llm_output", {})
        filters = llm_output.get("filters", {})

        formatted_filters = "\n".join([
            f"- {key.replace('_', ' ').capitalize()}: {value if value else 'None'}"
            for key, value in filters.items()
        ])

        block = f"""### Example {i}:
        Original query: {ex.get('original_query', 'N/A')}
        LLM Thinking: {llm_output.get('llm_thinking', 'N/A')}
        Rewritten query: {llm_output.get('rewritten_query', 'N/A')}
        Filters:
        {formatted_filters}
        """
        prompt_blocks.append(block)

    return "\n---\n".join(prompt_blocks)


def filter_results(results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    created_after = filters.get("created_after")
    created_before = filters.get("created_before")
    stars_min = filters.get("stars_min")

    def parse_date(date_str):
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        except Exception:
            return None

    after_date = parse_date(created_after) if created_after else None
    before_date = parse_date(created_before) if created_before else None

    filtered = []
    for item in results:
        created_at = parse_date(item.get("date", ""))
        stars = item.get("meta_data", {}).get("stars", 0)

        if after_date and (not created_at or created_at < after_date):
            continue

        if before_date and (not created_at or created_at > before_date):
            continue

        if stars_min is not None and (stars is None or stars < stars_min):
            continue

        filtered.append(item)

    return filtered

def parse_user_query(search_query: str) -> dict:
    parsed = client.preprocessing(search_query)
    return {
        "final_query": parsed.get("rewritten_query", search_query).strip(),
        "query_vector_required": parsed.get("query_vector_required", True),
        "filters": parsed.get("filters", {}),
        "raw_output": parsed
    }


def suggest_filter(query: str):
    try:
        return {"related_queries": client.generate_filter_chips(query)}
    except Exception as e:
        print(f"⚠️ Failed to suggest filters: {e}")
        return {"related_queries": []}
    
if __name__ == "__main__":
    results = github_text_search(query="Ai machine learning")
    formatted_prompt = format_example_for_prompt(results)
    print(formatted_prompt)