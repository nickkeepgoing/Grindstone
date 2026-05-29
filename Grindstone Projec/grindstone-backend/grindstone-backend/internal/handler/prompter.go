package handler

// Mode defines the type for the prompt selection modes
type Mode string

const (
	Fast   Mode = "fast"
	Medium Mode = "medium"
	Full   Mode = "full"
)

// PromptRequest defines the structure for selecting prompts
type PromptRequest struct {
	Mode      Mode
	TurnCount int // 1 or 2
}

// PromptResult defines the structure for the selected prompt
type PromptResult struct {
	ID      string
	Content string
	Turns   int
	Mode    Mode
}

// GetPrompt selects a prompt based on the requested mode and turn count
func GetPrompt(req PromptRequest, jsonData []JSONData, jsonlData []JSONLData) (*PromptResult, error) {
	// TODO: Implement logic to select prompt based on mode, turns, and provided data
	// 1. Filter data based on req.TurnCount (1 or 2 turns)
	// 2. Select data based on req.Mode (Fast, Medium, Full)
	// 3. Return a PromptResult based on the selection

	// For now, return a dummy result as a placeholder
	return &PromptResult{
		ID:      "dummy-id",
		Content: "This is a dummy prompt content.",
		Turns:   req.TurnCount,
		Mode:    req.Mode,
	}, nil
}
