package worker

import "context"

func run(err error) {
    ctx := context.Background()
    _ = ctx
    go func() {
        panic(err)
    }()
}
