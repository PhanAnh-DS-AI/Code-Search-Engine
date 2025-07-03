package hybrid

import (
	"code-semantic-search/internal/elastic"
	"code-semantic-search/internal/llm"
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

func parseQdrantResults(data []byte) []elastic.RepoDoc {
	var raw struct {
		Result []struct {
			Payload map[string]interface{} `json:"payload"`
			Score   float64                `json:"score"`
		} `json:"result"`
	}

	if err := json.Unmarshal(data, &raw); err != nil {
		return nil
	}

	var results []elastic.RepoDoc
	for _, item := range raw.Result {
		payloadBytes, err := json.Marshal(item.Payload)
		if err != nil {
			continue
		}
		var doc elastic.RepoDoc
		if err := json.Unmarshal(payloadBytes, &doc); err != nil {
			continue
		}
		doc.Score = item.Score
		results = append(results, doc)
	}

	return results
}

func normalizeID(doc elastic.RepoDoc) string {
	return fmt.Sprintf("%d", doc.MetaData.ID)
}

func normalizeRepoScores(docs []elastic.RepoDoc) []elastic.RepoDoc {
	if len(docs) == 0 {
		return docs
	}

	// Find min and max scores
	minScore := docs[0].Score
	maxScore := docs[0].Score
	for _, doc := range docs {
		if doc.Score < minScore {
			minScore = doc.Score
		}
		if doc.Score > maxScore {
			maxScore = doc.Score
		}
	}

	// Case max = min
	if maxScore == minScore {
		for i := range docs {
			docs[i].Score = 1.0
		}
		return docs
	}

	// Scale to [0, 1]
	for i := range docs {
		docs[i].Score = (docs[i].Score - minScore) / (maxScore - minScore)
	}
	return docs
}

func MapLLMToElasticFilters(f llm.Filters) elastic.RepoFilters {
	var languagePtr *string
	if f.Language != "" {
		languagePtr = &f.Language
	}

	var createdAfterPtr *string
	if f.CreatedAfter != "" {
		createdAfterPtr = &f.CreatedAfter
	}

	var createdBeforePtr *string
	if f.CreatedBefore != "" {
		createdBeforePtr = &f.CreatedBefore
	}

	return elastic.RepoFilters{
		Language:      languagePtr,
		Libraries:     f.Libraries,
		CreatedAfter:  createdAfterPtr,
		CreatedBefore: createdBeforePtr,
		StarsMin:      f.StarsMin,
		Topics:        f.Topics,
	}
}

func filterVectorResults(results []elastic.RepoDoc, filters llm.Filters) []elastic.RepoDoc {
	var filtered []elastic.RepoDoc
	for _, doc := range results {
		// Stars filter
		if filters.StarsMin != nil && doc.MetaData.Stars < *filters.StarsMin {
			continue
		}

		// Created_after filter
		if filters.CreatedAfter != "" {
			if doc.Date == "" || doc.Date < filters.CreatedAfter {
				continue
			}
		}

		// Created_before filter
		if filters.CreatedBefore != "" {
			if doc.Date == "" || doc.Date > filters.CreatedBefore {
				continue
			}
		}

		// Language filter
		if filters.Language != "" && !hasOverlap(doc.Tags, []string{filters.Language}) {
			continue
		}

		// Topics filter
		if len(filters.Topics) > 0 && !hasOverlap(doc.Tags, filters.Topics) {
			continue
		}

		// Libraries filter
		if len(filters.Libraries) > 0 && !hasOverlap(doc.Tags, filters.Libraries) {
			continue
		}

		filtered = append(filtered, doc)
	}
	return filtered
}

func hasOverlap(tags []string, filters []string) bool {
	tagSet := make(map[string]bool)
	for _, t := range tags {
		tagSet[strings.ToLower(t)] = true
	}
	for _, f := range filters {
		if tagSet[strings.ToLower(f)] {
			return true
		}
	}
	return false
}

func normalizeInt(val int) float64 {
	if val > 10000 {
		return 1.0
	}
	return float64(val) / 10000.0
}

func normalizeDate(dateStr string) float64 {
	t, err := time.Parse("2006-01-02", dateStr)
	if err != nil {
		return 0.0
	}
	daysAgo := time.Since(t).Hours() / 24
	if daysAgo < 0 {
		daysAgo = 0
	}
	if daysAgo > 180 {
		return 0.0
	}
	return 1.0 - daysAgo/180.0
}
