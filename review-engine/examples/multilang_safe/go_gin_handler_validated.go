package api

import (
    "errors"
    "net/http"

    "github.com/gin-gonic/gin"
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

func createUser(c *gin.Context) {
    var req createUserRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": "bad request"})
        return
    }
    if err := req.Validate(); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
        return
    }

    c.Status(http.StatusCreated)
}
