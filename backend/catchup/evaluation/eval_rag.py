import asyncio
import json
import os
import random
import sys
from pathlib import Path

from tqdm.asyncio import tqdm

current_dir = Path(__file__).resolve().parent
backend_root = current_dir.parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from catchup.configs.config import settings

os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
os.environ["COHERE_API_KEY"] = settings.COHERE_API_KEY
os.environ["ENABLE_LANGFUSE"] = "False"  # 평가 시 tracing 비활성화

from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from ragas import EvaluationDataset
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics.collections import AnswerRelevancy
from ragas.metrics.collections import Faithfulness

from catchup.chat.factory import get_chat_service
from catchup.schemas.context import GlobalContext
from catchup.schemas.context import GlobalUserContext
from catchup.utils.redis import init_langgraph_checkpointer

SAMPLE_SIZE = 30
MAX_CONCURRENCY = 5

chat_service = get_chat_service()


def get_eval_context() -> GlobalContext:
    user_ctx = GlobalUserContext(
        id=1,
        name="Evaluator",
        email="user@example.com",
    )
    return GlobalContext(user=user_ctx)


async def get_rag_response(
    question: str,
    context: GlobalContext,
    semaphore: asyncio.Semaphore,
):
    async with semaphore:
        try:
            # rate limit 완화
            await asyncio.sleep(0.3)

            response = await chat_service.chat(
                query=question,
                global_context=context,
                session_id=f"eval_{os.urandom(4).hex()}",
            )

            return {
                "user_input": question,
                "response": response.answer,
                "retrieved_contexts": [doc.text for doc in response.sources],
            }

        except Exception as e:
            return {
                "user_input": question,
                "response": "Error",
                "retrieved_contexts": [],
                "error": str(e),
            }


async def run_evaluation():
    await init_langgraph_checkpointer()

    data_dir = current_dir / "data"
    input_path = data_dir / "baseline_ragas_final.json"
    if not input_path.exists():
        input_path = data_dir / "baseline_ragas_v1.json"

    with open(input_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if len(dataset) > SAMPLE_SIZE:
        print(f"Random sampling: {len(dataset)} -> {SAMPLE_SIZE}")
        dataset = random.sample(dataset, SAMPLE_SIZE)

    eval_context = get_eval_context()
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    print(f"Collecting RAG responses for {len(dataset)} cases...")
    tasks = [
        get_rag_response(item["question"], eval_context, semaphore)
        for item in dataset
    ]
    rag_results = await tqdm.gather(*tasks)

    # 4. 전처리 (RAGAS 입력 포맷)
    valid_results = []
    for i, res in enumerate(rag_results):
        if res["response"] == "Error":
            continue
        if not res["retrieved_contexts"]:
            continue

        res["reference"] = dataset[i]["ground_truth"]
        valid_results.append(res)

    if not valid_results:
        print("유효한 평가 데이터가 없습니다.")
        return

    print(f"Valid responses: {len(valid_results)} / {len(dataset)}")

    judge_llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )
    judge_embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
    )

    eval_llm = LangchainLLMWrapper(judge_llm)
    eval_embeddings = LangchainEmbeddingsWrapper(judge_embeddings)

    metrics = [
        Faithfulness(llm=eval_llm),
        AnswerRelevancy(
            llm=eval_llm,
            embeddings=eval_embeddings,
        ),
    ]

    eval_dataset = EvaluationDataset.from_list(valid_results)

    print("\nStarting RAGAS evaluation...")
    score = evaluate(
        dataset=eval_dataset,
        metrics=metrics,
        llm=eval_llm,
        embeddings=eval_embeddings,
    )

    df = score.to_pandas()
    output_csv = current_dir / "quick_eval_results.csv"
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 50)
    print(f"Evaluation Finished (N={len(valid_results)})")
    print("=" * 50)
    print(df[["faithfulness", "answer_relevancy"]].mean())
    print("=" * 50)
    print(f"Saved to: {output_csv}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
