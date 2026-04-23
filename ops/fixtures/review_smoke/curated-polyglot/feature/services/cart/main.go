package cart

import "net/http"

func fetchCart(url string) error {
	resp, err := http.Get(url)
	if err != nil {
		return err
	}
	return nil
}
