import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { OpenAI } from 'openai';
import textToSpeech from '@google-cloud/text-to-speech';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// OpenAI 설정
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

// Google TTS 클라이언트 설정
const ttsClient = new textToSpeech.TextToSpeechClient({
  keyFilename: './credentials.json'  // 또는 GOOGLE_APPLICATION_CREDENTIALS 환경변수 사용
});

// ✅ [POST] /generate-lyrics
app.post('/generate-lyrics', async (req, res) => {
  const userInput = req.body.prompt;

  try {
    const response = await openai.chat.completions.create({
      model: "gpt-4o",
      messages: [
        {
          role: "system",
          content: "당신은 감성적인 한국어 작사가입니다. 주어진 주제에 따라 감정을 담은 2절짜리 노래 가사를 만들어주세요."
        },
        {
          role: "user",
          content: `"${userInput}" 주제로 [Verse], [Chorus] 형식을 포함해 가사를 한국어로 써줘`
        }
      ],
      temperature: 0.9
    });

    const lyrics = response.choices[0].message.content;
    res.json({ lyrics });

  } catch (error) {
    console.error("OpenAI 호출 중 오류:", error);
    res.status(500).json({ error: "가사 생성 실패: " + error.message });
  }
});

// ✅ [POST] /tts
app.post('/tts', async (req, res) => {
  const { text } = req.body;

  const request = {
    input: { text },
    voice: { languageCode: 'ko-KR', name: 'ko-KR-Neural2-A' },
    audioConfig: { audioEncoding: 'MP3', speakingRate: 1.0, pitch: 0.0 }
  };

  try {
    const [response] = await ttsClient.synthesizeSpeech(request);
    res.set('Content-Type', 'audio/mpeg');
    res.send(response.audioContent);
  } catch (err) {
    console.error("TTS 생성 오류:", err);
    res.status(500).send("TTS 생성 실패");
  }
});

// 서버 시작
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`✅ 서버 실행 중: http://localhost:${PORT}`);
});
