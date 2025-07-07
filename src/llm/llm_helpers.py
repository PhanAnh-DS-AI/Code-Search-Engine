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
from  openai import AzureOpenAI
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== PATH SETUP =====
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# from langchain_mistralai import ChatMistralAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.llm.utils import github_text_search, format_example_for_prompt


# ===== ENV =====
load_dotenv()
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')

# ===== PREPROCESS QUERY =====
def preprocess_query(query: str) -> str:
    query = query.lower()
    query = re.sub(rf"[{re.escape(string.punctuation)}]", " ", query)
    query = re.sub(r"[^\w\s]", "", query, flags=re.UNICODE)
    query = re.sub(r"\s+", " ", query).strip()
    return query

# ===== CONFIG LLM =====
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.1-8b-instant",  
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
        # Handle different types of result.content
        if isinstance(result.content, str):
            parsed = json.loads(result.content)  
        elif isinstance(result.content, list):
            # If it's a list, try to get the first string element
            content_str = next((item for item in result.content if isinstance(item, str)), "")
            parsed = json.loads(content_str) if content_str else {"label": False, "reason": "Invalid response format"}
        else:
            parsed = {"label": False, "reason": f"Unexpected content type: {type(result.content)}"}
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

# ===== PROMPT: AGENT INTENT QUERY FOR CACHE =====
def agent_intent_query(query: str) -> dict:
    """
    Calls LLM to extract intent and reasoning from a query.
    Returns a dict with 'intent' and 'reasoning' fields.
    """
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate(
            prompt=PromptTemplate.from_file(os.path.join(BASE_DIR, "prompt_helpers", "agent_intent_query.txt"), encoding="utf-8")
        ),
        HumanMessagePromptTemplate(
            prompt=PromptTemplate.from_template("Given the input query: {query}")
        )
    ])
    
    # llm_agent = ChatMistralAI(
    #     api_key=MISTRAL_API_KEY,
    #     model_name="mistral-small-latest",
    #     temperature=0.5,
    #     max_tokens=256,
    #     top_p=0.95
    # )
    
    chain = prompt | llm | parser
    result = chain.invoke({"query": query})
    return result



def llm_generate_shortdes(repo_name: str, repo_topics=None, repo_readme: str = "") -> str:
    """
    Generate a short English description for a GitHub repository using Groq.
    Returns JSON format with 'short_des' field.
    """
    # Create a comprehensive prompt for better description generation
    prompt = f"""
You are an expert at analyzing GitHub repositories and creating concise, informative descriptions.

Given the following repository information, generate a short, engaging description that explains what the repository does and its main purpose.

Repository Information:
- Name: {repo_name}
- Topics: {', '.join(repo_topics) if repo_topics else 'None specified'}
- README Preview: {repo_readme[:800] if repo_readme else 'No README available'}

Requirements:
1. Create a description that is 1-2 sentences long (max 200 characters)
2. Focus on the main functionality and purpose
3. Use clear, technical language
4. Make it engaging for developers
5. If no README is available, infer from the name and topics

Return ONLY a JSON object with this exact format:
{{
    "short_des": "Your generated description here"
}}

Example output:
{{
    "short_des": "A modern code editor built with TypeScript for building and debugging web applications."
}}
"""
    
    try:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not available")
            
        # Use Groq for description generation
        groq_llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model="llama-3.1-8b-instant",
            temperature=0.3  # Lower temperature for more consistent output
        )
        
        # Get response from Groq
        response = groq_llm.invoke(prompt)
        
        # Handle different response formats
        if hasattr(response, 'content'):
            content = response.content
            # Handle case where content might be a list
            if isinstance(content, list):
                content = str(content)
        else:
            content = str(response)
        
        # Parse JSON response
        try:
            # Clean up the response if it contains markdown code blocks
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            # Parse JSON
            result = json.loads(content)
            
            # Extract short_des field
            if 'short_des' in result:
                return result['short_des']
            else:
                logger.warning(f"Response missing 'short_des' field: {result}")
                return f"Repository: {repo_name}"
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}. Response: {content}")
            # Fallback: try to extract description from response
            if isinstance(content, str) and 'short_des' in content:
                # Try to extract the value after "short_des":
                import re
                match = re.search(r'"short_des":\s*"([^"]+)"', content)
                if match:
                    return match.group(1)
            
            # Last resort fallback
            return f"Repository: {repo_name}"
        
    except Exception as e:
        logger.error(f"Groq description generation failed: {e}")
        return f"Repository: {repo_name}"

if __name__ == "__main__":
    short_des = llm_generate_shortdes(
    repo_name="awesome-semantic-search",
    repo_topics=["semantic search", "vector database"],
    repo_readme="This repo contains code and docs for semantic search using Qdrant and Azure AI..."
)

    print(short_des)
