package hybrid

import (
	"code-semantic-search/internal/elastic"
	"code-semantic-search/internal/embedding"
	"code-semantic-search/internal/llm"
	"code-semantic-search/internal/qdrant"
	"log"
	"sort"
)

const (
	semanticWeight = 0.7
	lexicalWeight  = 0.3
)

type HybridSearcher struct {
	Qdrant *qdrant.QdrantClient
}

func (h *HybridSearcher) HybridSearchRepos(query string, top int, collectionName string) ([]elastic.RepoDoc, llm.Filters, error) {
	// 1. Hiểu intent và filters
	repoQuery, err := llm.UnderstandRepoQuery(query)
	if err != nil {
		log.Printf("❌ Failed to understand repo query: %v", err)
	}

	// 2. Query text cho elastic (ưu tiên rewritten_query nếu có)
	queryText := query
	if repoQuery != nil && repoQuery.RewrittenQuery != "" {
		queryText = repoQuery.RewrittenQuery
	} else if queries, err := llm.PreprocessQuery(query); err == nil && len(queries) > 0 {
		queryText = queries[0]
	}

	// 3. Search vector nếu cần hoặc fallback khi textResults rỗng
	var vectorResults []elastic.RepoDoc
	doVectorSearch := repoQuery != nil && repoQuery.QueryVectorRequired

	// Search vector nếu QueryVectorRequired = true
	if doVectorSearch {
		vector, err := embedding.GenerateEmbedding(query)
		if err != nil {
			log.Printf("❌ Failed to embed query: %v", err)
		} else {
			qdrantResp, err := h.Qdrant.Search(collectionName, vector, top*10)
			if err != nil {
				log.Printf("❌ Qdrant search failed: %v", err)
			} else {
				rawResults := parseQdrantResults(qdrantResp)
				vectorResults = filterVectorResults(rawResults, repoQuery.Filters)
			}
		}
	}

	// 4. Elastic search với filters
	var textResults []elastic.RepoDoc
	log.Printf("📄 Final queryText sent to Elastic: %s", queryText)
	if repoQuery != nil {
		elasticFilters := MapLLMToElasticFilters(repoQuery.Filters)
		log.Printf("🧪 Elastic filters: %+v", elasticFilters)
		textResults, err = elastic.SearchReposWithFilters(collectionName, elasticFilters, queryText, top*2)
	} else {
		textResults, err = elastic.SearchRepos(collectionName, queryText, top*2)
	}
	if err != nil {
		log.Printf("❌ Elasticsearch search failed: %v", err)
	}
	println("text Result: %+v", textResults)

	// Fallback: nếu Elasticsearch không ra kết quả, dù QueryVectorRequired=false vẫn search vector
	if len(textResults) == 0 && !doVectorSearch {
		log.Printf("⚠️ Elasticsearch không ra kết quả, fallback sang search vector")
		vector, err := embedding.GenerateEmbedding(query)
		if err != nil {
			log.Printf("❌ Failed to embed query fallback: %v", err)
		} else {
			qdrantResp, err := h.Qdrant.Search(collectionName, vector, top*10)
			if err != nil {
				log.Printf("❌ Qdrant fallback search failed: %v", err)
			} else {
				rawResults := parseQdrantResults(qdrantResp)
				vectorResults = filterVectorResults(rawResults, repoQuery.Filters)
			}
		}
	}

	// 5. Không có vector → trả text-only
	if len(vectorResults) == 0 {
		if len(textResults) > top {
			return textResults[:top], repoQuery.Filters, nil
		}
		return textResults, repoQuery.Filters, nil
	}

	// 6. Merge score
	normVector := normalizeRepoScores(vectorResults)
	normText := normalizeRepoScores(textResults)

	scoreMap := map[string]elastic.RepoDoc{}
	for _, doc := range normVector {
		id := normalizeID(doc)
		doc.Score = semanticWeight * doc.Score
		scoreMap[id] = doc
	}
	for _, doc := range normText {
		id := normalizeID(doc)
		if existing, ok := scoreMap[id]; ok {
			existing.Score += lexicalWeight * doc.Score
			scoreMap[id] = existing
		} else {
			doc.Score = lexicalWeight * doc.Score
			scoreMap[id] = doc
		}
	}

	// 7. Sort
	var final []elastic.RepoDoc
	for _, doc := range scoreMap {
		final = append(final, doc)
	}

	for i, doc := range final {
		trendScore := 0.5*normalizeInt(doc.MetaData.Stars) + 0.5*normalizeDate(doc.Date)
		final[i].Score = 0.7*final[i].Score + 0.3*trendScore
	}

	sort.Slice(final, func(i, j int) bool {
		return final[i].Score > final[j].Score
	})

	if len(final) > top {
		final = final[:top]
	}
	log.Printf("🔍 Hybrid search results: %d repos found\n", len(final))
	return final, repoQuery.Filters, nil
}
