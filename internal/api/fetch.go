package api

import (
	"code-semantic-search/internal/data"
	"code-semantic-search/internal/github"
	"code-semantic-search/internal/qdrant"
	"fmt"
	"log"
	"net/http"
)

func FetchDataHandler(w http.ResponseWriter, r *http.Request, qClient *qdrant.QdrantClient) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	client := github.NewGitHubClient()
	log.Println("⏳ Fetching repos from GitHub...")
	repos, err := client.SearchDiverseRepos()
	if err != nil {
		http.Error(w, fmt.Sprintf("❌ GitHub fetch error: %v", err), http.StatusInternalServerError)
		return
	}

	log.Printf("ℹ️ Found %d repos.", len(repos))
	err = data.CollectRepoDataAndStoreMany(CollectionName, qClient, repos)
	if err != nil {
		http.Error(w, fmt.Sprintf("❌ Failed to store data: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("✅ Data fetched and stored into Qdrant and Elasticsearch."))
}

func SyncQdrantToElasticsearchHandler(w http.ResponseWriter, r *http.Request, qClient *qdrant.QdrantClient) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	log.Println("⏳ Starting sync from Qdrant to Elasticsearch...")

	err := data.SyncQdrantToElasticsearch(CollectionName, qClient)
	if err != nil {
		http.Error(w, fmt.Sprintf("❌ Sync error: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("✅ Data synced from Qdrant to Elasticsearch successfully."))
}
