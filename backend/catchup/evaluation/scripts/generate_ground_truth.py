import json
import asyncio
import sys
import os
import time
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from tqdm.asyncio import tqdm

current_dir = Path(__file__).resolve().parent
eval_dir = current_dir.parent
backend_root = eval_dir.parent.parent
sys.path.append(str(backend_root))

from catchup.configs.config import settings

DATABASE_URL = settings.sqlalchemy_database_url
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    api_key=settings.OPENAI_API_KEY
)

gt_prompt = ChatPromptTemplate.from_messages([
    ("system", """당신은 사내 협업 데이터에서 정답을 추출하는 전문 검수원입니다.
제공된 [문서 맥락]에서 [질문]에 대한 답을 찾아 '모범 답안'을 작성하세요.

[수칙]
1. 답변은 반드시 사실(Fact)에 기반하여 간결한 문장으로 작성하세요.
2. 질문에 언급된 대상(담당자, 상태, 날짜 등)이 문서에 있다면 반드시 포함하세요.
3. 문서 내용이 다소 부족하더라도, 질문과 관련된 단서가 있다면 최대한 활용하여 답변하세요.
4. "문서에 따르면" 같은 서술어는 생략하고 동료에게 답하듯 쓰세요 (~입니다, ~중입니다)."""),
    ("human", "[문서 맥락]:\n{context}\n\n[질문]:\n{question}\n\n모범 답안:")
])

async def fetch_context(session, doc_id):
    # ID 매칭 실패를 대비해 LIKE 검색 고려 가능 (여기서는 우선 Exact Match)
    sql = text("SELECT document, cmetadata FROM langchain_pg_embedding WHERE id = :d_id")
    row = session.execute(sql, {"d_id": doc_id}).fetchone()
    if not row:
        return ""
    metadata = row[1] if isinstance(row[1], dict) else json.loads(row[1])
    return metadata.get('contextual_content') or row[0]

async def process_case(item, session, semaphore):
    async with semaphore:
        doc_ids = item.get('ground_truth_doc_ids', [item.get('ground_truth_doc_id')])
        contexts = [await fetch_context(session, d_id) for d_id in doc_ids]
        full_context = "\n---\n".join([c for c in contexts if c]).strip()
        
        item['ground_truth_context'] = full_context

        if not full_context:
            item['ground_truth'] = "참조 문서가 DB에 존재하지 않습니다. ID를 확인하세요."
            return item

        # 429 방지를 위해 순차 실행에 가까운 지연 시간 부여
        await asyncio.sleep(1.5)
        
        try:
            response = await (gt_prompt | llm).ainvoke({
                "context": full_context[:12000],
                "question": item['question']
            })
            item['ground_truth'] = response.content.strip()
        except Exception as e:
            item['ground_truth'] = f"Error: {str(e)}"
        
        return item

async def main():
    input_path = eval_dir / "data" / "baseline_v1.json"
    output_path = eval_dir / "data" / "baseline_ragas_v1.json"

    with open(input_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # TPM 30k 환경에서는 동시성을 1로 제한하는 것이 가장 안전함 (순차 처리)
    semaphore = asyncio.Semaphore(1)
    
    print(f"Starting Ground Truth generation (Serial mode for low TPM)...")
    with SessionLocal() as db:
        tasks = [process_case(item, db, semaphore) for item in dataset]
        updated_dataset = await tqdm.gather(*tasks)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(updated_dataset, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
