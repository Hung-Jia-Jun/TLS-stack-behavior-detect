#!/usr/bin/env python3
"""
requests_test.py — Python requests 庫 HTTPS 連線測試
目標: https://localhost (port 443, 4.3 劫持式探測)

Python requests 底層使用 urllib3，urllib3 再透過 Python ssl module
呼叫系統 OpenSSL。因此指紋行為與 curl (OpenSSL) 完全相同。

預期辨識結果 (4.3 劫持式探測):
  Alert 計數:  ~4 (OpenSSL 在收到非法 Record 後迅速回應 Alert)
  判定:         curl/k6/OpenSSL -> 封鎖
  連線結果:    Timeout (探測封鎖後不轉發，client 無回應等到 timeout)

用法:
    python3 requests_test.py
"""

import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TARGET = "https://localhost"

print("=" * 52)
print("  Python requests HTTPS 連線測試")
print("  目標:", TARGET)
print("  底層: urllib3 -> ssl module -> OpenSSL")
print("=" * 52)
print()
print("預期行為:")
print("  劫持式探測 發送探針 -> Alert 計數 ≈4")
print("  判定為 OpenSSL -> 連線被封鎖 -> timeout")
print()

try:
    resp = requests.get(TARGET, verify=False, timeout=10)
    print(f"[結果] HTTP {resp.status_code}  (放行：白名單或非 OpenSSL)")
    print(f"[回應] {resp.text.strip()}")

except requests.exceptions.ReadTimeout:
    print("[結果] Timeout  (預期：探測後判定為 OpenSSL，連線被封鎖)")

except requests.exceptions.ConnectionError as e:
    print("[結果] 連線中斷  (探測後連線被強制關閉)")
    print(f"       {e}")

except Exception as e:
    print(f"[結果] 其他錯誤: {type(e).__name__}: {e}")
