import os
import uuid
import subprocess
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from music21 import converter, environment

# ==== 환경변수, 경로 세팅 ====
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # 미사용시 제거 가능

UPLOAD_FOLDER = os.path.abspath('./results')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
MUSESCORE_PATH = '/usr/bin/musescore'  # 서버에 실제로 설치된 경로
environment.set('musescoreDirectPNGPath', MUSESCORE_PATH)
environment.set('musicxmlPath', MUSESCORE_PATH)

# ==== YuE 모델 세팅 ====
YUE_MODEL_ID = "m-a-p/YuE-s1-7B-anneal-jp-kr-cot"
yue_tokenizer = AutoTokenizer.from_pretrained(YUE_MODEL_ID)
yue_model = AutoModelForCausalLM.from_pretrained(YUE_MODEL_ID, torch_dtype="auto").to("cuda" if torch.cuda.is_available() else "cpu")

# ==== AI 멜로디 생성 ====
def generate_abc_with_yue(prompt):
    input_ids = yue_tokenizer(prompt, return_tensors="pt").input_ids.to(yue_model.device)
    output = yue_model.generate(input_ids, max_new_tokens=256)
    melody_abc = yue_tokenizer.decode(output[0], skip_special_tokens=True)
    # ABC 코드만 추출 (불필요 텍스트 제거)
    import re
    abc_pattern = r'X:\s*\d+.*?(?=X:|\Z)'  # 여러 곡이 연속 생성될 때 방지용
    abc_blocks = re.findall(abc_pattern, melody_abc, flags=re.DOTALL)
    if abc_blocks:
        return abc_blocks[0].strip()
    return melody_abc.strip()

# ==== ABC → MIDI 변환 ====
def abc_to_midi(abc_str, midi_path):
    try:
        s = converter.parse(abc_str, format='abc')
        s.write('midi', fp=midi_path)
        return True
    except Exception as e:
        print(f"ABC->MIDI 변환 에러: {e}")
        return False

# ==== MIDI + 가사 → WAV(보컬 합성, upsampler) ====
def midi_to_wav_with_tts(midi_path, lyrics, wav_path):
    # tts_infer.py를 subprocess로 실행
    # (가사/멜로디/midi 경로 등 tts_infer.py가 요구하는 파라미터로 수정!)
    try:
        cmd = [
            "python", "finetune/scripts/tts_infer.py",
            "--melody_path", midi_path,
            "--prompt", lyrics,
            "--outpath", wav_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("TTS 실행 에러:", result.stderr)
            return False
        return True
    except Exception as e:
        print(f"TTS 합성 subprocess 에러: {e}")
        return False

# ==== MIDI → PDF 악보 ====
def midi_to_pdf(midi_path, pdf_path):
    try:
        s = converter.parse(midi_path)
        s.write('lily.pdf', fp=pdf_path)  # musescore+pdf
        return True
    except Exception as e:
        print(f"MIDI->PDF 변환 에러: {e}")
        return False

# ========== Flask 라우트 ==========

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-lyrics', methods=['POST'])
def generate_lyrics():
    data = request.json or {}
    topic = data.get('topic', '')
    if not topic:
        return jsonify({'error': 'No topic provided.'}), 400
    # (OpenAI API 사용 부분은 제거. 오로지 YuE 기반 생성만 사용)
    prompt = f"{topic}에 어울리는 ABC notation으로 된 멜로디를 만들어줘.\n장르/감정/스타일 등 추가 가능"
    abc_code = generate_abc_with_yue(prompt)
    return jsonify({'abc_code': abc_code})

@app.route('/generate-song', methods=['POST'])
def generate_song():
    data = request.json or {}
    abc_code = data.get('abc_code', '')
    lyrics = data.get('lyrics', '')  # 보컬 가사
    if not abc_code or not lyrics:
        return jsonify({'error': 'abc_code와 lyrics가 필요합니다.'}), 400

    song_id = str(uuid.uuid4())
    midi_path = os.path.join(UPLOAD_FOLDER, f"song_{song_id}.mid")
    wav_path = os.path.join(UPLOAD_FOLDER, f"song_{song_id}.wav")

    if not abc_to_midi(abc_code, midi_path):
        return jsonify({'error': 'ABC → MIDI 변환 실패'}), 500

    if not midi_to_wav_with_tts(midi_path, lyrics, wav_path):
        return jsonify({'error': '보컬 합성(TTS) 실패'}), 500

    return jsonify({
        'midi_path': os.path.basename(midi_path),
        'audio_path': os.path.basename(wav_path),
        'song_id': song_id
    })

@app.route('/generate-score', methods=['POST'])
def generate_score():
    data = request.json or {}
    midi_path = data.get('midi_path', '')
    song_id = data.get('song_id', str(uuid.uuid4()))
    if not midi_path:
        return jsonify({'error': 'midi_path가 필요합니다.'}), 400
    midi_path_full = os.path.join(UPLOAD_FOLDER, os.path.basename(midi_path))
    pdf_path = os.path.join(UPLOAD_FOLDER, f"song_{song_id}.pdf")
    if not midi_to_pdf(midi_path_full, pdf_path):
        return jsonify({'error': 'MIDI → PDF 악보 변환 실패'}), 500
    return jsonify({'score_path': os.path.basename(pdf_path)})

@app.route('/download/<path:filename>')
def download(filename):
    safe_name = secure_filename(filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_name)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True)

# ========== 서버 실행 ==========
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

