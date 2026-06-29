from flask import Flask, request, jsonify
import json
import os
import urllib.request
import urllib.error
import time

app = Flask(__name__)

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
]

def call_gemini(subject, body):
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY가 .env 파일에 없습니다")

    prompt = f"""아래 이메일을 분석해서 반드시 JSON만 반환해줘. 다른 텍스트나 마크다운 코드블록 절대 쓰지 마.

이메일 제목: {subject}
이메일 본문: {body}

판단 기준:
- urgent: 서버 장애, 결제 오류, 보안 사고 등 즉시 대응 필요
- normal: 일반 업무 이메일
- spam: 광고, 스팸

반환 형식 (JSON만):
{{"category": "urgent" 또는 "normal" 또는 "spam", "reason": "판단 이유 한 문장", "slack_message": "Slack에 보낼 메시지 (이모지 포함)"}}"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }).encode("utf-8")

    last_error = None
    for model in MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:generateContent?key={api_key}"
        )
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=20) as res:
                    data = json.loads(res.read().decode("utf-8"))
                raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1]
                    raw = raw.rsplit("```", 1)[0].strip()
                return json.loads(raw)
            except urllib.error.HTTPError as e:
                last_error = e
                if e.code in (429, 503):
                    wait = 5 * (attempt + 1)
                    print(f"[{model}] HTTP {e.code} — {wait}초 후 재시도...")
                    time.sleep(wait)
                    continue
                break
            except Exception as e:
                last_error = e
                break

    raise RuntimeError(f"모든 모델 시도 실패: {last_error}")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    subject = data.get("subject", "")
    # body가 dict로 넘어오는 경우 대비
    body = data.get("body", "")
    if isinstance(body, dict):
        body = json.dumps(body, ensure_ascii=False)

    try:
        result = call_gemini(subject, body)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    load_env()
    print("서버 시작: http://localhost:3000")
    app.run(host="0.0.0.0", port=3000, debug=False)