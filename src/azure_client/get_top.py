import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from azure_client.config import search_client

def get_top_k_by_date(top_k: int):
    results = search_client.search(
        search_text="*",                
        order_by=["date desc"],        # Sort by most recent date
        top=top_k
    )

    return results

    # print(f"\nTop {top_k} most recent documents:")
    # for result in results:
    #     title = result.get("title", "<No title>")
    #     date = result.get("date", "N/A")
    #     print(f"- {title}: 📅 {date}")

if __name__ == "__main__":
    for i in get_top_k_by_date(5):
         print(f"- {i['title']}: 📅 {i['date']}")

