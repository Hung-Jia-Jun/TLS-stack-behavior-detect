package main

import (
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
)

func main() {
	fmt.Println("=== 使用【標準 Go http.Client】進行探測 ===")
	fmt.Println("論文預期 (表 2.5-1):")
	fmt.Println("  Alert(Warning)=16*  CCS=16*  AppData=16*  (共享計數器)")
	fmt.Println()
	fmt.Println("正在發起 HTTPS 連線 (目標: https://localhost)...")

	client := &http.Client{
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{
				InsecureSkipVerify: true,
			},
		},
	}

	resp, err := client.Get("https://localhost")
	if err != nil {
		fmt.Printf("\n[結果] 連線結束: %v\n", err)
		fmt.Println("=> 請查看 Nginx 日誌中的三維指紋向量")
	} else {
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		fmt.Printf("\n[結果] HTTP %d\n", resp.StatusCode)
		fmt.Printf("[回應] %s\n", string(body))
	}
}
