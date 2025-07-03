package elastic

type MetaData struct {
	Stars int    `json:"stars"`
	Owner string `json:"owner"`
	URL   string `json:"url"`
	ID    int64  `json:"id"`
}

type RepoDoc struct {
	Title    string   `json:"title"`
	ShortDes string   `json:"short_des"`
	Tags     []string `json:"tags"`
	Date     string   `json:"date"`
	MetaData MetaData `json:"meta_data"`
	Score    float64  `json:"score"`
}

func (r RepoDoc) ToMap() map[string]interface{} {
	return map[string]interface{}{
		"title":     r.Title,
		"short_des": r.ShortDes,
		"tags":      r.Tags,
		"date":      r.Date,
		"meta_data": r.MetaData,
	}
}

type RepoFilters struct {
	Language      *string  `json:"language"`
	Libraries     []string `json:"libraries"`
	CreatedAfter  *string  `json:"created_after"`
	CreatedBefore *string  `json:"created_before"`
	StarsMin      *int     `json:"stars_min"`
	Topics        []string `json:"topics"`
}
