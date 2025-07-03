package main

import (
	"code-semantic-search/internal/api"
	"code-semantic-search/internal/elastic"
	"code-semantic-search/internal/hybrid"
	"code-semantic-search/internal/qdrant"
	"log"
	"net/http"
	"os"

	"github.com/joho/godotenv"
)

func main() {
	if err := godotenv.Load(); err != nil {
		log.Println("⚠️ Could not load .env, using system environment variables.")
	}

	elastic.InitElasticClient()
	qClient := qdrant.NewQdrantClient()
	if err := qClient.CreateCollectionIfNotExists(api.CollectionName, api.VectorDim); err != nil {
		log.Fatalf("❌ Failed to create Qdrant collection: %v", err)
	}

	searcher := &hybrid.HybridSearcher{
		Qdrant: qClient,
	}

	http.HandleFunc("/fetch_data", func(w http.ResponseWriter, r *http.Request) {
		api.FetchDataHandler(w, r, qClient)
	})
	http.HandleFunc("/search/vector", api.SearchHandler)
	http.HandleFunc("/search/text", api.FullTextSearchHandler)
	http.HandleFunc("/search/tag", api.HandleTagSearch)
	http.HandleFunc("/search/hybrid", api.HybridSearchHandler(searcher))
	http.HandleFunc("/sync/qdrant-to-es", func(w http.ResponseWriter, r *http.Request) {
		api.SyncQdrantToElasticsearchHandler(w, r, qClient)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("🚀 Server running at http://localhost:%s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
