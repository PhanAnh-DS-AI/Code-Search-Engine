package llm

type RepoQueryResult struct {
	Intent              string  `json:"intent"`
	Filters             Filters `json:"filters"`
	QueryVectorRequired bool    `json:"query_vector_required"`
	RewrittenQuery      string  `json:"rewritten_query"`
}

type Filters struct {
	Language      string   `json:"language"`
	Libraries     []string `json:"libraries"`
	CreatedAfter  string   `json:"created_after"`
	CreatedBefore string   `json:"created_before"`
	StarsMin      *int     `json:"stars_min"`
	Topics        []string `json:"topics"`
}
