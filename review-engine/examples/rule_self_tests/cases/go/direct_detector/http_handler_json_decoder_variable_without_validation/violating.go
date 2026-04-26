package main
import ("encoding/json"; "net/http")
type Payload struct{ Name string }
func handler(w http.ResponseWriter, r *http.Request) { var payload Payload; decoder := json.NewDecoder(r.Body); decoder.Decode(&payload); use(payload.Name) }
