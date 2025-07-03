from datetime import datetime

def sort_results_by_boosted_score(results):
    today = datetime.today()

    for r in results:
        meta = r.get("meta_data", {})  # directly from r
        date_str = r.get("date", "2024-01-01")
        stars = meta.get("stars", 0)
        if "T" in date_str:
            date_str = date_str.split("T")[0]  # removes time and 'Z'
        try:
            created_date = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            created_date = today

        days_since_release = max((today - created_date).days, 1)
        bidst_score = stars / days_since_release

        search_score = r.get("@search.score")  # fallback if missing
        final_score = 0.8 * search_score + 0.2 * bidst_score

        r["bidst_score"] = bidst_score
        r["final_score"] = final_score

        print(f"[{r.get('title')}] stars: {stars}, created day: {date_str}, days: {days_since_release}, bidst_score: {bidst_score:.4f}, final_score: {final_score:.4f}")
    print(today)
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


if __name__== "__main__":
    result=[{
    "id": "00704f7f-619c-5424-b0cf-2e3c689b8ad6",
    "date": "2022-11-16",
    "meta_data": {
        "stars": 1214,
        "owner": "nerfstudio-project",
        "url": "https://github.com/nerfstudio-project/viser",
        "id": 566568196
    },
    "title": "viser",
    "tags": [
        "python",
        "visualization",
        "web"
    ],
    "short_des": "Web-based 3D visualization + Python",
    "vector": [
    ],
    "_rid": "g29pANUVp4ULAAAAAAAAAA==",
    "_self": "dbs/g29pAA==/colls/g29pANUVp4U=/docs/g29pANUVp4ULAAAAAAAAAA==/",
    "_etag": "\"45014f8b-0000-1800-0000-6840d1b40000\"",
    "_attachments": "attachments/",
    "_ts": 1749078452,
    "@search.score": 19.303852

}, {
      "short_des": "Semantic, lexical, multilingual search in your OGD metadata catalog.",
      "tags": [
        "ai",
        "hybrid-search",
        "machine-learning",
        "ogd",
        "openai",
        "opendata",
        "python",
        "semantic-search",
        "semanticsearch",
        "streamlit",
        "weaviate"
      ],
      "date": "2024-07-20T00:00:00Z",
      "vector": [
      ],
      "title": "ogd_ai-search",
      "rid": "ZzI5cEFOVVZwNFhZQWdBQUFBQUFBQT090",
      "meta_data": {
        "stars": 2,
        "owner": "machinelearningZH",
        "url": "https://github.com/machinelearningZH/ogd_ai-search",
        "id": 831329159
      },
      "@search.score": 19.303852
    }]
    sort_results_by_boosted_score(result)