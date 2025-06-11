# colab_server.py
import os
import subprocess
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyngrok import ngrok

app = Flask(__name__)
CORS(app)

def yue_generate(lyrics, genre, output_dir="./output"):
    # 1) 입력 임시 저장
    with open("lyrics.txt", "w", encoding="utf-8") as f:
        f.write(lyrics)
    with open("genre.txt", "w", encoding="utf-8") as f:
        f.write(genre)
    # 2) yue_infer.py 실행
    cmd = [
        "python", "yue_infer.py",
        "--lyrics_txt", "lyrics.txt",
        "--genre_txt", "genre.txt",
        "--output_dir", output_dir
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout, proc.stderr)

    # 3) 믹스된 mp3 경로 찾기
    mp3_dir = os.path.join(output_dir, "vocoder", "mix")
    for fn in os.listdir(mp3_dir):
        if fn.endswith(".mp3"):
            return os.path.join(mp3_dir, fn)
    return None

@app.route('/generate', methods=['POST'])
def generate():
    lyrics = request.form.get('lyrics', '')
    genre  = request.form.get('genre', 'pop')
    if not lyrics:
        return jsonify({'error': '가사 미입력'}), 400

    # query param 'file'로 mp3/pdf 선택
    file_type = request.args.get('file', 'mp3')
    mp3_path = yue_generate(lyrics, genre)

    if file_type == 'pdf':
        pdf_path = os.path.join("output", "score.pdf")  # yue_infer.py에서 PDF 생성 경로에 맞춰 조정
        return send_file(pdf_path, as_attachment=True, download_name="score.pdf")
    elif mp3_path:
        return send_file(mp3_path, as_attachment=True, download_name="song.mp3")
    else:
        return jsonify({'error': 'MP3 파일 생성 실패'}), 500

if __name__ == '__main__':
    # ngrok 터널 열기
    public_url = ngrok.connect(5000)
    print(f"▶ ngrok URL: {public_url}")
    # Flask 실행
    app.run(host='0.0.0.0', port=5000)
