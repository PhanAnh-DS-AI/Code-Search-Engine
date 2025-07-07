import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import streamlit as st
from urllib.parse import quote
from utils import perform_search, call_text_search

# ================== CSS ===================
st.markdown("""
<style>
.card {
    background-color: #fff;
    border: 1px solid #e1e4e8;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(27,31,35,0.04);
}
.card a {
    font-size: 20px;
    font-weight: bold;
    color: #0366d6;
    text-decoration: none;
}
.card a:hover {
    text-decoration: underline;
}
.card .desc {
    font-size: 16px;
    color: #586069;
    margin: 4px 0 8px 0;
}
.card .meta {
    font-size: 14px;
    color: #586069;
    margin-top: 8px;
}
.tag {
    display: inline-block;
    background-color: #f1f8ff;
    color: #0366d6;
    border: 1px solid #d1d5da;
    border-radius: 2em;
    padding: 4px 10px;
    font-size: 13px;
    margin-right: 6px;
}
.card .tag {
    font-weight: normal !important;
    text-decoration: none;
    font-size: 13px;
}
.element-container:has(#button-after) + div button {
    background-color: white !important;
    color: #0366d6 !important;
    border: 1px solid rgba(27, 31, 35, 0.15) !important;
    border-radius: 6px !important;
    padding: 6px 16px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    display: block !important;
    margin: 0 auto !important;
}
.element-container:has(#button-after) + div button:hover {
    background-color: #0366d6 !important;
    color: white !important;
}
.stTextInput>div>input { border-radius: 5px; border: 1px solid #d1d5da; padding: 8px; }
.stButton>button { background-color: #28a745; color: white; border-radius: 5px; padding: 8px 16px; }

/* Filter buttons */
button[kind="secondary"] {
    background-color: #1e1e1e !important;
    color: white !important;
    border-radius: 20px !important;
    padding: 4px 12px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    border: 1px solid #444 !important;
    white-space: nowrap !important;
    margin-right: 3px !important;
}
button[kind="secondary"]:hover {
    background-color: #333 !important;
    color: #fff !important;
}

/* column layout fix */
div[data-testid="stColumn"] {
    width: fit-content !important;
    flex: unset;
}
div[data-testid="stColumn"] * {
    width: fit-content !important;
}

/* filter bar spacing */
.scrolling-wrapper {
    position: relative;
    overflow-x: auto;
    display: flex;
    flex-wrap: nowrap;
    gap: 8px;
    padding: 10px 0;
    margin-top: 0;
    margin-bottom: 0;
    scrollbar-width: thin;
    scrollbar-color: #666 transparent;
    width: 100%;
}
.scrolling-wrapper::-webkit-scrollbar {
    height: 6px;
}
.scrolling-wrapper::-webkit-scrollbar-thumb {
    background-color: #666;
    border-radius: 5px;
}
</style>
""", unsafe_allow_html=True)

# ================== HELPERS ===================
def normalize_result(result: dict, source: str) -> dict:
    if source in {"vector"}:
        return {"payload": result.get("payload", {}), "score": result.get("score", None)}
    elif source in {"full-text", "tag", "hybrid"}:
        return {"payload": result, "score": result.get("score", None)}
    else:
        raise ValueError("Unknown result source")

def display_result(result):
    if isinstance(result, list):
        result = result[0] if result else {}

    if not isinstance(result, dict):
        st.warning("⚠️ Invalid result format")
        return

    payload = result.get("payload", {})
    if isinstance(payload, list):
        payload = payload[0] if payload else {}

    title = payload.get("title", "No Title")
    url = payload.get("url", "#")
    description = payload.get("short_des", "")
    tags = payload.get("tags", [])
    owner = payload.get("owner", "N/A")
    stars = payload.get("stars", 0)
    date = payload.get("date", "N/A")
    score = payload.get("final_score", 0)
    
    tag_html = "".join([
        f"<a href='?search_query={quote(tag)}&search_method=tag' class='tag'>#{tag}</a>"
        for tag in tags if tag.strip().lower() != "(none)"
    ])
    score_html = f"• Score: {score:.2f}" if score is not None else ""

    card_html = f"""
    <div class="card">
        <a href="{url}" target="_blank">{title}</a>
        <div class="desc">{description}</div>
        <div>{tag_html}</div>
        <div class="meta">
            👤 <strong>{owner}</strong> &nbsp;|&nbsp; ⭐ <strong>{stars}</strong> &nbsp;|&nbsp; 📅 <strong>{date}</strong> &nbsp;|&nbsp; 📈 {score_html}
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

def get_field(doc, field):
    # Prefer meta_data, fallback to top-level
    if "meta_data" in doc and field in doc["meta_data"]:
        return doc["meta_data"][field]
    return doc.get(field, None)

# ================== MAIN ===================
st.header("🔍 Search Engine")

query_params = st.query_params
query_from_url = "search_query" in query_params

if query_from_url and not st.session_state.get("search_submitted", False):
    st.session_state.search_query = query_params["search_query"].strip()
    st.session_state.search_method = query_params.get("search_method", "tag")
    st.session_state.limit = 5
    st.session_state.search_submitted = True
    st.rerun()

# ================== FORM ===================
if not query_from_url:
    with st.form(key="search_form"):
        search_query = st.text_input("Search Query", max_chars=128)
        submit_button = st.form_submit_button("Search")
        if submit_button:
            if not search_query.strip():
                st.error("Please enter a search query.")
            else:
                search_query_clean = search_query.strip()
                st.session_state.search_query = search_query_clean
                st.session_state.search_method = "hybrid-search"
                st.session_state.active_filter = "Most Relevant" 
                perform_search(search_query_clean, "hybrid-search", {
                    "full-text-search": "fulltext",
                    "vector-search": "vector",
                    "hybrid-search": "hybrid",
                    "tag": "tag"
                })
                st.session_state.search_submitted = True
                st.rerun()

# ================== FILTER BAR ===================
if st.session_state.get("search_submitted", False):
    default_filters = ["Most Relevant", "Most Starred", "Fewest Starred", "Recently Updated", "Oldest Repos", ]
    llm_filters = st.session_state.get("hybrid_filter_suggestions", [])
    filters = default_filters + llm_filters
    query = st.session_state.get("search_query", "")

    #st.markdown('<div class="scrolling-wrapper">', unsafe_allow_html=True)
    filter_columns = st.columns(len(filters), gap="small")

    for i, (col, filter_option) in enumerate(zip(filter_columns, filters)):
        with col:
            is_default = filter_option in default_filters
            is_active = st.session_state.get("active_filter") == filter_option if is_default else False
            label = f"✅ {filter_option}" if is_active else filter_option

            if st.button(label, key=f"filter_{i}"):
                if is_default:
                    st.session_state.active_filter = None if is_active else filter_option
                    st.rerun()
                else:
                    st.session_state.search_submitted = False
                    st.session_state.search_query = filter_option
                    result, _ = call_text_search(query=filter_option, limit=5)
                    display_result(result)
                    st.session_state.search_submitted = True
                    st.session_state.active_filter = None
                    st.rerun()

# ================== DISPLAY RESULTS ===================
if st.session_state.get("search_submitted", False):
    search_query = st.session_state.search_query
    search_method = st.session_state.search_method
    method_key_map = {
        "full-text-search": "fulltext",
        "vector-search": "vector",
        "hybrid-search": "hybrid",
        "tag": "tag"
    }
    key_prefix = method_key_map.get(search_method)
    source = search_method.replace("-search", "") if search_method != "tag" else "tag"

    if f"{key_prefix}_all_results" not in st.session_state:
        perform_search(search_query, search_method, method_key_map)

    elapsed_ms = st.session_state.get(f"{key_prefix}_elapsed_ms", 0)
    all_results = st.session_state.get(f"{key_prefix}_all_results", [])
    visible_limit = st.session_state.get(f"{key_prefix}_visible_limit", 5)
    max_limit = 25

    raw_results = all_results[:min(visible_limit, max_limit, len(all_results))]
    active_filter = st.session_state.get("active_filter", "")

    if active_filter and raw_results:
        if active_filter == "Most Starred":
            raw_results = sorted(raw_results, key=lambda r: get_field(r, "stars"), reverse=True)
        elif active_filter == "Fewest Starred":
            raw_results = sorted(raw_results, key=lambda r: get_field(r, "stars"))
        elif active_filter == "Recently Updated":
            raw_results = sorted(raw_results, key=lambda r: get_field(r, "date"), reverse=True)
        elif active_filter == "Oldest Repos":
            raw_results = sorted(raw_results, key=lambda r: get_field(r, "date"))
        elif active_filter == "Most Relevant":
            raw_results = sorted(raw_results, key=lambda r: get_field(r, "score"), reverse=True)

    st.caption(f"🔍 Search completed in {elapsed_ms} ms.")

    if raw_results:
        title_map = {
            "full-text": "📝 Full-text results for",
            "vector": "🧠 Vector results for",
            "hybrid": "⚡ Results for",
            "tag": "🏷️ Repositories with tag"
        }
        tag_display = f"<span style='display:inline-block; background-color:#dafbe1; color:#116329; border:1px solid #b7ebc0; border-radius:2em; padding:3px 10px; font-size:20px;'>#{search_query}</span>" \
            if source == "tag" else \
            f"<span style='color:#0366d6; font-weight: bold; font-size:20px;'>{search_query}</span>"
        st.markdown(f"<h4>{title_map[source]} {tag_display}</h4>", unsafe_allow_html=True)

        for raw_result in raw_results:
            normalized = normalize_result(raw_result, source)
            display_result(normalized)

        st.markdown('<span id="button-after"></span>', unsafe_allow_html=True)
        if visible_limit < len(all_results) and visible_limit < max_limit:
            if st.button("Show more", key=f"{key_prefix}_show_more"):
                st.session_state[f"{key_prefix}_visible_limit"] = visible_limit + 5
                st.rerun()

        st.markdown(
            "<div style='text-align:center; color: gray;'>Only display a maximum of 25 results.</div>",
            unsafe_allow_html=True
        )
    else:
        st.warning("No results found.")
