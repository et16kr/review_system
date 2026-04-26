package main
func demo(db DB) error { tx, err := db.Begin(); if err != nil { return err }; return tx.Commit() }
