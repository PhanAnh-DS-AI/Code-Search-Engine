package llm

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"regexp"
	"strings"
)

const geminiAPI = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key="

type Content struct {
	Role  string `json:"role"`
	Parts []struct {
		Text string `json:"text"`
	} `json:"parts"`
}

type GenerateContentRequest struct {
	Contents []Content `json:"contents"`
}

type GenerateContentResponse struct {
	Candidates []struct {
		Content struct {
			Parts []struct {
				Text string `json:"text"`
			} `json:"parts"`
		} `json:"content"`
	} `json:"candidates"`
	Error *struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

func CallGemini(promptText string) (string, error) {
	apiKey := os.Getenv("GOOGLE_API_KEY")
	if apiKey == "" {
		return "", fmt.Errorf("missing GOOGLE_API_KEY environment variable")
	}

	reqBody := GenerateContentRequest{
		Contents: []Content{
			{
				Role: "user",
				Parts: []struct {
					Text string `json:"text"`
				}{
					{Text: promptText},
				},
			},
		},
	}

	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return "", err
	}

	resp, err := http.Post(geminiAPI+apiKey, "application/json", bytes.NewBuffer(bodyBytes))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	// fmt.Println("Raw Gemini API response:", string(respBody))

	var genResp GenerateContentResponse
	if err := json.Unmarshal(respBody, &genResp); err != nil {
		return "", err
	}

	if genResp.Error != nil {
		return "", fmt.Errorf("API error %d: %s", genResp.Error.Code, genResp.Error.Message)
	}

	if len(genResp.Candidates) == 0 || len(genResp.Candidates[0].Content.Parts) == 0 {
		return "", fmt.Errorf("no valid candidates in response")
	}

	return genResp.Candidates[0].Content.Parts[0].Text, nil
}

func extractCleanJSON(input string) (string, error) {
	trimmed := strings.TrimSpace(input)
	// Match JSON inside ```json ... ```
	re := regexp.MustCompile("(?s)```json\\s*(\\{.*\\}|\\[.*\\])\\s*```")
	matches := re.FindStringSubmatch(trimmed)

	if len(matches) < 2 {
		return "", errors.New("no JSON object or array found between ```json blocks")
	}
	return matches[1], nil
}

// ExtractQueries lấy raw response string, trả về slice 6 query hoặc lỗi
func ExtractQueries(rawResp string) ([]string, error) {
	jsonStr, err := extractCleanJSON(rawResp)
	if err != nil {
		return nil, err
	}

	var queries []string
	err = json.Unmarshal([]byte(jsonStr), &queries)
	if err != nil {
		return nil, err
	}
	if len(queries) != 6 {
		return nil, fmt.Errorf("expected 6 queries, got %d", len(queries))
	}
	return queries, nil
}

// ExtractFirstQuery lấy raw response string, trả về query đầu tiên hoặc lỗi
func ExtractFirstQuery(rawResp string) (string, error) {
	queries, err := ExtractQueries(rawResp)
	if err != nil {
		return "", err
	}
	return queries[0], nil
}

func PreprocessQuery(rawQuery string) ([]string, error) {
	prompt := `You're a query preprocessing agent. 

Given a user search query, do the following:
1. Preprocess the original query: lowercase, remove punctuation, and stopwords. However, **do not remove Vietnamese diacritics (accents/tones).**
2. Generate 5 alternative search queries that are semantically similar to the cleaned query.
3. Return a JSON array with 6 total queries (the first is the cleaned original, the next 5 are similar queries).
4. All queries in the array must be preprocessed the same way: lowercase, no punctuation, no stopwords, and **must keep Vietnamese diacritics.**

User query: "` + rawQuery + `"`

	rawResp, err := CallGemini(prompt)
	if err != nil {
		return nil, err
	}

	return ExtractQueries(rawResp)
}

func UnderstandRepoQuery(rawQuery string) (*RepoQueryResult, error) {
	prompt := `
	You are a natural language understanding agent that helps interpret user queries about GitHub repositories. 

	Given a user query, extract the following fields and return valid strict JSON:

	{
		"intent": "search_repository",
		"filters": {
			"language": "<language_or_null>",
			"libraries": ["<libraries_or_empty_array>"],
			"created_after": "<yyyy-mm-dd_or_null>",
			"created_before": "<yyyy-mm-dd_or_null>",
			"stars_min": <number_or_null>,
			"topics": ["<topics_or_empty_array>"],
		}
	},
	"query_vector_required": <true_or_false>,
	"rewritten_query": "<text_to_use_for_tag_or_phrase_search>"
	}

	Guidelines:
	- Always extract filters such as language, libraries, stars_min, created_after, created_before, topics.
	- If the query mentions stars directly (e.g. "more than 20 stars"), extract the value into stars_min.
	- If the query implies popularity (e.g. "popular", "top", "most starred"), use a default like stars_min = 500.
	- The "rewritten_query" field is used to search in fields like title, short description, tags.
	- Only include rewritten_query **if it contains meaningful, precise domain-specific phrases**.
		- ❌ Avoid vague, generic, or ambiguous words (e.g. “mô hình mới”, “hữu ích”, “hay”).
		- ✅ Do include domain terms like “natural language processing”, “image captioning”, “transformer chatbot”.
	- Do NOT include stars_min or created_after or created_before in rewritten_query.
	- If the user query is vague, ambiguous, or exploratory (e.g. "có gì hay", "có repo nào xịn không", "repo thú vị"), set:
		- query_vector_required = true
		- rewritten_query = ""
	- If the query contains clear filters or domain-specific keywords (e.g. “llama.cpp dùng C++”), prefer:
		- query_vector_required = false
		- rewritten_query = meaningful phrase if applicable
	- Output must be strict, valid JSON. No comments, no markdown, no explanation.
	User query: "` + rawQuery + `"
	`
	rawResp, err := CallGemini(prompt)
	if err != nil {
		return nil, err
	}

	jsonStr, err := extractCleanJSON(rawResp)
	if err != nil {
		return nil, fmt.Errorf("failed to extract JSON: %w\nRaw response:\n%s", err, rawResp)
	}
	fmt.Printf("Raw response: %s\n", rawResp)

	var result RepoQueryResult
	err = json.Unmarshal([]byte(jsonStr), &result)
	if err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w\nRaw response:\n%s", err, rawResp)
	}

	return &result, nil
}

func GenerateFilterChips(query string) ([]string, error) {
	prompt := `
You are a filter suggestion assistant for a GitHub repository search interface.

Given a vague or broad user query (e.g. "AI", "Python", "machine learning"), return 5 short, distinct, and clickable filter chips that help refine search results.

These filters should be:
- Based on common technologies, frameworks, use cases, or repository attributes.
- Useful for filtering results without modifying the original query.
- Each filter must be under 6 words.
- Do NOT repeat or rephrase the original query.

If the original query is already very specific (e.g., includes task, tech stack, or combinations), return an empty list.

Output a strict JSON object:
{"related_queries": ["filter chip 1", "filter chip 2", ...]}

User query: "` + query + `"`

	rawResp, err := CallGemini(prompt)
	if err != nil {
		return nil, err
	}

	// Expecting output like: {"related_queries": ["chip1", "chip2", ...]}
	var obj struct {
		RelatedQueries []string `json:"related_queries"`
	}

	// Try extract clean JSON first
	jsonStr, err := extractCleanJSON(rawResp)
	if err != nil {
		return nil, fmt.Errorf("failed to extract JSON: %w\nRaw response:\n%s", err, rawResp)
	}

	if err := json.Unmarshal([]byte(jsonStr), &obj); err != nil {
		return nil, fmt.Errorf("failed to parse related queries: %w\nRaw response:\n%s", err, rawResp)
	}

	return obj.RelatedQueries, nil
}
