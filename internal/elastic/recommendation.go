package elastic

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
)

func GetTopTags(collectionName string, size int) ([]string, error) {
	var buf bytes.Buffer
	aggQuery := map[string]interface{}{
		"size": 0,
		"aggs": map[string]interface{}{
			"top_tags": map[string]interface{}{
				"terms": map[string]interface{}{
					"field": "tags.keyword",
					"size":  size,
				},
			},
		},
	}

	if err := json.NewEncoder(&buf).Encode(aggQuery); err != nil {
		return nil, fmt.Errorf("encode agg query: %w", err)
	}

	res, err := ESClient.Search(
		ESClient.Search.WithContext(context.Background()),
		ESClient.Search.WithIndex(collectionName),
		ESClient.Search.WithBody(&buf),
	)
	if err != nil {
		return nil, fmt.Errorf("ES search agg error: %w", err)
	}
	defer res.Body.Close()

	var r map[string]interface{}
	if err := json.NewDecoder(res.Body).Decode(&r); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	buckets, ok := r["aggregations"].(map[string]interface{})["top_tags"].(map[string]interface{})["buckets"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected agg format")
	}

	var tags []string
	for _, b := range buckets {
		bMap := b.(map[string]interface{})
		tag := bMap["key"].(string)
		tags = append(tags, tag)
	}
	return tags, nil
}

func GetRecommendations(collectionName string, top int) (trending []RepoDoc, popular []RepoDoc, topicRecs map[string][]RepoDoc, err error) {
	// 1. Trending: sort by stars desc + recent updated (fake query đơn giản)
	trending, err = searchWithSortAndDateFilter(collectionName, top, "2025-01-01", "meta_data.stars", "date")
	if err != nil {
		return
	}

	// 2. Popular: sort by stars desc, ignore date
	popular, err = searchWithSort(collectionName, top, "meta_data.stars")
	if err != nil {
		return
	}

	// 3. Topic Recommendations: tìm theo vài topic cố định
	topicRecs = make(map[string][]RepoDoc)
	topics := []string{"machine learning", "web3", "frontend"}
	for _, topic := range topics {
		docs, e := SearchReposByTag(collectionName, topic, top)
		if e != nil {
			continue
		}
		topicRecs[topic] = docs
	}

	return
}

func searchWithSort(collectionName string, top int, sortFields ...string) ([]RepoDoc, error) {
	var buf bytes.Buffer

	sortArr := []map[string]interface{}{}
	for _, f := range sortFields {
		sortArr = append(sortArr, map[string]interface{}{f: map[string]interface{}{"order": "desc"}})
	}

	query := map[string]interface{}{
		"size": top,
		"sort": sortArr,
		"query": map[string]interface{}{
			"match_all": map[string]interface{}{},
		},
	}

	if err := json.NewEncoder(&buf).Encode(query); err != nil {
		return nil, err
	}

	res, err := ESClient.Search(
		ESClient.Search.WithContext(context.Background()),
		ESClient.Search.WithIndex(collectionName),
		ESClient.Search.WithBody(&buf),
		ESClient.Search.WithTrackTotalHits(true),
	)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()

	var r map[string]interface{}
	if err := json.NewDecoder(res.Body).Decode(&r); err != nil {
		return nil, err
	}

	hitsMap, ok := r["hits"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid response format: missing 'hits'")
	}

	hitArray, ok := hitsMap["hits"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid response format: missing 'hits.hits'")
	}

	results := make([]RepoDoc, 0, len(hitArray))
	for _, hit := range hitArray {
		hitMap, ok := hit.(map[string]interface{})
		if !ok {
			continue
		}

		source, ok := hitMap["_source"]
		if !ok {
			continue
		}

		data, err := json.Marshal(source)
		if err != nil {
			continue
		}

		var repo RepoDoc
		if err := json.Unmarshal(data, &repo); err != nil {
			continue
		}

		results = append(results, repo)
	}

	return results, nil
}

func searchWithSortAndDateFilter(collectionName string, top int, fromDate string, sortFields ...string) ([]RepoDoc, error) {
	var buf bytes.Buffer

	sortArr := []map[string]interface{}{}
	for _, f := range sortFields {
		sortArr = append(sortArr, map[string]interface{}{f: map[string]interface{}{"order": "desc"}})
	}

	query := map[string]interface{}{
		"size": top,
		"sort": sortArr,
		"query": map[string]interface{}{
			"range": map[string]interface{}{
				"date": map[string]interface{}{
					"gte": fromDate,
				},
			},
		},
	}

	if err := json.NewEncoder(&buf).Encode(query); err != nil {
		return nil, err
	}

	res, err := ESClient.Search(
		ESClient.Search.WithContext(context.Background()),
		ESClient.Search.WithIndex(collectionName),
		ESClient.Search.WithBody(&buf),
		ESClient.Search.WithTrackTotalHits(true),
	)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()

	var r map[string]interface{}
	if err := json.NewDecoder(res.Body).Decode(&r); err != nil {
		return nil, err
	}

	hitsMap, ok := r["hits"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid response format: missing 'hits'")
	}

	hitArray, ok := hitsMap["hits"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid response format: missing 'hits.hits'")
	}

	results := make([]RepoDoc, 0, len(hitArray))
	for _, hit := range hitArray {
		hitMap, ok := hit.(map[string]interface{})
		if !ok {
			continue
		}

		source, ok := hitMap["_source"]
		if !ok {
			continue
		}

		data, err := json.Marshal(source)
		if err != nil {
			continue
		}

		var repo RepoDoc
		if err := json.Unmarshal(data, &repo); err != nil {
			continue
		}

		results = append(results, repo)
	}

	return results, nil
}
