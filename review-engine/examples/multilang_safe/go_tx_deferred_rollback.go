package repository

import "database/sql"

func createUser(db *sql.DB, name string) error {
    tx, err := db.Begin()
    if err != nil {
        return err
    }
    defer tx.Rollback()

    if _, err := tx.Exec("insert into users(name) values (?)", name); err != nil {
        return err
    }

    return tx.Commit()
}
