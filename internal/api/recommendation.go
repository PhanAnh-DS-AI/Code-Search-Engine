package api

import (
	"code-semantic-search/internal/elastic"
	"encoding/json"
	"net/http"
	"strconv"
)

type RecommendationResponse struct {
	TrendingRepos        []elastic.RepoDoc            `json:"trending"`
	PopularRepos         []elastic.RepoDoc            `json:"popular"`
	TopicRecommendations map[string][]elastic.RepoDoc `json:"topics"`
	SuggestedFilters     []string                     `json:"suggested_filters"`
	Limit                int                          `json:"limit"`
}

func RecommendationsHandler(collectionName string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit := 25
		if lStr := r.URL.Query().Get("limit"); lStr != "" {
			if l, err := strconv.Atoi(lStr); err == nil && l > 0 {
				limit = l
			}
		}

		trending, popular, topics, err := elastic.GetRecommendations(collectionName, limit)
		if err != nil {
			http.Error(w, "Failed to get recommendations", http.StatusInternalServerError)
			return
		}

		suggestedFilters, err := elastic.GetTopTags(collectionName, 10)
		if err != nil {
			suggestedFilters = []string{"machine learning", "web3", "frontend", "blockchain", "deep learning"} // fallback
		}

		resp := RecommendationResponse{
			TrendingRepos:        trending,
			PopularRepos:         popular,
			TopicRecommendations: topics,
			SuggestedFilters:     suggestedFilters,
			Limit:                limit,
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}
}
