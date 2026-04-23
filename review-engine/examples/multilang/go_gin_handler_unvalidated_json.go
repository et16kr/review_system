package api

import (
    "net/http"

    "github.com/gin-gonic/gin"
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

func (h handler) createUser(c *gin.Context) {
    var req createUserRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": "bad request"})
        return
    }

    if err := h.service.CreateUser(req.Email, req.Role); err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create user"})
        return
    }

    c.Status(http.StatusCreated)
}
