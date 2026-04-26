package main
import "net/http"
func demo() { client := &http.Client{}; client.Get("https://example.invalid") }
