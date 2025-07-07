from datetime import datetime

def get_field(doc, field):
    # Prefer meta_data, fallback to top-level
    if "meta_data" in doc and field in doc["meta_data"]:
        return doc["meta_data"][field]
    return doc.get(field, None)

def sort_results_by_boosted_score(results):
    today = datetime.today()

    for r in results:
        # Robustly get stars and date
        stars = get_field(r, "stars") or 0
        date_str = get_field(r, "date") or r.get("date", "2024-01-01")
        if "T" in date_str:
            date_str = date_str.split("T")[0]  # removes time and 'Z'
        try:
            created_date = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            created_date = today

        days_since_release = max((today - created_date).days, 1)
        boosted_score = stars / days_since_release

        search_score = r.get("@search.score") or 0  # fallback if missing
        final_score = 0.8 * search_score + 0.2 * boosted_score

        r["boosted_score"] = boosted_score
        r["final_score"] = final_score

        print(f"[{r.get('title')}] stars: {stars}, created day: {date_str}, days: {days_since_release}, boosted_score: {boosted_score:.4f}, final_score: {final_score:.4f}")
    print(today)
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


if __name__== "__main__":
    # Fixed test data: both results have meta_data
    result = [
    {
      "@search.score": 9.223912,
      "id": "884740226",
      "title": "Azure-Document-Processing-RAG-API",
      "short_des": "Azure Function: Rag doc store & search",
      "tags": [],
      "date": "2024-11-07T09:57:27Z",
      "stars": 8,
      "owner": "jvgriethuijsen",
      "url": "https://github.com/jvgriethuijsen/Azure-Document-Processing-RAG-API",
      "score": 0
    },
    {
      "@search.score": 9.106634,
      "id": "679478067",
      "title": "azure-search-comparison-tool",
      "short_des": "A demo app showcasing Vector Search using Azure AI Search, Azure OpenAI for text embeddings, and Azure AI Vision for image embeddings.",
      "tags": [
        "azure",
        "azurecognitivesearch",
        "azureopenai",
        "openai",
        "semanticsearch",
        "vectors",
        "visionai"
      ],
      "date": "2023-08-17T00:05:25Z",
      "stars": 74,
      "owner": "Azure-Samples",
      "url": "https://github.com/Azure-Samples/azure-search-comparison-tool",
      "score": 0
    },
    {
      "@search.score": 8.829607,
      "id": "919366546",
      "title": "Azure-openai-Realtime-RAG-twilio-phone",
      "short_des": "Azure Ppenai Realtime with Azure AI Search RAG and twilio phone",
      "tags": [],
      "date": "2025-01-20T09:05:15Z",
      "stars": 7,
      "owner": "Shailender-Youtube",
      "url": "https://github.com/Shailender-Youtube/Azure-openai-Realtime-RAG-twilio-phone",
      "score": 0
    },
    ]
    sort_results_by_boosted_score(result)
