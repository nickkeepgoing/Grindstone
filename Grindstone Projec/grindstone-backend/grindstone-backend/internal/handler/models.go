package handler

// JSONLData represents the structure of the .jsonl files
type JSONLData struct {
	ID             string   `json:"id"`
	Text           string   `json:"text"`
	Tags           []string `json:"tags"`
	Severity       string   `json:"severity"`
	TargetBehavior string   `json:"target_behavior"`
	Language       string   `json:"language"`
}

// JSONData represents the structure of the .json files
type JSONData struct {
	SetID          string          `json:"set_id"`
	Runtime        RuntimeWrapper  `json:"runtime"`
	Turn           int             `json:"turn"`
	AttackPattern  string          `json:"attack_pattern"`
}

type RuntimeWrapper struct {
	Messages []RuntimeMessage `json:"messages"`
}

// RuntimeMessage represents the individual message structure within the JSON runtime list
type RuntimeMessage struct {
	Turn    int    `json:"turn"`
	Role    string `json:"role"`
	Content string `json:"content"`
}
