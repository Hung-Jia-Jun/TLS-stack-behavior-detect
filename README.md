# TLS 深度行為指紋探測實驗環境

本專案實現論文「殺死那隻鸚鵡：基於深度行為的指紋探測識別」第 4.3 節的劫持式攻擊探測方法。

論文連結：
https://github.com/acgdaily/papers/blob/master/2025-10/01_%E6%9D%80%E6%AD%BB%E9%82%A3%E5%8F%AA%E9%B9%A6%E9%B9%89_TLS%E5%9F%BA%E4%BA%8E%E6%B7%B1%E5%BA%A6%E8%A1%8C%E4%B8%BA%E7%9A%84%E6%8C%87%E7%BA%B9%E6%8E%A2%E6%B5%8B%E8%AF%86%E5%88%AB/%E7%A0%94%E7%A9%B6%E6%8A%A5%E5%91%8A.pdf

透過在 TLS 握手階段（ClientHello 之後、ServerHello 之前）注入三種不同類型的 TLS Record，
觀察不同 TLS 堆疊對這些非標準紀錄的容忍行為差異，藉此識別客戶端所使用的 TLS 實現。

## 架構概覽

```
Client (瀏覽器/工具)
    |
    | TCP:443
    v
OpenResty (stream 層)
    |  preread_by_lua_block:
    |    1. 讀取 ClientHello
    |    2. 注入探測包 (Alert / CCS / AppData)
    |    3. 記錄各類型的成功發送次數
    |    4. 比對指紋窗口，決定放行或攔截
    |    5. 放行者加入白名單 (TTL 5 秒)
    |
    | proxy_pass 127.0.0.1:8443
    v
OpenResty (http 層, TLS 終端)
    |
    v
  回應 "OK"
```


## 探測包定義

根據論文表 2.5-1，使用以下三種 TLS Record 作為探測手段：

A. Warning Alert (Content Type 0x15)

    \x15\x03\x03\x00\x02\x01\x64
     |    |         |    |    |
     |    |         |    |    Description: 100
     |    |         |    Level: Warning (1)
     |    |         Length: 2
     |    Version: TLS 1.2
     Content Type: Alert (21)

B. ChangeCipherSpec (Content Type 0x14)

    \x14\x03\x03\x00\x01\x01
     |    |         |    |
     |    |         |    CCS Type: 1
     |    |         Length: 1
     |    Version: TLS 1.2
     Content Type: ChangeCipherSpec (20)

C. Empty Application Data (Content Type 0x17)

    \x17\x03\x03\x00\x00
     |    |         |
     |    |         Length: 0
     |    Version: TLS 1.2
     Content Type: Application Data (23)


## 論文表 2.5-1 計數器最大值

    TLS 堆疊            Alert (Warning)    CCS (TLS 1.3)    Empty AppData
    ────────────────     ───────────────    ──────────────    ─────────────
    BoringSSL (Chrome)   4                  32*               32*
    NSS (Firefox)        不限制              1                 不限制
    Safari               4                  32*               32*
    OpenSSL 1.1.1        4                  32*               32*
    GnuTLS               0                  不限制             不限制
    Cloudflare           4                  32*               32*
    Golang               16*                16*               16*

    * 相同角標為共享計數器。當發送第 n 個包後收到 Alert 或關閉則最大值為 n-1。


## 實測結果

依序發送 50 個 Alert、35 個 CCS、35 個 AppData，間隔 50ms。

    工具                TLS 堆疊           Alert    CCS    AppData    判定
    ────────────────    ────────────────   ─────    ───    ───────    ──────
    curl                OpenSSL 3.0        4        0      0          攔截
    k6                  Go stdlib          4        0      0          攔截
    Go http.Client      crypto/tls 1.26    21       0      0          攔截
    Chrome              BoringSSL          9-12     0      0          放行
    Firefox             NSS                50       5      0          放行
    Safari              WebKit             9-12     0      0          放行

實測值與論文理論值的差異來自 TCP 發送緩衝區：server 端 sock:send() 在客戶端
實際處理並關閉連線之前，可能已有數個包寫入 TCP buffer 而回報成功。


## 指紋判定規則

    Alert 得分    判定                          動作
    ──────────    ────────────────────────      ──────
    <= 3          Socket 已關閉 (跳過)           不判定
    4 - 7         curl / k6 / OpenSSL           攔截
    8 - 14        Chrome / BoringSSL / Safari   放行
    15 - 35       Golang (MaxUselessRecords=16) 攔截
    >= 40         Firefox / NSS                 放行 (提前判定，主動發送 Close Notify)


## 環境需求

- Docker 與 Docker Compose
- Go 1.25+（測試 Go 標準庫用）
- k6（壓測工具）
- curl
- 自簽憑證（server.crt / server.key）


## 啟動服務

```
docker compose up -d
```

重新載入設定（修改 nginx.conf 後）：

```
docker compose restart
```


## 測試指令

1. 即時監控日誌

```
docker logs -f openresty-tls-probe
```

觀察每個連線的指紋向量與判定結果。


2. 使用標準 Go http.Client 測試

```
cd stdlib_test
sudo go run main.go
```

使用標準 crypto/tls，不含任何 fork 修改。預期結果為 Alert 約 21，被判定為 Golang 並攔截。


3. 使用 openssl s_client 測試

```
openssl s_client -connect 127.0.0.1:443
```

底層為 OpenSSL，預期 Alert 約 4-5，被判定為 OpenSSL 並攔截。


4. 使用 k6 壓測

```
echo 'import http from "k6/http"; export default function () { http.get("https://localhost"); }' | K6_INSECURE_SKIP_TLS_VERIFY=true k6 run - --vus 2 --duration 3s --insecure-skip-tls-verify
```

k6 使用 Go 標準 TLS 堆疊。因為每次連線都會被探測攔截，預期 0 次成功迭代。


5. 使用 curl 測試

```
curl -vk https://localhost
```

首次連線會被探測並攔截。


6. 使用瀏覽器測試

直接在 Chrome / Firefox / Safari 中訪問 https://localhost。

首次會出現 ERR_SSL_PROTOCOL_ERROR（探測造成的連線中斷），
重新整理後因 IP 已在白名單中而直接通過，顯示 OK。

Firefox 的行為較特殊：瀏覽器會同時開啟多個 TCP 連線，部分連線會被 Firefox
自行以 Close Notify 關閉。對於這些預關閉的連線（Alert 得分 <= 3），
伺服器會跳過指紋判定，避免誤判。


## 檔案結構

    nginx.conf              OpenResty 配置，包含探測邏輯
    docker-compose.yml      容器編排
    server.crt / server.key 自簽憑證
    stdlib_test/            標準 Go http.Client 測試程式
    stdlib_test/main.go     使用 crypto/tls 的測試客戶端
    stdlib_test/go.mod      獨立模組（避免 fork 干擾）


## 注意事項

- 白名單 TTL 與 proxy_timeout 均設為 5 秒，確保白名單過期後既有連線也會被中斷並重新探測。
- 探測間隔設為 50ms，依論文建議等待客戶端處理完每個包後再發送下一個。
  間隔過小會導致 TCP 緩衝區累積，使實測值偏離論文理論值。
- 本實驗屬於論文 4.3 節的劫持式探測，會導致首次連線中斷。
  論文 4.2 節的重定向式探測不會中斷連線，但需要額外的 DNS 與路由配合。
