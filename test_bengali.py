import requests

url = "http://localhost:8000/analyze/text"
data = {
    "user_id": 1,
    "text": "আমি খুব দুশ্চিন্তায় আছি"
}

response = requests.post(url, data=data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
