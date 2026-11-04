#!/usr/bin/env python3

import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

USERNAME = "isra@arcagroup.com.mx"
PASSWORD = "Jehova773"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "izzi-epg.json"

def login():
    url = "https://www.izzigo.tv/managetv/core/user/login"
    data = urllib.parse.urlencode({"username": USERNAME, "password": PASSWORD}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)

def main():
    print("Login...", file=sys.stderr)
    resp = login()
    if resp.get("err") != 0:
        print(f"Error: {resp.get('mes')}", file=sys.stderr)
        return
    token = resp.get("userSessionToken")
    print(f"Token: {token[:50]}...", file=sys.stderr)
    print(f"Subscriber: {resp.get('subscriberId')}", file=sys.stderr)
    
    # Guarda el token para usarlo
    with open("token.json", "w") as f:
        json.dump({"token": token, "subscriber": resp.get("subscriberId")}, f)
    print("Token guardado en token.json", file=sys.stderr)

if __name__ == "__main__":
    main()
