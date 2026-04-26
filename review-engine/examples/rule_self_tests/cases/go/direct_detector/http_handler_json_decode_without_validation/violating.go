package main
import ("encoding/json"; "net/http")
type Payload struct{ Name string }
func handler(w http.ResponseWriter, r *http.Request) { var payload Payload; json.NewDecoder(r.Body).Decode(&payload); use(payload.Name) }
