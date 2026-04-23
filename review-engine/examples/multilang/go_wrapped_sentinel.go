package cache

import (
    "fmt"
    "io/fs"
)

func load(path string) error {
    err := readConfig(path)
    if err == fs.ErrNotExist {
        return nil
    }
    return err
}

func readConfig(path string) error {
    return fmt.Errorf("read %s: %w", path, fs.ErrNotExist)
}
