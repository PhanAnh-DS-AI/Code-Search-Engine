package api

import (
	"code-semantic-search/internal/elastic"
	"encoding/json"
	"net/http"
)

type TextSearchRequest struct {
	Query string `json:"query"`
	Top   int    `json:"limit"`
}

func FullTextSearchHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	var req TextSearchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	if req.Top <= 0 {
		req.Top = 5
	}

	results, err := elastic.SearchRepos(CollectionName, req.Query, req.Top)
	if err != nil {
		http.Error(w, "Search failed: "+err.Error(), http.StatusInternalServerError)
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"result": results,
	})
}

type TagSearchRequest struct {
	Query string `json:"query"`
	Limit int    `json:"limit"`
}

func HandleTagSearch(w http.ResponseWriter, r *http.Request) {
	var req TagSearchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.Limit == 0 {
		req.Limit = 10
	}

	results, err := elastic.SearchReposByTag(CollectionName, req.Query, req.Limit)
	if err != nil {
		http.Error(w, "Search error: "+err.Error(), http.StatusInternalServerError)
		return
	}

	resp := map[string]interface{}{
		"result": results,
	}
	json.NewEncoder(w).Encode(resp)
}
