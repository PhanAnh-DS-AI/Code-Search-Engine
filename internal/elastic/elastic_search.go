package elastic

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
)

func SearchRepos(collectionName string, query string, top int) ([]RepoDoc, error) {
	var buf bytes.Buffer
	searchQuery := map[string]interface{}{
		"query": map[string]interface{}{
			"multi_match": map[string]interface{}{
				"query":  query,
				"fields": []string{"title^3", "short_des", "tags"},
			},
		},
		"size": top,
	}

	if err := json.NewEncoder(&buf).Encode(searchQuery); err != nil {
		return nil, fmt.Errorf("encoding query: %w", err)
	}

	res, err := ESClient.Search(
		ESClient.Search.WithContext(context.Background()),
		ESClient.Search.WithIndex(collectionName),
		ESClient.Search.WithBody(&buf),
		ESClient.Search.WithTrackTotalHits(true),
	)
	if err != nil {
		return nil, fmt.Errorf("search error: %w", err)
	}
	defer res.Body.Close()

	bodyBytes, _ := io.ReadAll(res.Body)
	res.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))
	var r map[string]interface{}
	if err := json.NewDecoder(res.Body).Decode(&r); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	hitsMap, ok := r["hits"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid response format: missing 'hits'")
	}

	hitArray, ok := hitsMap["hits"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid response format: missing 'hits.hits'")
	}

	var results []RepoDoc
	for _, hit := range hitArray {
		hitMap, ok := hit.(map[string]interface{})
		if !ok {
			continue
		}

		source, ok := hitMap["_source"]
		if !ok {
			continue
		}

		score, _ := hitMap["_score"].(float64)

		data, err := json.Marshal(source)
		if err != nil {
			continue
		}

		var repo RepoDoc
		if err := json.Unmarshal(data, &repo); err != nil {
			continue
		}

		repo.Score = score
		results = append(results, repo)
	}

	return results, nil
}

func SearchReposWithFilters(collectionName string, filters RepoFilters, rewrittenQuery string, top int) ([]RepoDoc, error) {
	var executeQuery = func(f RepoFilters, rq string) ([]RepoDoc, error) {
		var buf bytes.Buffer
		filterClauses := []map[string]interface{}{}

		// ⭐ star-min
		if f.StarsMin != nil {
			filterClauses = append(filterClauses, map[string]interface{}{
				"range": map[string]interface{}{
					"meta_data.stars": map[string]interface{}{"gte": *f.StarsMin},
				},
			})
		}

		// 📅 created-after and created-before
		println("CreatedAfter:", f.CreatedAfter, "CreatedBefore:", f.CreatedBefore)
		if f.CreatedAfter != nil || f.CreatedBefore != nil {
			rangeFilter := map[string]interface{}{}

			if f.CreatedAfter != nil && *f.CreatedAfter != "" {
				rangeFilter["gte"] = *f.CreatedAfter
			}
			if f.CreatedBefore != nil && *f.CreatedBefore != "" {
				rangeFilter["lte"] = *f.CreatedBefore
			}

			filterClauses = append(filterClauses, map[string]interface{}{
				"range": map[string]interface{}{
					"date": rangeFilter,
				},
			})
		}

		queryShouldClauses := []map[string]interface{}{}
		tagShouldClauses := []map[string]interface{}{}

		// 🔑 rewrittenQuery (match_phrase trên title, short_des, tags)
		if rq != "" {
			queryShouldClauses = append(queryShouldClauses, map[string]interface{}{
				"match_phrase": map[string]interface{}{
					"title": map[string]interface{}{
						"query": rq,
						"boost": 5,
					},
				},
			})
			queryShouldClauses = append(queryShouldClauses, map[string]interface{}{
				"match_phrase": map[string]interface{}{
					"meta_data.owner": map[string]interface{}{
						"query": rq,
						"boost": 5,
					},
				},
			})
			queryShouldClauses = append(queryShouldClauses, map[string]interface{}{
				"match_phrase": map[string]interface{}{
					"short_des": map[string]interface{}{
						"query": rq,
						"boost": 2,
					},
				},
			})
			queryShouldClauses = append(queryShouldClauses, map[string]interface{}{
				"match_phrase": map[string]interface{}{
					"tags": map[string]interface{}{
						"query": rq,
						"boost": 1,
					},
				},
			})
		}

		// 🏷️ Tag filters
		tagFilters := []string{}
		if f.Language != nil {
			tagFilters = append(tagFilters, *f.Language)
		}
		tagFilters = append(tagFilters, f.Libraries...)
		tagFilters = append(tagFilters, f.Topics...)

		for _, tag := range tagFilters {
			tagShouldClauses = append(tagShouldClauses, map[string]interface{}{
				"bool": map[string]interface{}{
					"should": []map[string]interface{}{
						{"term": map[string]interface{}{"tags.keyword": tag}},
						{"match_phrase": map[string]interface{}{"title": tag}},
						{"match_phrase": map[string]interface{}{"short_des": tag}},
					},
					"minimum_should_match": 1,
				},
			})
		}

		// Combine all
		allShouldClauses := append(queryShouldClauses, tagShouldClauses...)

		// ✅ Tính đúng minimum_should_match
		minShould := 1
		if len(tagShouldClauses) > 0 {
			// Chỉ tính theo số tag blocks
			minShould = (len(tagShouldClauses) + 1) / 2
		}

		searchQuery := map[string]interface{}{
			"query": map[string]interface{}{
				"bool": map[string]interface{}{
					"should":               allShouldClauses,
					"minimum_should_match": minShould,
					"filter":               filterClauses,
				},
			},
			"size": top,
		}

		// Debug DSL
		// if q, err := json.MarshalIndent(searchQuery, "", "  "); err == nil {
		// 	fmt.Printf("📦 Final Elasticsearch DSL:\n%s\n", q)
		// }

		if err := json.NewEncoder(&buf).Encode(searchQuery); err != nil {
			return nil, fmt.Errorf("encode query: %w", err)
		}

		res, err := ESClient.Search(
			ESClient.Search.WithContext(context.Background()),
			ESClient.Search.WithIndex(collectionName),
			ESClient.Search.WithBody(&buf),
			ESClient.Search.WithTrackTotalHits(true),
		)
		if err != nil {
			return nil, fmt.Errorf("ES search error: %w", err)
		}
		defer res.Body.Close()

		body, _ := io.ReadAll(res.Body)
		res.Body = io.NopCloser(bytes.NewBuffer(body))

		var raw map[string]interface{}
		if err := json.NewDecoder(res.Body).Decode(&raw); err != nil {
			return nil, fmt.Errorf("decode response: %w", err)
		}
		hits, _ := raw["hits"].(map[string]interface{})
		hArr, _ := hits["hits"].([]interface{})

		results := make([]RepoDoc, 0, len(hArr))
		for _, h := range hArr {
			hm, _ := h.(map[string]interface{})
			src := hm["_source"]
			b, _ := json.Marshal(src)

			var repo RepoDoc
			if json.Unmarshal(b, &repo) == nil {
				if sc, ok := hm["_score"].(float64); ok {
					repo.Score = sc
				}
				results = append(results, repo)
			}
		}
		return results, nil
	}

	return executeQuery(filters, rewrittenQuery)
}

func SearchReposByTag(collectionName string, tag string, top int) ([]RepoDoc, error) {
	var buf bytes.Buffer
	searchQuery := map[string]interface{}{
		"query": map[string]interface{}{
			"match": map[string]interface{}{
				"tags": tag,
			},
		},
		"size": top,
	}

	if err := json.NewEncoder(&buf).Encode(searchQuery); err != nil {
		return nil, fmt.Errorf("encoding tag search query: %w", err)
	}

	res, err := ESClient.Search(
		ESClient.Search.WithContext(context.Background()),
		ESClient.Search.WithIndex(collectionName),
		ESClient.Search.WithBody(&buf),
		ESClient.Search.WithTrackTotalHits(true),
	)
	if err != nil {
		return nil, fmt.Errorf("search by tag error: %w", err)
	}
	defer res.Body.Close()

	bodyBytes, _ := io.ReadAll(res.Body)
	res.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))

	var r map[string]interface{}
	if err := json.NewDecoder(res.Body).Decode(&r); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	hitsMap, ok := r["hits"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid response format: missing 'hits'")
	}

	hitArray, ok := hitsMap["hits"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid response format: missing 'hits.hits'")
	}

	var results []RepoDoc
	for _, hit := range hitArray {
		hitMap, ok := hit.(map[string]interface{})
		if !ok {
			continue
		}

		source, ok := hitMap["_source"]
		if !ok {
			continue
		}

		score, _ := hitMap["_score"].(float64)

		data, err := json.Marshal(source)
		if err != nil {
			continue
		}

		var repo RepoDoc
		if err := json.Unmarshal(data, &repo); err != nil {
			continue
		}

		repo.Score = score
		results = append(results, repo)
	}

	return results, nil
}
