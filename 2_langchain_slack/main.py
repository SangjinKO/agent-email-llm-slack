# main.py
import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()

app = FastAPI()

# --- LangChain Chain 구성 ---

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0,
)

prompt = ChatPromptTemplate.from_template("""
다음 이메일을 분석해서 JSON으로만 응답해. 다른 텍스트는 절대 포함하지 마.

제목: {subject}
본문: {body}

응답 형식:
{{
  "category": "urgent | normal | spam 중 하나",
  "reason": "판단 이유 한 문장",
  "slack_message": "Slack에 보낼 메시지 (이모지 포함)"
}}
""")

parser = JsonOutputParser()
chain = prompt | llm | parser

# --- FastAPI 엔드포인트 ---

class EmailRequest(BaseModel):
    subject: str
    body: str

@app.post("/analyze")
async def analyze(req: EmailRequest):
    # Step 1: LangChain Chain 실행 (Gemini 판단)
    result = chain.invoke({"subject": req.subject, "body": req.body})

    # Step 2: Slack 발송
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    requests.post(slack_url, json={"text": result["slack_message"]})

    return result