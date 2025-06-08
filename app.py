import os
import tempfile
import base64

from flask import Flask, request, send_file, jsonify, render_template
from dotenv import load_dotenv
from openai import OpenAI
import music21
from music21 import instrument as m21instr

# ───────────────────────────────────────────────────────────────────────────────
# (1) 환경 변수 로드 & Flask 앱 초기화
# ───────────────────────────────────────────────────────────────────────────────
load_dotenv()
# load_dotenv() 호출 직후
# 기존 하드코딩 대신 환경변수로부터 MuseScore 경로를 불러옵니다.
MUSICXML_PATH = os.getenv("MUSESCORE_PATH", "/usr/bin/musescore")
MUSESCORE_DIRECT_PNG_PATH = os.getenv("MUSESCORE_DIRECT_PNG_PATH", MUSICXML_PATH)

# music21 환경에 설정
music21.environment.set("musicxmlPath", MUSICXML_PATH)
music21.environment.set("musescoreDirectPNGPath", MUSESCORE_DIRECT_PNG_PATH)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise RuntimeError("환경 변수에 OPENAI_API_KEY를 설정하세요.")

app = Flask(__name__)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ───────────────────────────────────────────────────────────────────────────────
# (2) Music21 + MuseScore 환경 설정 (악보 PNG 생성용)
# ───────────────────────────────────────────────────────────────────────────────
# music21 환경에 설정
music21.environment.set("musicxmlPath", MUSICXML_PATH)
music21.environment.set("musescoreDirectPNGPath", MUSESCORE_DIRECT_PNG_PATH)

# ───────────────────────────────────────────────────────────────────────────────
# (3) 가사 생성 함수 (YUE 사용)
# ───────────────────────────────────────────────────────────────────────────────
def generate_lyrics(topic: str, feeling: str, genre: str, min_lines: int = 4) -> str:
    prompt = (
        f"'{topic}'이라는 주제로, '{feeling}' 느낌의 '{genre}' 장르 한국어 노래 가사를 써줘. "
        f"최소 {min_lines}줄 이상."
    )
    response = openai_client.chat.completions.create(
        model="<여기에-정확한-yue-가사-모델명>",  # 예: "yue-lyrics-v1"
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=512
    )
    return response.choices[0].message.content.strip()

# ───────────────────────────────────────────────────────────────────────────────
# (4) 멜로디+보컬 생성 함수 (YUE 사용)
# ───────────────────────────────────────────────────────────────────────────────
def generate_melody(lyrics: str, feeling: str, genre: str) -> bytes:
    prompt = f"[{feeling} | {genre}] 다음 가사로 자연스러운 노래(보컬+멜로디) 생성:\n{lyrics}"
    response = openai_client.chat.completions.create(
        model="<여기에-정확한-yue-오디오-모델명>",  # 예: "yue-music-v1"
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2048
    )
    audio_b64 = response.choices[0].message.content.strip()
    return base64.b64decode(audio_b64)

# ───────────────────────────────────────────────────────────────────────────────
# (5) 악보 생성 함수 (Music21 이용)
# ───────────────────────────────────────────────────────────────────────────────
def generate_score(chords: list[str], repeats: int, instrument_name: str) -> bytes:
    score = music21.stream.Score()
    part = music21.stream.Part()

    if instrument_name.lower() == "piano":
        instr_obj = m21instr.Piano()
    elif instrument_name.lower() == "guitar":
        instr_obj = m21instr.Guitar()
    elif instrument_name.lower() == "violin":
        instr_obj = m21instr.Violin()
    elif instrument_name.lower() == "flute":
        instr_obj = m21instr.Flute()
    else:
        instr_obj = m21instr.Piano()

    part.append(instr_obj)
    part.append(music21.metadata.Metadata(title=f"악보 ({instrument_name})"))
    part.metadata.title = f"악보 ({instrument_name})"
    part.append(music21.meter.TimeSignature("4/4"))
    part.append(music21.key.Key("C"))

    for _ in range(repeats):
        for chord_symbol in chords:
            c = music21.chord.Chord(chord_symbol)
            c.quarterLength = 4
            part.append(c)

    score.append(part)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
        png_path = f.name
    score.write("musicxml.png", fp=png_path)
    with open(png_path, "rb") as pf:
        png_bytes = pf.read()
    os.remove(png_path)
    return png_bytes

# ───────────────────────────────────────────────────────────────────────────────
# (6) Flask 라우트 정의
# ───────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate-lyrics", methods=["POST"])
def route_generate_lyrics():
    data = request.get_json() or {}
    topic = data.get("topic", "").strip()
    feeling = data.get("feeling", "").strip()
    genre = data.get("genre", "").strip()
    if not topic:
        return jsonify({"error": "주제를 입력하세요."}), 400
    if not feeling:
        return jsonify({"error": "느낌을 선택하세요."}), 400
    if not genre:
        return jsonify({"error": "장르를 선택하세요."}), 400

    lyrics = generate_lyrics(topic, feeling, genre)
    return jsonify({"lyrics": lyrics})


@app.route("/generate-melody", methods=["POST"])
def route_generate_melody():
    data = request.get_json() or {}
    lyrics = data.get("lyrics", "").strip()
    feeling = data.get("feeling", "").strip()
    genre = data.get("genre", "").strip()
    if not lyrics:
        return jsonify({"error": "가사가 없습니다."}), 400
    if not feeling or not genre:
        return jsonify({"error": "느낌/장르가 없습니다."}), 400

    audio_bytes = generate_melody(lyrics, feeling, genre)
    # YUE가 MP3로 반환한다고 가정
    tmp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_audio.write(audio_bytes)
    tmp_audio.flush()
    tmp_audio.close()

    return send_file(
        tmp_audio.name,
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name="melody.mp3"
    )


@app.route("/generate-score", methods=["POST"])
def route_generate_score():
    data = request.get_json() or {}
    instrument_name = data.get("instrument", "").strip()
    if not instrument_name:
        return jsonify({"error": "악기를 선택하세요."}), 400

    chords = ["C", "G", "Am", "F"]
    repeats = 2

    png_bytes = generate_score(chords, repeats, instrument_name)
    b64_png = base64.b64encode(png_bytes).decode("utf-8")
    return jsonify({"score_png": b64_png})


# ───────────────────────────────────────────────────────────────────────────────
# (7) Flask 앱 실행
# ───────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
