package api

import (
	"code-semantic-search/internal/hybrid"
	"code-semantic-search/internal/llm"
	"encoding/json"
	"log"
	"net/http"
)

type HybridSearchRequest struct {
	Query string `json:"query"`
	Top   int    `json:"limit"`
}

func HybridSearchHandler(searcher *hybrid.HybridSearcher) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var req HybridSearchRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Query == "" {
			http.Error(w, "Invalid request payload", http.StatusBadRequest)
			return
		}

		top := req.Top
		if top <= 0 {
			top = 10
		}

		results, suggestTopic, err := searcher.HybridSearchRepos(req.Query, top, CollectionName)
		if err != nil {
			log.Printf("❌ hybrid search failed: %v", err)
			http.Error(w, "Search failed", http.StatusInternalServerError)
			return
		}
		suggestedTopics := ExtractSuggestedFiltersFromQuery(suggestTopic)

		// 🔍 Generate filter chips
		filters, err := llm.GenerateFilterChips(req.Query)
		if err != nil {
			log.Printf("⚠️ failed to generate filters: %v", err)
			filters = []string{}
		}

		resp := map[string]interface{}{
			"results":            results,
			"filter_suggestions": filters,
			"suggested_topics":   suggestedTopics,
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}
}

func ExtractSuggestedFiltersFromQuery(filters llm.Filters) []string {
	filterSet := map[string]bool{}
	var suggestions []string

	if filters.Language != "" {
		filterSet[filters.Language] = true
	}
	for _, lib := range filters.Libraries {
		filterSet[lib] = true
	}
	for _, topic := range filters.Topics {
		filterSet[topic] = true
	}

	for tag := range filterSet {
		suggestions = append(suggestions, tag)
	}
	return suggestions
}
