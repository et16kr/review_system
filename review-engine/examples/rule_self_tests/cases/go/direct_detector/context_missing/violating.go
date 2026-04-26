package main
import "net/http"
func demo() { http.NewRequest("GET", "https://example.invalid", nil) }
