package handler

import (
	"encoding/json"
	"io/ioutil"
	"os"
)

// LoadJSONL parses a JSONL file into a slice of JSONLData
func LoadJSONL(filePath string) ([]JSONLData, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var data []JSONLData
	decoder := json.NewDecoder(file)
	for decoder.More() {
		var entry JSONLData
		if err := decoder.Decode(&entry); err != nil {
			return nil, err
		}
		data = append(data, entry)
	}
	return data, nil
}

// LoadJSON parses a JSON file into a JSONData struct
func LoadJSON(filePath string) (*JSONData, error) {
	file, err := ioutil.ReadFile(filePath)
	if err != nil {
		return nil, err
	}

	var data JSONData
	if err := json.Unmarshal(file, &data); err != nil {
		return nil, err
	}
	return &data, nil
}
