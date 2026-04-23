package cache

import (
    "errors"
    "fmt"
    "io/fs"
)

func load(path string) error {
    readErr := readConfig(path)
    if errors.Is(readErr, fs.ErrNotExist) {
        return nil
    }
    return readErr
}

func readConfig(path string) error {
    return fmt.Errorf("read %s: %w", path, fs.ErrNotExist)
}
