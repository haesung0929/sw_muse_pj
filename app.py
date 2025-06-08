import os
import uuid
import subprocess
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from music21 import converter, environment

# --- 환경 세팅 ---
load_dotenv()
UPLOAD_FOLDER = os.path.abspath('./results')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
MUSESCORE_PATH = '/usr/bin/musescore'
environment.set('musescoreDirectPNGPath', MUSESCORE_PATH)
environment.set('musicxmlPath', MUSESCORE_PATH)

# --- YuE 모델 inference 경로 (서브모듈) ---
YUE_INFER_PATH = "YuE/inference/infer.py"

app = Flask(__name__)

# --- 1. (신규) 가사 자동 생성 ---
def generate_lyrics_with_gpt(topic):
    # 실제 production에선 OpenAI API/LLM/koGPT 등을 사용!
    # 여기선 예시로 프롬프트 조합
    if not topic:
        return "주제를 입력해주세요!"
    # 심플 버전 (실전 AI API 연동시 이 함수만 교체)
    return f"{topic}에 관한 AI 작사 예시 한 소절입니다.\n(실제로는 GPT/LLM 기반 가사 생성 API 결과)"

@app.route('/generate-lyrics', methods=['POST'])
def generate_lyrics():
    data = request.json or {}
    topic = data.get('topic', '')
    result_lyrics = generate_lyrics_with_gpt(topic)
    return jsonify({'lyrics': result_lyrics})

# --- 2. AI 멜로디(ABC) 생성 및 곡/보컬 합성 ---
def generate_abc_with_yue(prompt, style="", genre="", tempo="", mood="", output_dir=UPLOAD_FOLDER):
    run_id = str(uuid.uuid4())
    result_dir = os.path.join(output_dir, run_id)
    os.makedirs(result_dir, exist_ok=True)
    full_prompt = f"{prompt} 스타일:{style} 장르:{genre} 템포:{tempo} 분위기:{mood}".strip()
    cmd = [
        "python3", YUE_INFER_PATH,
        "--prompt", full_prompt,
        "--output_dir", result_dir,
        "--use_tts", "True"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("YUE 추론 에러:", result.stderr)
        return None, None
    midi_path = None
    wav_path = None
    for fname in os.listdir(result_dir):
        if fname.endswith('.mid') or fname.endswith('.midi'):
            midi_path = os.path.join(result_dir, fname)
        elif fname.endswith('.wav'):
            wav_path = os.path.join(result_dir, fname)
    return midi_path, wav_path

# --- 3. MIDI → PDF 악보 변환 ---
def midi_to_pdf(midi_path, output_dir=UPLOAD_FOLDER):
    pdf_path = os.path.splitext(midi_path)[0] + ".pdf"
    try:
        s = converter.parse(midi_path)
        s.write('lily.pdf', fp=pdf_path)
        return pdf_path
    except Exception as e:
        print(f"MIDI->PDF 변환 에러: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-song', methods=['POST'])
def generate_song():
    data = request.json or {}
    topic = data.get('topic', '')
    lyrics = data.get('lyrics', '')
    style = data.get('style', '')
    genre = data.get('genre', '')
    tempo = data.get('tempo', '')
    mood = data.get('mood', '')
    accompaniment = data.get('accompaniment', '')

    if not lyrics and topic:
        # 가사가 비어있고 주제가 있으면 자동생성
        lyrics = generate_lyrics_with_gpt(topic)
    if not topic and not lyrics:
        return jsonify({'error': '주제나 가사 중 하나는 입력해야 합니다.'}), 400

    prompt = lyrics if lyrics else topic

    midi_path, wav_path = generate_abc_with_yue(
        prompt=prompt,
        style=style,
        genre=genre,
        tempo=tempo,
        mood=mood,
        output_dir=UPLOAD_FOLDER
    )
    if not midi_path or not wav_path:
        return jsonify({'error': 'AI 노래 생성 실패'}), 500

    midi_file = os.path.basename(midi_path)
    wav_file = os.path.basename(wav_path)

    return jsonify({
        'midi_path': midi_file,
        'audio_path': wav_file
    })

@app.route('/generate-score', methods=['POST'])
def generate_score():
    data = request.json or {}
    midi_path = data.get('midi_path', '')
    if not midi_path:
        return jsonify({'error': 'midi_path가 필요합니다.'}), 400
    midi_path_full = os.path.join(UPLOAD_FOLDER, os.path.basename(midi_path))
    pdf_path = midi_to_pdf(midi_path_full, output_dir=UPLOAD_FOLDER)
    if not pdf_path:
        return jsonify({'error': 'MIDI → PDF 악보 변환 실패'}), 500
    return jsonify({'score_path': os.path.basename(pdf_path)})

@app.route('/download/<path:filename>')
def download(filename):
    safe_name = secure_filename(filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_name)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
