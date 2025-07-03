import requests
import logging
import time
import streamlit as st
from typing import List, Dict, Any, Tuple, Callable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = ("http://localhost:8080")

def call_vector_search(query: str, limit: int = 25) -> Tuple[List[Dict[str, Any]], int]:
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/search/vector",
            json={"query": query, "limit": limit},
            timeout=10
        )
        response.raise_for_status()
        elapsed_ms = int((time.time() - start_time) * 1000)
        return response.json().get("result", []), elapsed_ms
    except requests.RequestException as e:
        logger.error(f"Error calling Vector search API: {e}")
        return [], 0

def call_text_search(query: str, limit: int = 25) -> Tuple[List[Dict[str, Any]], int]:
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/search/text",
            json={"query": query, "limit": limit},
            timeout=10
        )
        response.raise_for_status()
        elapsed_ms = int((time.time() - start_time) * 1000)
        return response.json().get("result", []), elapsed_ms
    except requests.RequestException as e:
        logger.error(f"Error calling Text Search API: {e}")
        return [], 0

def call_hybrid_search(query: str, limit: int = 25) -> Tuple[List[Dict[str, Any]], List[str], List[str], int]:
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/search/hybrid",
            json={"query": query, "limit": limit},
            timeout=10
        )
        response.raise_for_status()
        elapsed_ms = int((time.time() - start_time) * 1000)

        response_json = response.json()

        # Fallback: if "results" not present, try using "result"
        results = response_json.get("results")
        if results is None and "result" in response_json:
            result_data = response_json["result"]
            # Ensure result_data is list-like
            if hasattr(result_data, "__iter__") and not isinstance(result_data, dict):
                results = list(result_data)
            else:
                results = []
        #print("Results:", results)
        llm_filter = response_json.get("suggest_filter", [])
        suggested_topics = response_json.get("suggest_topic", [])

        return results, llm_filter, suggested_topics, elapsed_ms
    except requests.RequestException as e:
        logger.error(f"Error calling Hybrid Search API: {e}")
        return [], [], [], 0


def call_tag_search(query: str, limit: int = 25) -> Tuple[List[Dict[str, Any]], int]:
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/search/tag",
            json={"query": query, "limit": limit},
            timeout=10
        )
        response.raise_for_status()
        elapsed_ms = int((time.time() - start_time) * 1000)
        return response.json().get("result", []), elapsed_ms
    except requests.RequestException as e:
        logger.error(f"Error calling Tag Search API: {e}")
        return [], 0

def show_more_result(
    key_prefix: str,
    page_size: int = 5,
    max_limit: int = 25,
) -> List[Dict[str, Any]]:
    all_results_key = f"{key_prefix}_all_results"
    visible_limit_key = f"{key_prefix}_visible_limit"

    if all_results_key not in st.session_state:
        st.error("No cached results found. Please submit a search first.")
        return []

    all_results = st.session_state[all_results_key]

    if visible_limit_key not in st.session_state:
        st.session_state[visible_limit_key] = page_size

    visible_limit = st.session_state[visible_limit_key]
    visible_limit = min(visible_limit, max_limit, len(all_results))

    return all_results[:visible_limit]

def perform_search(search_query: str, search_method: str, method_key_map: Dict[str, str]) -> None:
    max_limit = 25
    key_prefix = method_key_map.get(search_method)

    if search_method == "full-text-search":
        all_results, elapsed_ms = call_text_search(search_query, max_limit)
    elif search_method == "vector-search":
        all_results, elapsed_ms = call_vector_search(search_query, max_limit)
    elif search_method == "hybrid-search":
        all_results, llm_filter, suggestion_topic, elapsed_ms = call_hybrid_search(search_query, max_limit)
        print("Filter:", llm_filter)
        print("Suggested topics:", suggestion_topic)

        st.session_state["hybrid_filter_suggestions"] = llm_filter or []
        st.session_state["hybrid_suggested_topics"] = suggestion_topic or []
    elif search_method == "tag":
        all_results, elapsed_ms = call_tag_search(search_query, max_limit)
    else:
        st.error("Unknown search method.")
        return

    st.session_state[f"{key_prefix}_all_results"] = all_results
    st.session_state[f"{key_prefix}_visible_limit"] = 5
    st.session_state[f"{key_prefix}_elapsed_ms"] = elapsed_ms

def call_recommendation(query: str = None, limit: int = 25):
    payload = {"limit": limit}
    if query:
        payload["query"] = query
    try:
        response = requests.post(f"{BASE_URL}/recommendations", json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("Error calling recommendation API:", e)
        return {}

def recommendation_result(result: dict):
    payload = result.get("payload", {}) if "payload" in result else result
    title = payload.get("title") or payload.get("repo_name") or "No Title"
    description = payload.get("short_des") or payload.get("description") or ""
    tags = payload.get("tags") or result.get("tags", [])
    meta = payload.get("meta_data", {})  
    url = meta.get("url", "#")
    owner = meta.get("owner", "N/A")
    stars = meta.get("stars", 0)
    date = payload.get("date") or result.get("date", "N/A")
    score = result.get("score", 0)

    tag_html = "".join([
        f"<span style='background-color:#e8f0fe; color:#1967d2; border-radius:16px; padding:4px 12px; margin-right:5px; font-size:13px; display:inline-block; margin-top:4px;'>#{tag}</span>"
        for tag in tags if tag.strip().lower() != "(none)"
    ])

    card_html = f"""
    <div style="
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        background-color: #ffffff;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    ">
        <a href="{url}" target="_blank" style="font-size:20px; font-weight:bold; color:#1a73e8; text-decoration:none;">{title}</a>
        <p style="margin:8px 0 12px 0; font-size:14px; color:#333;">{description}</p>
        <div style="margin-bottom:10px;">{tag_html}</div>
        <div style="font-size:13px; color:#555;">
            👤 <strong style="color:#6a1b9a;">{owner}</strong> &nbsp;|&nbsp;
            ⭐ <strong style="color:#f9a825;">{stars}</strong> &nbsp;|&nbsp;
            📅 <strong>{date}</strong> &nbsp;|&nbsp;
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
