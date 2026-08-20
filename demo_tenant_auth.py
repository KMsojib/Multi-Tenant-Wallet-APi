"""
Demo Script: Tenant Resolution via X-Tenant-ID and API Key
"""

import requests
import json
import sys
import uuid
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"


def print_section(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def print_response(response):
    print(f"Status Code : {response.status_code}")
    try:
        print("Response    :")
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print("Response    :", response.text)


def main():
    # Make a unique name every time so it never conflicts
    unique_name = f"Demo Company {datetime.now().strftime('%H:%M:%S')}"

    print_section("1. Creating a new Tenant")

    try:
        res = requests.post(
            f"{BASE_URL}/api/tenants/",
            json={"name": unique_name},
            timeout=5
        )
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to the server.")
        print("Please run: python manage.py runserver")
        sys.exit(1)

    print_response(res)

    if res.status_code not in [200, 201]:
        print("\nFailed to create tenant.")
        return

    data = res.json()
    tenant_id = data.get("id")
    api_key = data.get("api_key")   # Will be None if api_key field is not added yet

    print(f"\n→ Tenant Name : {unique_name}")
    print(f"→ Tenant ID   : {tenant_id}")
    if api_key:
        print(f"→ API Key     : {api_key}")
    else:
        print("→ API Key     : Not available yet (you still need to add api_key field)")

    # -------------------------------------------------
    # Test 1: X-Tenant-ID
    # -------------------------------------------------
    print_section("2. Testing with X-Tenant-ID header")

    res = requests.get(
        f"{BASE_URL}/api/wallets/",
        headers={"X-Tenant-ID": str(tenant_id)}
    )
    print_response(res)

    if res.status_code == 200:
        print("\n✅ SUCCESS → X-Tenant-ID is working correctly")
    else:
        print("\n❌ FAILED → X-Tenant-ID is not working")

    # -------------------------------------------------
    # Test 2 & 3: API Key (only if available)
    # -------------------------------------------------
    if api_key:
        print_section("3. Testing with X-API-Key header")

        res = requests.get(
            f"{BASE_URL}/api/wallets/",
            headers={"X-API-Key": api_key}
        )
        print_response(res)

        if res.status_code == 200:
            print("\n✅ SUCCESS → X-API-Key is working correctly")
        else:
            print("\n❌ FAILED → X-API-Key is not working")

        print_section("4. Testing with Authorization: Api-Key")

        res = requests.get(
            f"{BASE_URL}/api/wallets/",
            headers={"Authorization": f"Api-Key {api_key}"}
        )
        print_response(res)

        if res.status_code == 200:
            print("\n✅ SUCCESS → Authorization: Api-Key is working")
        else:
            print("\n❌ FAILED → Authorization: Api-Key is not working")
    else:
        print_section("3 & 4. API Key tests skipped")
        print("The Tenant model does not have an `api_key` field yet.")
        print("Once you add it, this script will automatically test API Key authentication.")

    # -------------------------------------------------
    # Test 5: No header (should fail)
    # -------------------------------------------------
    print_section("5. Testing WITHOUT any header (should fail)")

    res = requests.get(f"{BASE_URL}/api/wallets/")
    print_response(res)

    if res.status_code in [400, 401]:
        print("\n✅ SUCCESS → Correctly rejected request without tenant header")
    else:
        print("\n❌ FAILED → Server should reject requests without tenant identification")

    print("\n" + "=" * 65)
    print("  Demo finished")
    print("=" * 65)


if __name__ == "__main__":
    main()