# main.py
import os
import requests
from dotenv import load_dotenv
from typing import TypedDict
from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()

# --- State ---
class EmailState(TypedDict):
    subject: str
    body: str
    category: str
    reason: str
    slack_message: str

# --- LangChain Chain ---
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

# --- 노드 ---
def analyze_node(state: EmailState) -> EmailState:
    result = chain.invoke({"subject": state["subject"], "body": state["body"]})
    return {**state, **result}

def slack_node(state: EmailState) -> EmailState:
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    requests.post(slack_url, json={"text": state["slack_message"]})
    return state

# --- 그래프 ---
graph = StateGraph(EmailState)
graph.add_node("analyze", analyze_node)
graph.add_node("slack", slack_node)
graph.add_edge(START, "analyze")
graph.add_edge("analyze", "slack")
graph.add_edge("slack", END)
pipeline = graph.compile()

# --- FastAPI ---
app = FastAPI()

class EmailRequest(BaseModel):
    subject: str
    body: str

@app.post("/analyze")
async def analyze(req: EmailRequest):
    result = pipeline.invoke({
        "subject": req.subject,
        "body": req.body,
        "category": "",
        "reason": "",
        "slack_message": "",
    })
    return result