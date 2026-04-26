package main
import "github.com/gin-gonic/gin"
type Payload struct{ Name string }
func handler(c *gin.Context) { var payload Payload; c.ShouldBindJSON(&payload); use(payload.Name) }
