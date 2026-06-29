# agent-email-llm-slack

> AI Agent with Gemini & Slack — n8n · LangChain · LangGraph

**Date:** 2026.06

## Why

이메일이 들어오면 AI가 긴급도를 판단하고, 자동으로 Slack에 메시지를 보내는 파이프라인이다.
같은 파이프라인을 세 가지 방식으로 구현해서 각 도구가 "노드"를 어떻게 다루는지 직접 비교한다.

**핵심 아키텍처:** Orchestration을 Model 바깥으로 꺼내는 것.
Model(Gemini)은 판단만 하고, 흐름 관리는 외부 오케스트레이터가 담당한다.

---

## Architecture

동일한 3-노드 파이프라인을 n8n / LangChain / LangGraph 세 가지로 구현한다.

```
[노드 1] 이메일 수신 (Webhook / FastAPI)
      ↓
[노드 2] Gemini 판단 → urgent / normal / spam
      ↓
[노드 3] Slack 발송
```

### 구현별 노드 대응

| 노드 | n8n | LangChain | LangGraph |
|---|---|---|---|
| 노드 1 (수신) | n8n Webhook 노드 | FastAPI `@app.post` | FastAPI `@app.post` |
| 노드 2 (판단) | HTTP Request → Flask → Gemini | `chain = prompt \| llm \| parser` | `analyze_node` |
| 노드 3 (발송) | n8n HTTP Request 노드 | `requests.post()` | `slack_node` |
| 노드 연결 | 캔버스에서 선으로 | 함수 안에서 순서대로 | `add_edge`로 명시적 선언 |
| 데이터 전달 | n8n 자동 | 변수로 직접 넘김 | State 공유 |

### LangGraph 흐름

```
START → analyze_node → slack_node → END
         (Gemini 판단)   (Slack 발송)
```

---

## Key Design Decisions

**왜 LangChain과 LangGraph를 분리했나**

LangChain의 `chain = prompt | llm | parser`는 노드 2(Model 호출) 하나만 대체한다.
LangGraph의 `add_node` / `add_edge`는 n8n 캔버스의 "노드 연결" 개념 자체를 코드로 표현한다.
같은 파이프라인이지만 추상화 레벨이 다르다 — 이 차이를 직접 체험하기 위해 두 구현을 분리했다.

**왜 Flask → FastAPI로 전환했나 (n8n → Python 구현)**

n8n은 JavaScript만 실행할 수 있어서, Python Gemini 호출을 위해 Flask 서버를 별도로 띄웠다.
Python 코드 구현에서는 FastAPI + uvicorn으로 직접 처리한다.

**Gemini 모델 폴백 체인**

무료 API 제한(429/503) 대응:
```python
MODELS = [
    "gemini-2.5-flash-lite",   # 최우선 — 무료 토큰 가장 많음
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
]
```

---

## Tech Stack

| 항목 | 사용 기술 |
|---|---|
| LLM | Gemini API (무료 티어) |
| Orchestration | n8n, LangChain, LangGraph |
| Server | Flask (n8n 연동), FastAPI + uvicorn (Python 구현) |
| Notification | Slack Incoming Webhook |
| Language | Python 3.x |
| Cost | $0 |

---

## Repository Structure

```
email-ai-slack-pipeline/
├── 1_gmail_n8n_slack/        # n8n + Flask
│   ├── server.py               # Flask 서버 (Gemini 호출)
│   └── My workflow.json      # n8n workflow
│
├── 2_langchain_slack/        # LangChain + FastAPI
│   ├── main.py                 # FastAPI + LangChain Chain
│
└── 3_langgraph_slack/        # LangGraph + FastAPI
    ├── main.py                 # FastAPI + LangGraph 파이프라인
```

---

## How to Run

### 공통 환경 설정

```bash
# .env 파일 생성
GEMINI_API_KEY=발급받은_Gemini_API_키
SLACK_WEBHOOK_URL=Slack_Incoming_Webhook_URL
```

### n8n + Flask

```bash
# 1. Flask 서버 실행
cd 1_gmail_n8n_slack
pip install flask python-dotenv google-generativeai
python3 server.py

# 2. n8n 실행 (Docker)
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  -e N8N_ENABLE_EXECUTE_COMMAND=true \
  -e NODES_EXCLUDE='[]' \
  n8nio/n8n

# 3. 테스트
curl -X POST http://localhost:5678/webhook-test/email-trigger \
  -H "Content-Type: application/json" \
  -d '{"subject":"결제 오류 긴급","body":"고객 결제가 실패하고 있습니다."}'
```

### LangChain + FastAPI

```bash
cd 2_langchain_slack
pip install langchain langchain-google-genai fastapi uvicorn python-dotenv requests

# Chain 단독 테스트
python3 analyze.py

# 서버 실행
uvicorn main:app --port 3000 --reload

# 테스트
curl -X POST http://localhost:3000/analyze \
  -H "Content-Type: application/json" \
  -d '{"subject":"결제 오류 긴급","body":"고객 결제가 실패하고 있습니다."}'
```

### LangGraph + FastAPI

```bash
cd 3_langgraph_slack
pip install langchain langchain-google-genai langgraph fastapi uvicorn python-dotenv requests

# LangGraph 단독 테스트
python3 analyze.py

# 서버 실행
uvicorn main:app --port 3000 --reload

# 테스트
curl -X POST http://localhost:3000/analyze \
  -H "Content-Type: application/json" \
  -d '{"subject":"결제 오류 긴급","body":"고객 결제가 실패하고 있습니다."}'
```

---

## Known Issues & Lessons

**n8n Execute Command 노드 비활성화 문제**

n8n 2.0+ 에서 보안상 기본 비활성화. Docker 실행 시 환경변수로 활성화 필요.
단, 컨테이너 내부에 Python이 없어서 `python3`를 직접 실행할 수 없음 → Flask 서버 방식으로 전환.

```


<img width="864" height="215" alt="n8n_agentic-loop-search" src="https://github.com/user-attachments/assets/f89151d9-8419-42ce-aaa4-b531099a5c07" />

