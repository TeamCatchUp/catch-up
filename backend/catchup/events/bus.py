import asyncio
import inspect
from collections import defaultdict
from typing import Callable

from catchup.events.context import current_bg_tasks


class EventBus:
    def __init__(self):
        """
        리스너 목록
        """
        self._listeners: dict[str, list[Callable]] = defaultdict(list)
        self._retained_tasks = set()  # GC 방지 용도
        
    def subscribe(
        self,
        topic: str,
        func: Callable
    ):
        """
        특정 topic에 리스너를 등록한다.
        """
        self._listeners[topic].append(func)
        
    def emit(
        self,
        topic: str,
        immediate: bool = False,
        **payload
    ):
        """
        특정 topic으로 이벤트를 발행한다.
        """
        bg_tasks = current_bg_tasks.get()
        for func in self._listeners[topic]:
            
            # BackgroundTasks 지연 실행
            if not immediate and bg_tasks:
                bg_tasks.add_task(func, **payload)
                continue
            
            # 즉시 실행 (immediate=True 또는 bg_tasks가 없는 경우)
            try:
                # 현재 코드가 실행 중인 스레드의 이벤트 루프 획득
                loop = asyncio.get_running_loop()
                
                # case) async def
                if inspect.iscoroutinefunction(func):
                    task = loop.create_task(func(**payload))
                
                # case) def (sync)
                else:                    
                    task = asyncio.create_task(
                        asyncio.to_thread(func, **payload)
                    )
                
                # GC 방지
                self._retained_tasks.add(task)
                task.add_done_callback(self._retained_tasks.discard)

            except RuntimeError:
                # 순수 동기 스레드 환경인 경우
                # run_in_threadpool() 처럼 별도의 스레드 풀에서 동작하는 경우
                if inspect.iscoroutinefunction(func):
                    asyncio.run(func(**payload))
                else:
                    func(**payload)


# 전역 event bus 인스턴스
bus = EventBus()
