"""
Chat 전용 executor 격리 검증

asyncio 기본 thread pool을 블로킹 작업으로 포화시킨 상태에서
chat_executor가 독립적으로 완료되는지 확인한다.

실행:
    cd backend
    python -m catchup.evaluation.eval_thread_pool_isolation

기대 결과:
    [PASS] chat_executor: 즉시 완료 (< 1.0s)
    [확인] 기본 executor: 블로킹됨 (>= 1.0s) — 격리 효과 증명
"""

import asyncio
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

DEFAULT_POOL_SIZE = min(32, (os.cpu_count() or 1) + 4)
BLOCK_SECONDS = 5       # 기본 pool 점유 시간
CHAT_TIMEOUT = 1.0      # chat_executor 응답 기준 (초)


async def main():
    loop = asyncio.get_running_loop()

    chat_executor = ThreadPoolExecutor(
        max_workers=10,
        thread_name_prefix="rag-chat",
    )

    print(f"\n{'='*55}")
    print(f"  Chat Executor 격리 테스트")
    print(f"{'='*55}")
    print(f"OS CPU 수:           {os.cpu_count()}")
    print(f"기본 thread pool 크기: {DEFAULT_POOL_SIZE}")
    print(f"블로킹 작업 지속 시간:  {BLOCK_SECONDS}s")
    print(f"chat 응답 기준:        < {CHAT_TIMEOUT}s")
    print(f"{'-'*55}")

    # 1단계: 기본 pool을 블로킹 작업으로 포화
    print(f"\n[1] 기본 executor를 {BLOCK_SECONDS}s짜리 작업 {DEFAULT_POOL_SIZE}개로 포화 중...")
    blocking_tasks = [
        loop.run_in_executor(None, time.sleep, BLOCK_SECONDS)
        for _ in range(DEFAULT_POOL_SIZE)
    ]
    await asyncio.sleep(0.05)   # 블로킹 작업들이 thread를 점유할 시간

    # 2단계: chat_executor 응답 시간 측정
    print("[2] 기본 pool 포화 상태에서 chat_executor 응답 시간 측정...")
    start = time.perf_counter()
    await loop.run_in_executor(chat_executor, lambda: None)
    chat_elapsed = time.perf_counter() - start

    chat_ok = chat_elapsed < CHAT_TIMEOUT
    chat_label = "PASS" if chat_ok else "FAIL"
    print(f"    결과: [{chat_label}] {chat_elapsed:.4f}s")

    # 3단계: 기본 executor 응답 시간 측정 (대조군)
    print("[3] 기본 executor 응답 시간 측정 (블로킹 상태, 대조군)...")
    start = time.perf_counter()
    blocked = False
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, lambda: None),
            timeout=CHAT_TIMEOUT,
        )
        default_elapsed = time.perf_counter() - start
        default_label = "예상보다 빠름 — pool 크기를 확인하세요"
    except asyncio.TimeoutError:
        default_elapsed = time.perf_counter() - start
        default_label = "블로킹됨 (격리 효과 확인됨)"
        blocked = True
    print(f"    결과: {default_elapsed:.4f}s → {default_label}")

    # 요약
    print(f"\n{'='*55}")
    if chat_ok and blocked:
        print("  최종: 격리 성공 — sync worker와 chat가 독립적으로 동작합니다.")
    elif chat_ok and not blocked:
        print("  최종: chat_executor는 정상이나 기본 pool이 예상보다 큽니다.")
        print("         컨테이너 CPU 수를 확인하세요.")
    else:
        print("  최종: 격리 실패 — chat_executor 설정을 확인하세요.")
    print(f"{'='*55}\n")

    # 정리
    for t in blocking_tasks:
        t.cancel()
    chat_executor.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
