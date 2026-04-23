package api

import (
    "encoding/json"
    "net/http"
)

type createUserRequest struct {
    Email string `json:"email"`
    Role  string `json:"role"`
}

type userService interface {
    CreateUser(email string, role string) error
}

type handler struct {
    service userService
}

func (h handler) createUser(w http.ResponseWriter, r *http.Request) {
    var req createUserRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "bad request", http.StatusBadRequest)
        return
    }

    if err := h.service.CreateUser(req.Email, req.Role); err != nil {
        http.Error(w, "failed to create user", http.StatusInternalServerError)
        return
    }

    w.WriteHeader(http.StatusCreated)
}
