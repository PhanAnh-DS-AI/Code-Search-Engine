package api

import (
	"code-semantic-search/internal/embedding"
	"code-semantic-search/internal/llm"
	"code-semantic-search/internal/qdrant"
	"encoding/json"
	"fmt"
	"net/http"
)

type SearchRequest struct {
	Text string `json:"query"`
	Top  int    `json:"limit"`
}

func SearchHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	var req SearchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	if req.Top <= 0 {
		req.Top = 5
	}

	queries, err := llm.PreprocessQuery(req.Text)
	preprocessedQuery := req.Text
	if err == nil && len(queries) > 0 {
		preprocessedQuery = queries[0]
	}
	fmt.Println("Preprocessed query:", preprocessedQuery)
	vector, err := embedding.GenerateEmbedding(preprocessedQuery)
	if err != nil {
		http.Error(w, fmt.Sprintf("❌ Embedding error: %v", err), http.StatusInternalServerError)
		return
	}
	if len(vector) != VectorDim {
		http.Error(w, "❌ Embedding must return {VectorDim} dimensions", http.StatusBadRequest)
		return
	}

	qClient := qdrant.NewQdrantClient()
	result, err := qClient.Search(CollectionName, vector, req.Top)
	if err != nil {
		http.Error(w, fmt.Sprintf("❌ Search failed: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(result)
}
