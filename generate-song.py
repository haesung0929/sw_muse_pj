import requests

url = "http://127.0.0.1:5000/generate-song"
payload = {
    "lyrics": "하늘을 보며 너를 그리던 그날의 노래"
}

response = requests.post(url, json=payload)

print("응답 상태:", response.status_code)
print("응답 결과:", response.json())
