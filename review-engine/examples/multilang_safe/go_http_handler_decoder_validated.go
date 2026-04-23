package api

import (
    "encoding/json"
    "errors"
    "net/http"
)

var errInvalidRequest = errors.New("invalid request")

type createUserRequest struct {
    Email string `json:"email"`
    Role  string `json:"role"`
}

func (r createUserRequest) Validate() error {
    if r.Email == "" || r.Role == "" {
        return errInvalidRequest
    }
    return nil
}

func createUser(w http.ResponseWriter, r *http.Request) {
    var req createUserRequest
    decoder := json.NewDecoder(r.Body)
    decoder.DisallowUnknownFields()
    if err := decoder.Decode(&req); err != nil {
        http.Error(w, "bad request", http.StatusBadRequest)
        return
    }
    if err := req.Validate(); err != nil {
        http.Error(w, "invalid request", http.StatusBadRequest)
        return
    }

    w.WriteHeader(http.StatusCreated)
}
