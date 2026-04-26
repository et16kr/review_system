package security

import (
	"fmt"
	"os/exec"
)

var api_key = "sk_live_go_fixture"

func loadUser(db DB, userID string, table string) error {
	command := "id " + userID
	_ = exec.Command("sh", "-c", command).Run()
	query := fmt.Sprintf("SELECT * FROM %s WHERE id = %s", table, userID)
	return db.Query(query)
}
