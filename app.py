import os
import uuid
import requests
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLAB_API_BASE = os.getenv("COLAB_API_BASE")  # 예: http://colab-api-url:port

app = Flask(__name__)

RESULT_DIR = './results'
os.makedirs(RESULT_DIR, exist_ok=True)

# 1. 가사 생성
@app.route("/generate-lyrics", methods=["POST"])
def generate_lyrics():
    data = request.get_json()
    topic = data.get("topic", "")
    if not topic:
        return jsonify({"lyrics": ""})
    import openai
    openai.api_key = OPENAI_API_KEY
    prompt = f"'{topic}'라는 주제로 16마디 분량의 한국어 노래 가사를 만들어줘. 운율과 구성을 신경 써서 써줘."
    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user", "content":prompt}],
        max_tokens=256,
        temperature=0.8
    )
    lyrics = completion.choices[0].message.content.strip()
    return jsonify({"lyrics": lyrics})

# 2. 노래(멜로디+보컬) 생성 (Colab에 요청, 파일 저장 후 경로 반환)
@app.route("/generate-song", methods=["POST"])
def generate_song():
    data = request.get_json()
    # 입력 데이터
    lyrics = data.get("lyrics", "")
    style = data.get("style", "")
    tempo = data.get("tempo", "")
    genre = data.get("genre", "")
    accompaniment = data.get("accompaniment", "")

    payload = {
        "lyrics": lyrics,
        "style": style,
        "tempo": tempo,
        "genre": genre,
        "accompaniment": accompaniment
    }
    # Colab 서버에 POST 요청
    colab_url = f"{COLAB_API_BASE}/generate-song"
    r = requests.post(colab_url, json=payload)
    r.raise_for_status()
    result = r.json()
    # Colab에서 반환: midi_url, audio_url (외부 주소)
    midi_url = result["midi_url"]
    audio_url = result["audio_url"]
    # 서버에 파일 저장(다운로드)
    midi_path = os.path.join(RESULT_DIR, str(uuid.uuid4()) + ".mid")
    audio_path = os.path.join(RESULT_DIR, str(uuid.uuid4()) + ".wav")
    with requests.get(midi_url, stream=True) as rfile:
        with open(midi_path, "wb") as f:
            for chunk in rfile.iter_content(chunk_size=8192):
                f.write(chunk)
    with requests.get(audio_url, stream=True) as rfile:
        with open(audio_path, "wb") as f:
            for chunk in rfile.iter_content(chunk_size=8192):
                f.write(chunk)
    return jsonify({"midi_path": midi_path, "audio_path": audio_path})

# 3. 악보 생성 (MIDI → PDF, 또는 Colab에서 PDF 반환)
@app.route("/generate-score", methods=["POST"])
def generate_score():
    data = request.get_json()
    midi_path = data.get("midi_path")
    accompaniment = data.get("accompaniment", "")
    # Colab 서버에 파일 업로드 + 요청
    colab_url = f"{COLAB_API_BASE}/generate-score"
    with open(midi_path, "rb") as f:
        files = {'midi_file': f}
        r = requests.post(colab_url, files=files, data={'accompaniment': accompaniment})
        r.raise_for_status()
        # Colab에서 pdf_url 반환
        pdf_url = r.json()["pdf_url"]
        pdf_path = os.path.join(RESULT_DIR, str(uuid.uuid4()) + ".pdf")
        with requests.get(pdf_url, stream=True) as rfile:
            with open(pdf_path, "wb") as fpdf:
                for chunk in rfile.iter_content(chunk_size=8192):
                    fpdf.write(chunk)
    return jsonify({"score_path": pdf_path})

# 4. 파일 다운로드
@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(RESULT_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)
