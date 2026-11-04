#!/usr/bin/env python3

import json
import urllib.request
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
import sys

USERNAME = "isra@arcagroup.com.mx"
PASSWORD = "Jehova773"
TZ = ZoneInfo("America/Mexico_City")

DEVICE_ID = "b9f63bb2-b4c9-4d6b-8820-c20c7f10127b"
PROFILE_ID = "18836121"
MODULE_ID = "/E5EoryV"

def login():
    url = "https://www.izzigo.tv/managetv/core/user/login"
    data = urllib.parse.urlencode({"username": USERNAME, "password": PASSWORD}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)

def get_license(token, content_id):
    provisioning = {
        "provisioning": [{
            "system": "verimatrix",
            "data": [{"name": "vuid", "value": DEVICE_ID}]
        }]
    }
    params = {
        "drm": "WV",
        "packaging": "DASH",
        "provisioningData": urllib.parse.quote(json.dumps(provisioning)),
        "url": f"multirights://elemental/SVC/{content_id}",
        "userSessionToken": token
    }
    url = f"https://be-cdn.izzigo.tv/streamlocators/getLicenseUrlByContent?{urllib.parse.urlencode(params)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
        "Authorization": token,
        "IRIS-HW-DEVICE-ID": DEVICE_ID,
        "IRIS-DEVICE-STATUS": "ACTIVE",
        "IRIS-APP-VERSION": "11.6.22(0)_prd",
        "IRIS-PROFILE-ID": PROFILE_ID,
        "IRIS-APP-NAME": "izzi go",
        "IRIS-DEVICE-TYPE": "LINUX/CHROME",
        "IRIS-DEVICE-REGION": "METRO",
        "IRIS-DEVICE-CLASS": "PC",
        "IRIS-MODULE-ID": MODULE_ID,
        "Origin": "https://www.izzigo.tv",
        "Referer": "https://www.izzigo.tv/"
    }
    
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)

def main():
    print("Login...", file=sys.stderr)
    resp = login()
    if resp.get("err") != 0:
        print(f"Error: {resp.get('mes')}", file=sys.stderr)
        return
    token = resp.get("userSessionToken")
    print(f"Token OK", file=sys.stderr)
    
    # Cambia el content_id según el canal
    content_id = "601333"
    print(f"Obteniendo licencia para {content_id}...", file=sys.stderr)
    
    try:
        license_resp = get_license(token, content_id)
        print(json.dumps(license_resp, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
