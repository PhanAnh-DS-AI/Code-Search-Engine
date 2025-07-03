import os
import sys
import streamlit as st
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils import call_recommendation, recommendation_result, call_text_search

# ===== Lấy query param =====
query_params = st.query_params
if "search_query" in query_params:
    st.session_state["search_query"] = query_params["search_query"][0]
    st.session_state["search_submitted"] = query_params.get("search_submitted", ["false"])[0] == "true"

# ===== Tiêu đề chính =====
st.title("🔍 Repository Recommendations")

query = st.session_state.get("search_query", None)
search_submitted = st.session_state.get("search_submitted", False)

if "recommendation_data" not in st.session_state or (query and search_submitted):
    with st.spinner("Fetching recommendations..."):
        st.session_state["recommendation_data"] = call_recommendation(query=query, limit=5) if query and search_submitted else call_recommendation(limit=5)

data = st.session_state["recommendation_data"]
trending = data.get("trending", [])
popular = data.get("popular", [])
topics = data.get("topics", {})
suggested_filters = data.get("suggested_filters", [])
suggested_topic = st.session_state["hybrid_suggested_topics"] if "hybrid_suggested_topics" in st.session_state else []

tabs = st.tabs(["🔥 Trending", "🌟 Popular", "🧭 Topics"])

with tabs[0]:
    st.subheader("🔥 Trending Repositories")
    if trending:
        for repo in trending:
            recommendation_result(repo)
    else:
        st.info("No trending repositories available.")

with tabs[1]:
    st.subheader("🌟 Most Starred Repositories")
    if popular:
        for repo in popular:
            recommendation_result(repo)
    else:
        st.info("No popular repositories available.")

with tabs[2]:
    st.subheader("🧭 Topic-Based Recommendations")

    # Bỏ (none)
    filters = [f for f in suggested_filters if f != "(none)"]

    # ===== Cập nhật queue topic gần nhất từ hybrid_suggested_topics =====
    if "hybrid_suggested_topics" in st.session_state:
        if "recent_topics" not in st.session_state:
            st.session_state["recent_topics"] = []

        for topic in st.session_state["hybrid_suggested_topics"]:
            if topic not in st.session_state["recent_topics"]:
                st.session_state["recent_topics"].append(topic)

        # Giữ tối đa 10 topic
        st.session_state["recent_topics"] = st.session_state["recent_topics"][-10:]

    # ===== Lấy 5 topic đề xuất =====
    recent_topics = st.session_state.get("recent_topics", [])
    selected_topics = recent_topics[-5:] if len(recent_topics) >= 5 else recent_topics

    # Bổ sung random nếu thiếu
    needed = 5 - len(selected_topics)
    if needed > 0:
        candidates = [f for f in filters if f not in selected_topics]
        additional = random.sample(candidates, min(needed, len(candidates)))
        selected_topics += additional

    if not selected_topics:
        st.info("No topics available for recommendation.")
    else:
        for topic in selected_topics:
            st.markdown(f"#### 📌 Topic: {topic}")

            # Gọi full-text search theo topic
            with st.spinner(f"Searching repositories for topic '{topic}'..."):
                results, elapsed = call_text_search(topic, limit=5)

            if results:
                for res in results:
                    recommendation_result(res)
            else:
                st.info(f"No repositories found for topic '{topic}'.")

# Debug: check topic queue trong sidebar
# st.sidebar.write("🧠 Recent topics queue:", st.session_state.get("recent_topics", []))

