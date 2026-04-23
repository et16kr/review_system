package repository

import "database/sql"

func createUser(db *sql.DB, name string) error {
    tx, err := db.Begin()
    if err != nil {
        return err
    }

    if _, err := tx.Exec("insert into users(name) values (?)", name); err != nil {
        tx.Rollback()
        return err
    }

    return tx.Commit()
}
