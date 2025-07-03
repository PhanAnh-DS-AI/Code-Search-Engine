package qdrant

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
)

type QdrantClient struct {
	url    string
	client *http.Client
}

// NewQdrantClient creates a new instance of QdrantClient using environment variables or defaults.
func NewQdrantClient() *QdrantClient {
	address := os.Getenv("QDRANT_URL")
	if address == "" {
		address = "http://localhost:6333"
	}
	log.Printf("🚀 Qdrant client connecting to URL: %s\n", address)
	return &QdrantClient{
		url:    address,
		client: &http.Client{},
	}
}

// CreateCollectionIfNotExists checks if a collection exists in Qdrant and creates it if it doesn't.
func (q *QdrantClient) CreateCollectionIfNotExists(name string, dim int) error {
	checkURL := fmt.Sprintf("%s/collections/%s", q.url, name)
	req, err := http.NewRequestWithContext(context.Background(), http.MethodGet, checkURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create check request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	if apiKey := os.Getenv("QDRANT_API_KEY"); apiKey != "" {
		req.Header.Set("api-key", apiKey)
	}

	resp, err := q.client.Do(req)
	if err != nil {
		return fmt.Errorf("collection check failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		fmt.Printf("✅ Collection '%s' already exists.\n", name)
		return nil
	}

	if resp.StatusCode != http.StatusNotFound {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("collection check returned status %d: %s", resp.StatusCode, string(body))
	}

	reqBody := map[string]interface{}{
		"vectors": map[string]interface{}{
			"size":     dim,
			"distance": "Cosine",
		},
	}
	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal collection body: %w", err)
	}

	createReq, err := http.NewRequestWithContext(
		context.Background(),
		http.MethodPut,
		fmt.Sprintf("%s/collections/%s", q.url, name),
		bytes.NewBuffer(bodyBytes),
	)
	if err != nil {
		return fmt.Errorf("failed to create collection request: %w", err)
	}
	createReq.Header.Set("Content-Type", "application/json")

	if apiKey := os.Getenv("QDRANT_API_KEY"); apiKey != "" {
		createReq.Header.Set("api-key", apiKey)
	}

	createResp, err := q.client.Do(createReq)
	if err != nil {
		return fmt.Errorf("create collection request failed: %w", err)
	}
	defer createResp.Body.Close()

	if createResp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(createResp.Body)
		return fmt.Errorf("create collection failed: %s — %s", createResp.Status, string(respBody))
	}

	fmt.Printf("✅ Collection '%s' created successfully.\n", name)
	return nil
}

// UpsertVector inserts or updates a vector in the specified Qdrant collection.
func (q *QdrantClient) UpsertVector(collectionName string, id string, vector []float32, payload map[string]interface{}) error {
	points := []map[string]interface{}{
		{
			"id":      id,
			"vector":  vector,
			"payload": payload,
		},
	}

	reqBody := map[string]interface{}{
		"points": points,
	}

	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal upsert body: %w", err)
	}

	url := fmt.Sprintf("%s/collections/%s/points?wait=true", q.url, collectionName)
	req, err := http.NewRequestWithContext(context.Background(), http.MethodPut, url, bytes.NewBuffer(bodyBytes))
	if err != nil {
		return fmt.Errorf("failed to create upsert request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	apiKey := os.Getenv("QDRANT_API_KEY")
	if apiKey == "" {
		return fmt.Errorf("QDRANT_API_KEY is not set in environment variables")
	}
	req.Header.Set("api-key", apiKey)

	resp, err := q.client.Do(req)
	if err != nil {
		return fmt.Errorf("qdrant insert failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("upsert points failed with status: %s — response: %s", resp.Status, string(respBody))
	}

	fmt.Printf("✅ Upserted vector to collection '%s'.\n", collectionName)
	return nil
}

// CollectionExists checks whether a Qdrant collection already exists
func (q *QdrantClient) CollectionExists(name string) (bool, error) {
	checkURL := fmt.Sprintf("%s/collections/%s", q.url, name)
	req, err := http.NewRequestWithContext(context.Background(), http.MethodGet, checkURL, nil)
	if err != nil {
		return false, fmt.Errorf("failed to create check request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	if apiKey := os.Getenv("QDRANT_API_KEY"); apiKey != "" {
		req.Header.Set("api-key", apiKey)
	}

	resp, err := q.client.Do(req)
	if err != nil {
		return false, fmt.Errorf("collection check failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		return true, nil
	}
	if resp.StatusCode == http.StatusNotFound {
		return false, nil
	}

	body, _ := io.ReadAll(resp.Body)
	return false, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
}

func (q *QdrantClient) ScrollRandomPoints(collection string, limit int) ([]map[string]interface{}, error) {
	url := fmt.Sprintf("%s/collections/%s/points/scroll", q.url, collection)

	// No filter, just random offset (simulate randomness by choosing non-zero offset)
	body := map[string]interface{}{
		"limit":        limit,
		"with_payload": true,
		"with_vector":  false,
	}

	bodyBytes, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal scroll body: %w", err)
	}

	req, err := http.NewRequestWithContext(context.Background(), http.MethodPost, url, bytes.NewBuffer(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("failed to create scroll request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if apiKey := os.Getenv("QDRANT_API_KEY"); apiKey != "" {
		req.Header.Set("api-key", apiKey)
	}

	resp, err := q.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("scroll request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("scroll failed: %s — %s", resp.Status, string(respBody))
	}

	var result struct {
		Result struct {
			Points []struct {
				ID      interface{}            `json:"id"`
				Payload map[string]interface{} `json:"payload"`
			} `json:"points"`
		} `json:"result"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode scroll result: %w", err)
	}

	var payloads []map[string]interface{}
	for _, p := range result.Result.Points {
		payloads = append(payloads, p.Payload)
	}

	return payloads, nil
}

type SearchRequest struct {
	Vector      []float32      `json:"vector"`
	Top         int            `json:"top"`
	Params      map[string]any `json:"params,omitempty"`
	Filter      map[string]any `json:"filter,omitempty"`
	WithPayload bool           `json:"with_payload"`
	WithVector  bool           `json:"with_vector"`
}

func (q *QdrantClient) Search(collectionName string, vector []float32, top int) ([]byte, error) {
	url := fmt.Sprintf("%s/collections/%s/points/search", q.url, collectionName)

	reqBody := SearchRequest{
		Vector:      vector,
		Top:         top,
		WithPayload: true,
		WithVector:  false,
	}

	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("marshal search body failed: %w", err)
	}

	req, err := http.NewRequestWithContext(context.Background(), http.MethodPost, url, bytes.NewBuffer(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("create request failed: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if apiKey := os.Getenv("QDRANT_API_KEY"); apiKey != "" {
		req.Header.Set("api-key", apiKey)
	}

	resp, err := q.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("http request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("search failed: %s — %s", resp.Status, string(respBody))
	}

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response failed: %w", err)
	}

	return respBody, nil
}

func (q *QdrantClient) ScrollAllPoints(collection string, batchSize int) ([]map[string]interface{}, error) {
	var allPoints []map[string]interface{}
	var nextPage interface{} = nil

	for {
		body := map[string]interface{}{
			"limit":        batchSize,
			"with_payload": true,
			"with_vector":  false,
		}
		if nextPage != nil {
			body["page"] = nextPage
		}

		bodyBytes, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal scroll body: %w", err)
		}

		url := fmt.Sprintf("%s/collections/%s/points/scroll", q.url, collection)
		req, err := http.NewRequest(http.MethodPost, url, bytes.NewBuffer(bodyBytes))
		if err != nil {
			return nil, fmt.Errorf("failed to create scroll request: %w", err)
		}

		req.Header.Set("Content-Type", "application/json")
		if apiKey := os.Getenv("QDRANT_API_KEY"); apiKey != "" {
			req.Header.Set("api-key", apiKey)
		}

		resp, err := q.client.Do(req)
		if err != nil {
			return nil, fmt.Errorf("scroll request failed: %w", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			respBody, _ := io.ReadAll(resp.Body)
			return nil, fmt.Errorf("scroll failed: %s — %s", resp.Status, string(respBody))
		}

		var result struct {
			Result struct {
				Points []struct {
					ID      interface{}            `json:"id"`
					Payload map[string]interface{} `json:"payload"`
				} `json:"points"`
				NextPage interface{} `json:"next_page"`
			} `json:"result"`
		}

		if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
			return nil, fmt.Errorf("failed to decode scroll result: %w", err)
		}

		if len(result.Result.Points) == 0 {
			break
		}

		for _, p := range result.Result.Points {
			allPoints = append(allPoints, p.Payload)
		}

		if result.Result.NextPage == nil {
			break
		}
		nextPage = result.Result.NextPage
	}

	return allPoints, nil
}
