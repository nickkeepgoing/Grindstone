package main

import (
	"fmt"

	"grindstone/internal/handler"
)

func main() {
	// ใช้ backtick สำหรับ Windows path
	jsonFilePath := `C:\Users\User\Desktop\Grindstone Projec\grindstone-backend\grindstone-backend\data\multiple_turn\thai\th-multi-001.json`

	jsonlFilePath := `C:\Users\User\Desktop\Grindstone Projec\grindstone-backend\grindstone-backend\data\thai\Hierarchy.jsonl`

	// 1. ทดสอบโหลด JSON
	jsonData, err := handler.LoadJSON(jsonFilePath)
	if err != nil {
		fmt.Println("Error loading JSON:", err)
	} else {
		fmt.Printf("JSON Loaded successfully: %+v\n", jsonData)
	}

	// 2. ทดสอบโหลด JSONL
	jsonlData, err := handler.LoadJSONL(jsonlFilePath)
	if err != nil {
		fmt.Println("Error loading JSONL:", err)
	} else {
		if len(jsonlData) > 0 {
			fmt.Printf("JSONL Loaded successfully. First entry: %+v\n", jsonlData[0])
		} else {
			fmt.Println("JSONL loaded but no data found.")
		}
	}
}
