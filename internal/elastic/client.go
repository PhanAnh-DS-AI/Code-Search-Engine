package elastic

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"

	"github.com/elastic/go-elasticsearch/v8"
)

var ESClient *elasticsearch.Client

func InitElasticClient() {
	// cfg := elasticsearch.Config{
	// 	Addresses: []string{
	// 		os.Getenv("ES_URL"),
	// 	},
	// }
	cfg := elasticsearch.Config{
		CloudID:  os.Getenv("ES_CLOUD_ID"),
		Username: os.Getenv("ES_USER"),
		Password: os.Getenv("ES_PASSWORD"),
	}

	es, err := elasticsearch.NewClient(cfg)
	if err != nil {
		log.Fatalf("❌ Error creating the client: %s", err)
	}
	ESClient = es
	log.Println("✅ Elasticsearch client initialized")
}

func StoreToElasticsearch(collectionName string, doc RepoDoc, id string) error {
	body := doc.ToMap()
	jsonBody, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal failed: %w", err)
	}

	resp, err := ESClient.Index(
		collectionName,
		bytes.NewReader(jsonBody),
		ESClient.Index.WithDocumentID(id),
		ESClient.Index.WithContext(context.Background()),
	)
	if err != nil {
		return fmt.Errorf("index failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.IsError() {
		return fmt.Errorf("index error: %s", resp.String())
	}
	return nil
}
