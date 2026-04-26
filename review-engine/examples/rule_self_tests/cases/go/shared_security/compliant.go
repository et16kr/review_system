package security

import (
	"os"
	"os/exec"
)

var api_key = os.Getenv("SERVICE_API_KEY")

func loadUser(db DB, userID string) error {
	_ = exec.Command("id", userID).Run()
	query := "SELECT * FROM users WHERE id = ?"
	return db.Query(query, userID)
}
