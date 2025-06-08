# app.py
import os
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

# 환경변수에서 OPENAI KEY 로딩 (pip install python-dotenv)
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

UPLOAD_FOLDER = './results'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ======== 예시 함수들 ==========

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
    # 실제 YUE 모델 실행 코드로 바꿔야 함!
    # 결과물은 song.mid 저장
    midi_path = './results/song.mid'
    # 임시 dummy 파일 생성 (테스트용)
    with open(midi_path, 'wb') as f: f.write(b'')
    return midi_path

def synthesize_vocal_audio(midi_path, lyrics):
    # 실제 upsampler, 보컬 합성 코드로 교체!
    audio_path = './results/song.wav'
    # 임시 dummy 파일 생성 (테스트용)
    with open(audio_path, 'wb') as f: f.write(b'')
    return audio_path

def create_score(midi_path, accompaniment):
    # 실제 악보생성 코드(music21, MuseScore 등)로 교체!
    score_path = './results/song.pdf'
    # 임시 dummy 파일 생성 (테스트용)
    with open(score_path, 'wb') as f: f.write(b'')
    return score_path

# ======== 라우터들 ==========

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-lyrics', methods=['POST'])
def generate_lyrics():
    data = request.json
    topic = data.get('topic', '')
    lyrics = data.get('lyrics', '')
    if lyrics:
        result = lyrics
    else:
        result = generate_lyrics_with_gpt(topic)
    return jsonify({'lyrics': result})

@app.route('/generate-song', methods=['POST'])
def generate_song():
    data = request.json
    lyrics = data['lyrics']
    style = data.get('style')
    tempo = data.get('tempo')
    genre = data.get('genre')
    accompaniment = data.get('accompaniment')
    mood = data.get('mood')

    midi_path = generate_song_with_yue(
        lyrics=lyrics,
        style=style,
        tempo=tempo,
        genre=genre,
        accompaniment=accompaniment,
        mood=mood
    )
    audio_path = synthesize_vocal_audio(midi_path, lyrics)
    return jsonify({
        'midi_path': midi_path,
        'audio_path': audio_path
    })

@app.route('/generate-score', methods=['POST'])
def generate_score():
    data = request.json
    midi_path = data['midi_path']
    accompaniment = data.get('accompaniment', '')
    score_path = create_score(midi_path, accompaniment)
    return jsonify({'score_path': score_path})

@app.route('/download/<path:filename>')
def download(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename), as_attachment=True)

# ===========================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

