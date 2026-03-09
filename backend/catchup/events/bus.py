from collections import defaultdict
from typing import Callable

from catchup.events.context import current_bg_tasks
from catchup.observability.logging.context import get_request_context


class EventBus:
    def __init__(self):
        self._listeners: dict[str, list[Callable]] = defaultdict(list)
        
    def subscribe(
        self,
        event_name: str,
        func: Callable
    ):
        self._listeners[event_name].append(func)
        
    def emit(
        self,
        event_name: str,
        **payload
    ):
        bg_tasks = current_bg_tasks.get()
        
        context = get_request_context()        
        if "actor" in context and "actor" not in payload:
            payload["actor"] = context["actor"]
        
        if "trace-id" in context and "trace_id" not in payload:
            payload["trace_id"] = context["trace_id"]

        
        for func in self._listeners[event_name]:
            if bg_tasks:
                bg_tasks.add_task(func, **payload)
            else:
                func(**payload)
            
bus = EventBus()
