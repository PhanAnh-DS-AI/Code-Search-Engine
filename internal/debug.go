package main

import (
	"code-semantic-search/internal/llm"
	"fmt"
	"log"
)

func main() {
	rawQuery := "hướng dẫn setup GitHub Actions"
	prompt := `You're a query preprocessing agent. 

Given a user search query, do the following:
1. Preprocess the original query: lowercase, remove punctuation, and stopwords. However, **do not remove Vietnamese diacritics (accents/tones).**
2. Generate 5 alternative search queries that are semantically similar to the cleaned query.
3. Return a JSON array with 6 total queries (the first is the cleaned original, the next 5 are similar queries).
4. All queries in the array must be preprocessed the same way: lowercase, no punctuation, no stopwords, and **must keep Vietnamese diacritics.**

User query: "` + rawQuery + `"`

	resp, err := llm.CallGemini(prompt)
	if err != nil {
		log.Fatalf("Failed to call Gemini API: %v", err)
	}

	queries, err := llm.ExtractQueries(resp)
	if err != nil {
		log.Fatalf("Failed to extract queries: %v", err)
	}

	fmt.Println("All queries:")
	for i, q := range queries {
		fmt.Printf("%d. %s\n", i+1, q)
	}

	firstQuery, err := llm.ExtractFirstQuery(resp)
	if err != nil {
		log.Fatalf("Failed to extract first query: %v", err)
	}
	fmt.Println("First query only:", firstQuery)
}
