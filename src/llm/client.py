import os
import json
import re
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class LLMClient:
    def __init__(self, model: str = "gemini-1.5-pro"):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("⚠️ GOOGLE_API_KEY not set in .env file")
        
        self.model = model
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        self.headers = {"Content-Type": "application/json"}

        today = date.today()
        self.date_context = {
            "today": today.strftime("%Y-%m-%d"),
            "7_days_ago": (today - timedelta(days=7)).strftime("%Y-%m-%d"),
            "30_days_ago": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
            "90_days_ago": (today - timedelta(days=90)).strftime("%Y-%m-%d"),
            "365_days_ago": (today - timedelta(days=365)).strftime("%Y-%m-%d"),
        }

    def _call(self, prompt: str) -> str:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        response = requests.post(
            f"{self.base_url}?key={self.api_key}",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return re.sub(r"^```(json)?\s*|\s*```$", "", text.strip())

    def preprocessing(self, query: str) -> dict:
        p = self.date_context
        prompt = f"""
You are a natural language understanding agent that interprets user queries about GitHub repositories.

Given a user query, extract and return a strict, valid JSON object with the following structure:

{{
  "intent": "search_repository",
  "filters": {{
    "language": "<language_or_null>",
    "libraries": ["<libraries_or_empty_array>"],
    "created_after": "<yyyy-mm-dd_or_null>",
    "created_before": "<yyyy-mm-dd_or_null>",
    "stars_min": <number_or_null>,
    "topics": ["<topics_or_empty_array>"]
  }},
  "query_vector_required": <true_or_false>,
  "rewritten_query": "<concise, accurate version of the user's query>"
}}

Guidelines:
- "popular", "top", "nổi tiếng" → stars_min = 500
- "recent" → created_after = {p["90_days_ago"]}
- "last week" → created_after = {p["7_days_ago"]}, created_before = {p["today"]}
- "last month" → created_after = {p["30_days_ago"]}
- "last year" → created_after = {p["365_days_ago"]}

User query: "{query}"

**Only return valid JSON. No explanation.**
""".strip()

        try:
            raw = self._call(prompt)
            return json.loads(raw)
        except Exception as e:
            print("⚠️ Preprocessing failed:", e)
            return {
                "intent": "search_repository",
                "filters": {
                    "language": None,
                    "libraries": [],
                    "created_after": None,
                    "created_before": None,
                    "stars_min": None,
                    "topics": []
                },
                "query_vector_required": True,
                "rewritten_query": ""
            }

    def generate_filter_chips(self, query: str) -> list:
        prompt = f"""
You are a filter suggestion assistant for a GitHub repository search interface.

Given a vague or broad user query (e.g. "AI", "Python", "machine learning"), return 5 short, distinct, and clickable filter chips that help refine search results.

Rules:
- Filters must not repeat the original query.
- Max 6 words per chip.
- Return empty list if the query is already very specific.

Output format:
{{"related_queries": ["chip1", "chip2", ...]}}

User query: "{query}"
""".strip()

        try:
            raw = self._call(prompt)
            data = json.loads(raw)
            return data.get("related_queries", [])
        except Exception as e:
            print("⚠️ Filter chip generation failed:", e)
            return []

if __name__ == "__main__":
    client = LLMClient()
    query = input("💬 Enter your GitHub query: ")

    print("\n🎯 Filter Chips:")
    print(json.dumps(client.generate_filter_chips(query), indent=2, ensure_ascii=False))

    print("\n🧠 Preprocessed Query:")
    print(json.dumps(client.preprocessing(query), indent=2, ensure_ascii=False))
