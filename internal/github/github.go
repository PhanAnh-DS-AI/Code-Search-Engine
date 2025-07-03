package github

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/google/go-github/v53/github"
	"golang.org/x/oauth2"
)

type GitHubClient struct {
	client *github.Client
}

func NewGitHubClient() *GitHubClient {
	token := os.Getenv("GITHUB_TOKEN")
	if token == "" {
		log.Fatal("GITHUB_TOKEN is not set in the environment variables")
	}

	ts := oauth2.StaticTokenSource(
		&oauth2.Token{AccessToken: token},
	)
	tc := oauth2.NewClient(context.Background(), ts)

	client := github.NewClient(tc)

	return &GitHubClient{client: client}
}

func (g *GitHubClient) FetchRepoDetails(owner, repo string) (*github.Repository, error) {
	repoDetails, _, err := g.client.Repositories.Get(context.Background(), owner, repo)
	if err != nil {
		return nil, fmt.Errorf("error fetching repository details: %w", err)
	}

	return repoDetails, nil
}

func (g *GitHubClient) FetchRepoTopics(owner, repo string) ([]string, error) {
	topics, _, err := g.client.Repositories.ListAllTopics(context.Background(), owner, repo)
	if err != nil {
		return nil, fmt.Errorf("error fetching repository topics: %w", err)
	}

	return topics, nil
}

func (g *GitHubClient) FetchRepoReadme(owner, repo string) (string, error) {
	readme, _, err := g.client.Repositories.GetReadme(context.Background(), owner, repo, nil)
	if err != nil {
		return "", fmt.Errorf("error fetching README: %w", err)
	}

	content, err := readme.GetContent()
	if err != nil {
		return "", fmt.Errorf("error reading README content: %w", err)
	}
	return content, nil
}

func (g *GitHubClient) SearchDiverseRepos() ([]*github.Repository, error) {
	queries := []string{
		/*
			// Push Data 1 - 716
			"stars:>1000",
			"stars:50..200",
			"stars:<50",
			"created:>2023-01-01",
			"language:go pushed:>2024-12-01",
			"language:python",
			"language:rust",
			"language:typescript",
			"language:cpp",
			"topic:web",
			"topic:cli",
			"topic:ai",
			"topic:game",
			"topic:education",

			// Push Data 717 - 1716
			"in:description \"trí tuệ nhân tạo\"",
			"in:readme \"mã nguồn mở\"",
			"language:go in:readme \"hướng dẫn\"",
			"topic:ai",
			"in:description NLP OR deep learning",
			"language:go stars:>50",
		*/
		// Push Data 1717 - 2716
		"language:go in:readme tiếng việt",
		"language:go in:description tiếng việt",
		"language:go in:readme \"hướng dẫn\"",
		"language:go in:readme \"mã nguồn\"",
		"language:go topic:vietnamese",
		"language:go in:description \"ứng dụng\"",
		"language:go topic:vn",
		/*
			// Push Data 2717 - 3716
			"topic:web",
			"topic:nextjs",
			"language:typescript topic:frontend",
			"language:javascript in:description \"responsive\"",

			// Push Data 3717 - 4716
			"qdrant in:readme",
			"qdrant topic:qdrant",
			"elasticsearch topic:elasticsearch",
			"elasticsearch in:readme",
			"vector search in:readme",
			"semantic search in:readme",

			// Push Data 3717 - 4716
			"embedding search stars:>10",
			"pinecone vector database",
			"weaviate topic:weaviate",
			"milvus vector search",
			"retrieval augmented generation",
			"rag search in:description",
			"semantic ranking in:readme",
			"hybrid search topic:search",
		*/
	}

	var allRepos []*github.Repository
	seen := make(map[int64]bool)
	ctx := context.Background()

	for _, query := range queries {
		log.Printf("🔍 Searching query: %s", query)
		page := 1
		for {
			opts := &github.SearchOptions{
				Sort:        "updated",
				Order:       "desc",
				ListOptions: github.ListOptions{Page: page, PerPage: 100},
			}

			results, _, err := g.client.Search.Repositories(ctx, query, opts)
			if err != nil {
				log.Printf("⚠️  Search failed for query '%s': %v", query, err)
				break
			}

			if len(results.Repositories) == 0 {
				log.Printf("ℹ️  No more repos found for query '%s'", query)
				break
			}

			for _, repo := range results.Repositories {
				if repo.ID == nil {
					continue
				}
				if !seen[*repo.ID] {
					allRepos = append(allRepos, repo)
					seen[*repo.ID] = true
				}
				if len(allRepos) >= 1000 {
					log.Printf("✅ Collected 1000 unique repos.")
					return allRepos, nil
				}
			}

			page++
			if page > 10 {
				log.Printf("⏭️  Reached max page limit for query '%s'", query)
				break
			}
		}

	}

	return allRepos, nil
}
