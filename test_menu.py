"""测试菜单API"""
import requests
import json

BASE_URL = "http://localhost:9999/api/v1"

# 1. 登录
login_response = requests.post(
    f"{BASE_URL}/base/access_token",
    json={"username": "admin", "password": "123456"}
)

if login_response.status_code != 200:
    print("登录失败!")
    print(login_response.text)
    exit(1)

token = login_response.json()["data"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. 获取菜单
menu_response = requests.get(f"{BASE_URL}/base/usermenu", headers=headers)
print("菜单响应:")
print(json.dumps(menu_response.json(), indent=2, ensure_ascii=False))

# 3. 获取API权限
api_response = requests.get(f"{BASE_URL}/base/userapi", headers=headers)
print("\nAPI权限响应:")
print(json.dumps(api_response.json(), indent=2, ensure_ascii=False))

