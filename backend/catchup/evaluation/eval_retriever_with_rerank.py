import json
import time
import sys
import asyncio
from pathlib import Path
from tqdm.asyncio import tqdm

current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from langchain_cohere import CohereEmbeddings

from catchup.configs.config import settings
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.components.reranker.service import RerankService 

DATABASE_URL = settings.sqlalchemy_database_url
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

embeddings = CohereEmbeddings(
    model=settings.COHERE_EMBEDDING_MODEL,
    cohere_api_key=settings.COHERE_API_KEY,
)

vector_service = PGVectorService(
    postgresql_engine=engine,
    embeddings=embeddings,
    collection_name=settings.PGVECTOR_COLLECTION_NAME,
    session_factory=SessionLocal
)

rerank_service = RerankService()

async def evaluate_pipeline(dataset_path: str, initial_k: int = 50, final_k: int = 5):
    with open(dataset_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
    
    print(f"Starting Evaluation (Retrieve@{initial_k} -> Rerank@{final_k})...")
    
    hits = 0
    mrr_sum = 0.0
    start_time = time.time()
    
    # 비동기 처리
    for case in tqdm(test_cases):
        query = case['question']
        ground_truth_id = case['ground_truth_doc_id']
        
        try:
            # Hybrid Search
            initial_docs = await vector_service.hybrid_search(query, k=initial_k)
            
            if not initial_docs:
                continue

            # Reranking
            reranked_docs = await rerank_service.rerank(
                query=query, 
                documents=initial_docs, 
                top_n=final_k
            )
            
            # 정답 확인
            found_rank = -1
            for rank, doc in enumerate(reranked_docs):
                retrieved_id = doc.id or doc.metadata.get('id')
                
                if retrieved_id == ground_truth_id:
                    found_rank = rank + 1
                    break
            
            if found_rank > 0:
                hits += 1
                mrr_sum += 1.0 / found_rank
            else:
                print(f"[MISS] {query} (Target: {ground_truth_id})")
                pass
                
        except Exception as e:
            print(f"Error processing query '{query}': {e}")

    # 결과 출력
    total = len(test_cases)
    avg_time = (time.time() - start_time) / total
    
    print("\n" + "="*45)
    print(f"Final RAG Performance (Ret@{initial_k} -> Top-{final_k})")
    print("="*45)
    print(f"Hit Rate : {hits/total:.2%} ({hits}/{total})")
    print(f"MRR      : {mrr_sum/total:.4f}")
    print(f"Avg Time : {avg_time:.4f}s")
    print("="*45)

if __name__ == "__main__":
    asyncio.run(evaluate_pipeline("catchup_golden_dataset.json", initial_k=100, final_k=5))