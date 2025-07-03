import os
import sys
import re
import string
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from enum import Enum
from typing import Tuple, List
from datetime import timedelta, date
from langchain_core.messages import get_buffer_string

# ===== PATH SETUP =====
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.utils import github_text_search, format_example_for_prompt


# ===== ENV =====
load_dotenv()
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

# ===== PREPROCESS QUERY =====
def preprocess_query(query: str) -> str:
    query = query.lower()
    query = re.sub(rf"[{re.escape(string.punctuation)}]", " ", query)
    query = re.sub(r"[^\w\s]", "", query, flags=re.UNICODE)
    query = re.sub(r"\s+", " ", query).strip()
    return query

# ===== CONFIG LLM =====
llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model_name="llama-3.1-8b-instant",  
    temperature=0.5
)

parser = JsonOutputParser()

# ===== PYDANTIC SCHEMAS =====
class SearchMethodEnum(str, Enum):
    full_text = "full-text-search"
    vector = "vector-search"
    hybrid = "hybrid-search"

class SearchMethodRequest(BaseModel):
    search_method: SearchMethodEnum

class RelatedQueries(BaseModel):
    related_queries: List[str]

# ===== PROMPT: LLM PREPROCESS =====
prompt_method = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_file(os.path.join(BASE_DIR, "prompt_helpers", "llm_fielter_process.txt"), encoding="utf-8")
    ),
    HumanMessagePromptTemplate(
        prompt=PromptTemplate.from_template("Query: {query}")
    )
])

def llm_preprocess(query: str) -> Tuple[str, dict]: 
    current_date = date.today()
    formatted_current_date = current_date.strftime("%Y-%m-%d")
    date_7_days_ago = (current_date - timedelta(days=7)).strftime("%Y-%m-%d")
    date_30_days_ago = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
    date_90_days_ago = (current_date - timedelta(days=90)).strftime("%Y-%m-%d")
    date_365_days_ago = (current_date - timedelta(days=365)).strftime("%Y-%m-%d")

    github_example = github_text_search(query, top_k=3)
    github_formatted_prompt = format_example_for_prompt(github_example)
    cleaned_query = preprocess_query(query)

    input_vars = {
        "query": cleaned_query,
        "current_date_str": formatted_current_date, 
        "date_90_days_ago": date_90_days_ago,
        "date_7_days_ago": date_7_days_ago,
        "date_30_days_ago": date_30_days_ago,
        "date_365_days_ago": date_365_days_ago,
        "github_example": github_formatted_prompt
    }

    # Debug prompt
    formatted_prompt = prompt_method.format(**input_vars)


    chain = prompt_method | llm | parser
    result = chain.invoke(input_vars)

    # print("===== PROMPT INPUT TO LLM =====")
    # print(formatted_prompt) 
    return query, result

# ===== PROMPT: QUERY GENERATE RELATED =====
prompt_generate = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_file(os.path.join(BASE_DIR, "prompt_helpers", "query_generate.txt"), encoding="utf-8")
    ),
    HumanMessagePromptTemplate(
        prompt=PromptTemplate.from_template("Given the input query: '{query}'")
    )
])

def query_generate_related(query: str) -> Tuple[str, RelatedQueries]:
    cleaned_query = preprocess_query(query)
    chain = prompt_generate | llm | parser

    raw_result = chain.invoke({"query": cleaned_query})

    # print("🔍 Raw result from LLM (query_generate_related):", raw_result)
    # print("📄 Type of result:", type(raw_result))

    if isinstance(raw_result, str):
        try:
            parsed_result = json.loads(raw_result)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse result as JSON: {e}")
    elif isinstance(raw_result, dict):
        parsed_result = raw_result
    else:
        raise ValueError(f"Unsupported result type: {type(raw_result)}")

    if "related_queries" not in parsed_result:
        raise ValueError(f"'related_queries' key not found in: {parsed_result}")

    related_request = RelatedQueries(related_queries=parsed_result["related_queries"])
    return query, related_request

# ===== PROMPT: FILTER GENERATION =====
prompt_filter = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_file(os.path.join(BASE_DIR, "prompt_helpers", "filter_generate.txt"), encoding="utf-8")
    ),
    HumanMessagePromptTemplate(
        prompt=PromptTemplate.from_template("Given the input query: {query}")
    )
])

def llm_filter_generate(query: str) -> RelatedQueries:
    cleaned_query = preprocess_query(query)
    chain = prompt_filter | llm | parser
    result = chain.invoke({"query": cleaned_query})
    return result

# ===== PROMPT: EVALUATION =====
evaluation_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_file(os.path.join(BASE_DIR, "prompt_helpers", "llm_evaluate_process.txt"), encoding="utf-8")
    )
])

def evaluate_rewrite(original_query: str, rewritten_query: str) -> Tuple[bool, str]:
    if not rewritten_query.strip():
        return False, "Rewritten query is empty, likely too vague or generic."

    chain = evaluation_prompt | llm  
    result = chain.invoke({
        "original_query": original_query,
        "rewritten_query": rewritten_query
    })

    try:
        parsed = json.loads(result.content)  
        return parsed["label"], parsed["reason"]
    except Exception as e:
        return False, f"LLM evaluation failed: {str(e)}"

# ===== BATCH RUN FOR EVALUATION =====
def run_batch(json_file_path: str):
    with open(json_file_path, "r", encoding="utf-8") as f:
        test_items = json.load(f)

    results = []

    for item in test_items:
        query_id = item.get("id")
        query_text = item.get("query")

        print(f"🟡 Processing (ID {query_id}): {query_text}")
        original, output = llm_preprocess(query_text)
        rewritten_query = output.get("rewritten_query", "")

        try:
            label, thinking = evaluate_rewrite(original, rewritten_query)
        except Exception as e:
            label = False
            thinking = f"LLM evaluation failed: {str(e)}"

        result = {
            "id": query_id,
            "original_query": original,
            "rewritten_query": rewritten_query,
            "true_label": label,
            "llm_evaluate_think": thinking,
            "llm_output": output
        }

        results.append(result)

        print(f"✅ Query: {original}")
        print(f"🔁 Rewritten: {rewritten_query}")
        print(f"🧠 LLM Thinking: {thinking}")
        print(f"🏷️ Label: {'True' if label else 'False'}")
        print("-" * 50)

    with open("llm_rewrite_evaluation_v2.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results

# ===== MANUAL TESTING =====
if __name__ == "__main__":
    query = "Azure AI search engine with python and pytorch more than 100 stars in 2024"

    query_related, result = llm_preprocess(query)
    print("Print Result:", result)
