# app.py
import os
import uuid
import requests
from flask import Flask, request, jsonify, send_from_directory, render_template
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLAB_API_BASE  = os.getenv("COLAB_API_BASE")  
# ex) https://443d-34-53-108-235.ngrok-free.app

app = Flask(__name__, template_folder='templates', static_folder='static')

RESULT_DIR = './results'
os.makedirs(RESULT_DIR, exist_ok=True)

# 0) 메인 페이지
@app.route('/')
def index():
    return render_template('index.html')

# 1) 가사 생성
@app.route("/generate-lyrics", methods=["POST"])
def generate_lyrics():
    data = request.get_json() or {}
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"lyrics": ""})

    import openai
    openai.api_key = OPENAI_API_KEY
    prompt = f"'{topic}'라는 주제로 16마디 분량의 한국어 노래 가사를 만들어줘. 운율과 구성을 신경 써서 작성해줘."
    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user", "content": prompt}],
        max_tokens=256,
        temperature=0.8
    )
    lyrics = res.choices[0].message.content.strip()
    return jsonify({"lyrics": lyrics})

# 2) 노래 생성 (멜로디+보컬 → MP3 파일 & 악보 PDF 파일 생성)
@app.route("/generate-song", methods=["POST"])
def generate_song():
    data = request.get_json() or {}
    lyrics        = data.get("lyrics", "").strip()
    style         = data.get("style", "").strip()
    tempo         = data.get("tempo", "").strip()
    genre         = data.get("genre", "").strip() or "pop"
    accompaniment = data.get("accompaniment", "").strip()

    if not lyrics:
        return jsonify({"error": "가사를 입력해주세요."}), 400

    files = {
        "lyrics":        (None, lyrics),
        "genre":         (None, genre),
        # style, tempo, accompaniment 를 colab 쪽에서 쓴다면 여기에 추가로 넘기시면 됩니다.
    }

    # 2-1) MP3 생성
    try:
        r_mp3 = requests.post(
            f"{COLAB_API_BASE}/generate?file=mp3",
            files=files, timeout=300
        )
        r_mp3.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"음악 생성 실패: {e}"}), 500

    # 2-2) PDF(악보) 생성
    try:
        r_pdf = requests.post(
            f"{COLAB_API_BASE}/generate?file=pdf",
            files=files, timeout=300
        )
        r_pdf.raise_for_status()
    except Exception as e:
        return jsonify({"error": f"악보 생성 실패: {e}"}), 500

    # 3) 로컬에 저장
    audio_name = f"{uuid.uuid4()}.mp3"
    pdf_name   = f"{uuid.uuid4()}.pdf"
    audio_path = os.path.join(RESULT_DIR, audio_name)
    pdf_path   = os.path.join(RESULT_DIR, pdf_name)

    with open(audio_path, "wb") as f:
        f.write(r_mp3.content)
    with open(pdf_path, "wb") as f:
        f.write(r_pdf.content)

    return jsonify({
        "audio_path": audio_name,
        "score_path": pdf_name
    })

# 3) 파일 다운로드
@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(RESULT_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    # 디버그 모드로 5000번 포트 실행
    app.run(host="0.0.0.0", port=5000, debug=True)
