package main
import ("io"; "net/http")
func demo() { resp, err := http.Get("https://example.invalid"); if err != nil { return }; io.ReadAll(resp.Body) }
