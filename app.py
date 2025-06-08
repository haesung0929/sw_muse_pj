import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# 환경변수 로딩
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

UPLOAD_FOLDER = os.path.abspath('./results')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Hugging Face 모델명
YUE_MODEL_NAME = "m-a-p/YuE-s1-7B-anneal-jp-kr-cot"
UPSAMPLER_MODEL_NAME = "m-a-p/YuE-upsampler"

# 모델 캐시 전역 변수 (최초 1회만 로드)
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoModel, AutoProcessor
import torch

yue_tokenizer = AutoTokenizer.from_pretrained(YUE_MODEL_NAME)
yue_model = AutoModelForCausalLM.from_pretrained(YUE_MODEL_NAME, torch_dtype="auto").to("cuda" if torch.cuda.is_available() else "cpu")

upsampler_processor = AutoProcessor.from_pretrained(UPSAMPLER_MODEL_NAME)
upsampler_model = AutoModel.from_pretrained(UPSAMPLER_MODEL_NAME).to("cuda" if torch.cuda.is_available() else "cpu")

# ========= 예시 함수들 =========

def generate_lyrics_with_gpt(topic):
    import openai
    openai.api_key = OPENAI_API_KEY
    prompt = f"{topic}에 어울리는 노래 가사 한 소절을 만들어줘."
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100
    )
    return response['choices'][0]['message']['content'].strip()

def generate_song_with_yue(lyrics, style, tempo, genre, accompaniment, mood):
    # UUID 파일명 생성
    song_id = str(uuid.uuid4())
    midi_path = os.path.join(UPLOAD_FOLDER, f"song_{song_id}.mid")
    # === YUE 모델 실제 사용 예시 ===
    # 간단하게 텍스트로부터 midi(멜로디) 생성, 상세 옵션(감정 등) 적용 필요시 수정
    prompt = f"{lyrics}\nStyle:{style}\nGenre:{genre}\nMood:{mood}\nTempo:{tempo}"
    input_ids = yue_tokenizer(prompt, return_tensors="pt").input_ids.to(yue_model.device)
    output = yue_model.generate(input_ids, max_new_tokens=128)
    generated_melody = yue_tokenizer.decode(output[0], skip_special_tokens=True)
    # 실제론 generated_melody를 midi 파일로 저장해야 함 (여기선 dummy 파일로 대체)
    with open(midi_path, 'wb') as f:
        f.write(b'')  # 실제 midi 변환 로직 필요!
    return midi_path, song_id

def synthesize_vocal_audio(midi_path, lyrics, song_id):
    audio_path = os.path.join(UPLOAD_FOLDER, f"song_{song_id}.wav")
    # === upsampler 모델 실제 사용 예시 ===
    # 실제론 midi/가사/멜로디와 함께 오디오 합성 처리 필요 (여긴 dummy)
    with open(audio_path, 'wb') as f:
        f.write(b'')  # 실제 오디오 합성 로직 필요!
    return audio_path

def create_score(midi_path, accompaniment, song_id):
    score_path = os.path.join(UPLOAD_FOLDER, f"song_{song_id}.pdf")
    # music21, MuseScore 등으로 midi를 pdf 악보로 변환 (여긴 dummy)
    with open(score_path, 'wb') as f:
        f.write(b'')  # 실제 악보 생성 로직 필요!
    return score_path

# ========== 라우터 ==========

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-lyrics', methods=['POST'])
def generate_lyrics():
    data = request.json or {}
    topic = data.get('topic', '')
    lyrics = data.get('lyrics', '')
    if lyrics:
        result = lyrics
    else:
        result = generate_lyrics_with_gpt(topic)
    return jsonify({'lyrics': result})

@app.route('/generate-song', methods=['POST'])
def generate_song():
    data = request.json or {}
    lyrics = data.get('lyrics', '')
    style = data.get('style', '')
    tempo = data.get('tempo', '')
    genre = data.get('genre', '')
    accompaniment = data.get('accompaniment', '')
    mood = data.get('mood', '')

    midi_path, song_id = generate_song_with_yue(
        lyrics=lyrics,
        style=style,
        tempo=tempo,
        genre=genre,
        accompaniment=accompaniment,
        mood=mood
    )
    audio_path = synthesize_vocal_audio(midi_path, lyrics, song_id)
    return jsonify({
        'midi_path': os.path.basename(midi_path),
        'audio_path': os.path.basename(audio_path),
        'song_id': song_id
    })

@app.route('/generate-score', methods=['POST'])
def generate_score():
    data = request.json or {}
    midi_path = data.get('midi_path', '')
    accompaniment = data.get('accompaniment', '')
    song_id = data.get('song_id', str(uuid.uuid4()))  # song_id가 없으면 새로 생성
    # midi_path가 상대경로면 보정
    midi_path_full = os.path.join(UPLOAD_FOLDER, os.path.basename(midi_path))
    score_path = create_score(midi_path_full, accompaniment, song_id)
    return jsonify({'score_path': os.path.basename(score_path)})

@app.route('/download/<path:filename>')
def download(filename):
    safe_name = secure_filename(filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_name)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True)

# ========== 실행 ==========

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
