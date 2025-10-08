"""测试 AI 配置 API"""
import requests
import json

BASE_URL = "http://localhost:9999/api/v1"

# 1. 登录获取token
print("=" * 50)
print("1. 登录获取token")
print("=" * 50)
login_response = requests.post(
    f"{BASE_URL}/base/access_token",
    json={"username": "admin", "password": "123456"}
)
print(f"Status: {login_response.status_code}")
print(f"Response: {json.dumps(login_response.json(), indent=2, ensure_ascii=False)}")

if login_response.status_code != 200:
    print("登录失败!")
    exit(1)

token = login_response.json()["data"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. 获取用户菜单
print("\n" + "=" * 50)
print("2. 获取用户菜单")
print("=" * 50)
menu_response = requests.get(f"{BASE_URL}/base/usermenu", headers=headers)
print(f"Status: {menu_response.status_code}")
print(f"Response: {json.dumps(menu_response.json(), indent=2, ensure_ascii=False)}")

# 3. 获取AI模型列表
print("\n" + "=" * 50)
print("3. 获取AI模型列表")
print("=" * 50)
models_response = requests.get(f"{BASE_URL}/llm/models", headers=headers)
print(f"Status: {models_response.status_code}")
print(f"Response: {json.dumps(models_response.json(), indent=2, ensure_ascii=False)}")

# 4. 获取AI Prompt列表
print("\n" + "=" * 50)
print("4. 获取AI Prompt列表")
print("=" * 50)
prompts_response = requests.get(f"{BASE_URL}/llm/prompts", headers=headers)
print(f"Status: {prompts_response.status_code}")
print(f"Response: {json.dumps(prompts_response.json(), indent=2, ensure_ascii=False)}")

# 5. 创建新模型
print("\n" + "=" * 50)
print("5. 创建新模型")
print("=" * 50)
create_model_response = requests.post(
    f"{BASE_URL}/llm/models",
    headers=headers,
    json={
        "name": "测试模型",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test123456",
        "description": "测试用模型",
        "timeout": 60,
        "is_active": True,
        "is_default": False
    }
)
print(f"Status: {create_model_response.status_code}")
print(f"Response: {json.dumps(create_model_response.json(), indent=2, ensure_ascii=False)}")

# 6. 创建新Prompt
print("\n" + "=" * 50)
print("6. 创建新Prompt")
print("=" * 50)
create_prompt_response = requests.post(
    f"{BASE_URL}/llm/prompts",
    headers=headers,
    json={
        "name": "测试Prompt",
        "version": "v1.0",
        "system_prompt": "你是一个测试助手",
        "description": "测试用Prompt",
        "is_active": False
    }
)
print(f"Status: {create_prompt_response.status_code}")
print(f"Response: {json.dumps(create_prompt_response.json(), indent=2, ensure_ascii=False)}")

print("\n" + "=" * 50)
print("测试完成!")
print("=" * 50)

