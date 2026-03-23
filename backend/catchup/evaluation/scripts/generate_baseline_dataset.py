import json
import os
import asyncio
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List
from tqdm.asyncio import tqdm

current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from catchup.configs.config import settings

DATABASE_URL = settings.sqlalchemy_database_url
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
COLLECTION_NAME = settings.PGVECTOR_COLLECTION_NAME

# [수동 선별 데이터]
# 이 데이터는 Few-shot 예시로도 쓰이고, 최종 데이터셋에도 포함됨.
MANUAL_SEEDS = [
    # JIRA
    {
        "source": "jira",
        "doc_id": "jira:issue:CAT-129",
        "content": "팀원D이 프론트 라우팅 경로 구성 작업(CAT-129)을 진행하고 있다...",
        "q1": "CAT-129 프론트 라우팅 작업 담당자 누구야?",
        "q2": "권한별 페이지 구성이랑 폴더 구조 바꾸는 작업 진행 상황 좀 알려줘"
    },
    {
        "source": "jira",
        "doc_id": "jira:issue:CAT-167",
        "content": "팀원B이 Slack 사용자가 논의 중인 안건을 요약하거나...",
        "q1": "CAT-167 스레드 요약 기능 요건",
        "q2": "슬랙에서 봇 태그하면 대화 내용 요약해주는 기능 개발 다 됐나?"
    },
    {
        "source": "jira",
        "doc_id": "jira:issue:CAT-65",
        "content": "팀원B이 Slack Bot의 답변 내용 기획 작업(CAT-65)을 진행하고 있다...",
        "q1": "CAT-65 봇 답변 기획 내용",
        "q2": "예시고객사 PoC 관련해서 봇이 뭐라고 답변할지 정한 기획 문서 어딨어?"
    },
    # SLACK
    {
        "source": "slack",
        "doc_id": "slack:message:T09...:1769662802.815379",
        "content": "성훈이 좌측 질문 리스트가 채팅방에서 확인되지 않는 문제를 점검해달라고...",
        "q1": "좌측 질문 리스트 안 뜨는 버그",
        "q2": "성훈님이랑 채팅방 리스트 안 보인다고 얘기했던 스레드 찾아줘"
    },
    {
        "source": "slack",
        "doc_id": "slack:message:T09...:1764680535.168609",
        "content": "누군가 학생용 가입 신청을 두 번 했지만 아무런 반응이 없다고...",
        "q1": "Framer 학생용 플랜 가입 이슈",
        "q2": "프레이머 계정 트랜스퍼하고 QR 코드 만들기로 한 대화 내용"
    },
    # GITHUB
    {
        "source": "github",
        "doc_id": "github:pr:TeamCatchUp/CatchUp:28",
        "content": "gilbert09031이 GitHub, Jira, Slack 커넥터의 인증 관련 로직을...",
        "q1": "PR #28 리뷰 코멘트",
        "q2": "커넥터 인증 로직 분리하면서 들여쓰기 에러 났던 거 수정됐어?"
    },
    {
        "source": "github",
        "doc_id": "github:pr:TeamCatchUp/CatchUp:12",
        "content": "ba2slk가 벡터 DB 검색과 관련된 런타임 버그와 relevance score...",
        "q1": "PR #12 변경 사항",
        "q2": "벡터 DB 런타임 버그랑 순환 참조 해결한 코드 보여줘"
    }
]

# 프롬프트 구성
class GeneratedQueries(BaseModel):
    questions: List[str] = Field(description="2 distinct search queries (Keyword-based, Context-based)")
    is_valid: bool = Field(description="False if content is too short or noise")

llm = ChatOpenAI(model="gpt-4o", temperature=0.7, api_key=settings.OPENAI_API_KEY)
parser = JsonOutputParser(pydantic_object=GeneratedQueries)

# Few-shot 예시 템플릿
example_prompt = ChatPromptTemplate.from_messages([
    ("human", "[Source]: {source}\n[Document]: {content}\nGenerate queries."),
    ("ai", "{{\"questions\": [\"{q1}\", \"{q2}\"], \"is_valid\": true}}")
])

# Few-shot Prompt 조립
few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=example_prompt,
    examples=MANUAL_SEEDS
)

final_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are a QA Dataset Generator for 'CatchUp'.
    Your goal is to mimic the style of the provided examples perfectly.
    
    [Style Guide]
    1. **Korean Native Tone:** Use natural Korean developer speech (e.g., "~했어?", "~확인 좀").
    2. **Ambiguity:** Do NOT copy the document content exactly. Assume the user has 'vague memory'.
    3. **Two Types:**
       - Query 1: Keyword/ID focused (but natural).
       - Query 2: Context/Intent focused (No IDs, purely descriptive).
    
    [Strict Rules]
    - If the document is a system log (joined, left) or too short (<50 chars), set `is_valid` to `false`.
    """),
    few_shot_prompt,
    ("human", "[Source]: {source}\n[Document]: {content}\n[Metadata]: {metadata}\n\nGenerate queries based on the style above.")
])

# --- 데이터 Fetching ---
def fetch_new_samples(session, coll_uuid, limit_per_source=32):
    """Seed에 없는 새로운 데이터만 Fetch"""
    seed_ids = [item['doc_id'] for item in MANUAL_SEEDS]
    
    all_new_data = []
    sources = ["jira", "slack", "github"]
    
    for src in sources:
        print(f"Fetching new samples for {src.upper()}...")
        sql = text(f"""
            SELECT document, cmetadata, id
            FROM langchain_pg_embedding
            WHERE collection_id = :coll_uuid
              AND cmetadata ->> 'source' = :src
              AND id != ALL(:seed_ids)
              AND length(document) > 100 -- 너무 짧은 건 DB단에서 거름
            ORDER BY RANDOM()
            LIMIT :limit
        """)
        
        rows = session.execute(sql, {
            "coll_uuid": coll_uuid, 
            "src": src, 
            "seed_ids": seed_ids, 
            "limit": limit_per_source
        }).fetchall()
        
        for r in rows:
            all_new_data.append({"page_content": r[0], "metadata": r[1], "id": r[2], "source": src})
            
    return all_new_data

# --- 메인 로직 ---
async def process_item(chain, item):
    try:
        # 메타데이터 간소화
        meta_subset = {k: v for k, v in item["metadata"].items() if k in ["title", "summary", "status", "author"]}
        
        resp = await chain.ainvoke({
            "source": item["source"],
            "content": item["page_content"],
            "metadata": json.dumps(meta_subset, ensure_ascii=False)
        })
        
        if not resp["is_valid"]:
            return []
            
        return [{
            "question": q,
            "ground_truth_doc_id": item["id"],
            "source": item["source"],
            "type": "generated"
        } for q in resp["questions"]]
        
    except Exception as e:
        # print(f"Error: {e}")
        return []

async def main():
    # 시드 데이터 변환 (Manual Seeds -> Final Format)
    final_dataset = []
    print(f"Adding {len(MANUAL_SEEDS)} Manual Seeds to dataset...")
    for seed in MANUAL_SEEDS:
        final_dataset.append({"question": seed["q1"], "ground_truth_doc_id": seed["doc_id"], "source": seed["source"], "type": "manual"})
        final_dataset.append({"question": seed["q2"], "ground_truth_doc_id": seed["doc_id"], "source": seed["source"], "type": "manual"})

    # DB에서 새로운 데이터 Fetch
    with SessionLocal() as db:
        coll_query = text("SELECT uuid FROM langchain_pg_collection WHERE name = :name")
        coll_result = db.execute(coll_query, {"name": COLLECTION_NAME}).fetchone()
        coll_uuid = coll_result[0]
        
        # 소스당 32개씩 Fetch (총 ~96개)
        new_samples = fetch_new_samples(db, coll_uuid, limit_per_source=32)
        print(f"Fetched {len(new_samples)} new documents for generation.")

    # LLM 생성 (Async)
    chain = final_prompt | llm | parser
    tasks = [process_item(chain, item) for item in new_samples]
    
    print("Generating questions using Few-shot prompting...")
    results = await tqdm.gather(*tasks)
    
    for res in results:
        final_dataset.extend(res)

    output_file = "final_golden_dataset.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_dataset, f, ensure_ascii=False, indent=2)
        
    print(f"\n[DONE] Final Dataset Saved: {output_file}")
    print(f"Total Questions: {len(final_dataset)} (Manual: {len(MANUAL_SEEDS)*2}, Generated: {len(final_dataset) - len(MANUAL_SEEDS)*2})")

if __name__ == "__main__":
    asyncio.run(main())
