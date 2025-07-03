package data

import (
	"code-semantic-search/internal/elastic"
	"code-semantic-search/internal/embedding"
	"code-semantic-search/internal/github"
	"code-semantic-search/internal/qdrant"
	"fmt"
	"log"
	"strconv"

	gogithub "github.com/google/go-github/v53/github"
	"github.com/google/uuid"
)

func safeString(s *string) string {
	if s != nil {
		return *s
	}
	return "(unknown)"
}

func safeInt(i *int) int {
	if i != nil {
		return *i
	}
	return 0
}

func safeSlice(s []string) []string {
	if len(s) == 0 {
		return []string{"(none)"}
	}
	return s
}

func CollectRepoDataAndStoreMany(collectionName string, qClient *qdrant.QdrantClient, repos []*gogithub.Repository) error {
	client := github.NewGitHubClient()

	for _, repo := range repos {
		if repo.Name == nil || repo.StargazersCount == nil || repo.HTMLURL == nil || repo.Owner == nil || repo.Owner.Login == nil || repo.ID == nil || repo.CreatedAt == nil {
			log.Printf("⚠️ Skipping incomplete repo: %+v", repo.Name)
			continue
		}
		if repo.Description == nil {
			empty := ""
			repo.Description = &empty
		}

		text := fmt.Sprintf("%s %s", *repo.Name, *repo.Description)
		log.Printf("🔍 Embedding repo: %s", text)

		vector, err := embedding.GenerateEmbedding(text)
		if err != nil {
			log.Printf("❌ Embedding failed for %s: %v", *repo.Name, err)
			continue
		}

		id := uuid.NewSHA1(uuid.NameSpaceURL, []byte(fmt.Sprintf("repo-%d", *repo.ID))).String()
		owner := *repo.Owner.Login

		topics := []string{}
		ts, err := client.FetchRepoTopics(owner, *repo.Name)
		if err != nil {
			log.Printf("⚠️ Failed to fetch topics for %s/%s: %v", owner, *repo.Name, err)
		} else {
			topics = ts
		}

		// ✅ Unified schema using RepoDoc
		doc := elastic.RepoDoc{
			Title:    safeString(repo.Name),
			ShortDes: safeString(repo.Description),
			Tags:     safeSlice(topics),
			Date:     repo.CreatedAt.Format("2006-01-02"),
			MetaData: elastic.MetaData{
				Stars: safeInt(repo.StargazersCount),
				Owner: owner,
				URL:   safeString(repo.HTMLURL),
				ID:    *repo.ID,
			},
		}
		payload := doc.ToMap()

		// Insert to Qdrant
		err = qClient.UpsertVector(collectionName, id, vector, payload)
		if err != nil {
			log.Printf("❌ Qdrant insert failed for %s: %v", *repo.Name, err)
			continue
		}
		log.Printf("✅ Repo '%s' inserted into Qdrant", *repo.Name)

		// Insert to Elasticsearch
		err = elastic.StoreToElasticsearch(collectionName, doc, id)
		if err != nil {
			log.Printf("⚠️ Failed to insert to Elasticsearch for %s: %v", *repo.Name, err)
		} else {
			log.Printf("✅ Repo '%s' inserted into Elasticsearch", *repo.Name)
		}
	}

	return nil
}

func SyncQdrantToElasticsearch(collectionName string, qClient *qdrant.QdrantClient) error {
	// Scroll toàn bộ data Qdrant với batch size 100 (hoặc tuỳ)
	points, err := qClient.ScrollAllPoints(collectionName, 1000)
	if err != nil {
		return fmt.Errorf("failed to scroll points from Qdrant: %w", err)
	}

	for _, payload := range points {
		metaRaw, ok := payload["meta_data"]
		if !ok {
			log.Printf("⚠️ Missing meta_data in payload, skipping")
			continue
		}
		meta, ok := metaRaw.(map[string]interface{})
		if !ok {
			log.Printf("⚠️ meta_data type assertion failed, skipping")
			continue
		}

		var idStr string
		if idv, ok := meta["id"]; ok {
			switch v := idv.(type) {
			case float64:
				idStr = strconv.FormatInt(int64(v), 10)
			case int64:
				idStr = strconv.FormatInt(v, 10)
			case string:
				idStr = v
			default:
				idStr = fmt.Sprintf("%v", v)
			}
		} else {
			log.Printf("⚠️ id not found in meta_data, skipping")
			continue
		}

		doc := elastic.RepoDoc{
			Title:    safeStringFromMap(payload, "title"),
			ShortDes: safeStringFromMap(payload, "short_des"),
			Tags:     safeStringSliceFromMap(payload, "tags"),
			Date:     safeStringFromMap(payload, "date"),
			MetaData: elastic.MetaData{
				Stars: safeIntFromMeta(meta, "stars"),
				Owner: safeStringFromMeta(meta, "owner"),
				URL:   safeStringFromMeta(meta, "url"),
				ID:    int64(safeIntFromMeta(meta, "id")),
			},
		}

		err := elastic.StoreToElasticsearch(collectionName, doc, idStr)
		if err != nil {
			log.Printf("⚠️ Failed to index repo ID %s to Elasticsearch: %v", idStr, err)
		} else {
			log.Printf("✅ Synced repo ID %s from Qdrant to Elasticsearch", idStr)
		}
	}
	return nil
}

func safeStringFromMap(m map[string]interface{}, key string) string {
	if v, ok := m[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}

func safeStringSliceFromMap(m map[string]interface{}, key string) []string {
	if v, ok := m[key]; ok {
		if slice, ok := v.([]interface{}); ok {
			res := make([]string, 0, len(slice))
			for _, i := range slice {
				if s, ok := i.(string); ok {
					res = append(res, s)
				}
			}
			return res
		}
	}
	return nil
}
func safeIntFromMeta(m map[string]interface{}, key string) int {
	if v, ok := m[key]; ok {
		switch t := v.(type) {
		case float64:
			return int(t)
		case int:
			return t
		case int64:
			return int(t)
		case string:
			n, _ := strconv.Atoi(t)
			return n
		}
	}
	return 0
}
func safeStringFromMeta(m map[string]interface{}, key string) string {
	if v, ok := m[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}
