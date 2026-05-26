from catchup.agents.tools.internal.search import CatchUpSearchTool
from catchup.agents.tools.registry import ToolRegistry


def init_agent_tool_registry() -> None:
    """Execution Agent가 사용할 툴을 ToolRegistry에 등록한다.

    GlobalContext 의존 툴(CatchUpSearchTool)은 schema 조회용으로 등록한다.
    실제 실행 시에는 build_execution_graph()에서 GlobalContext를 주입한 인스턴스를 사용한다.
    """
    ToolRegistry.register(CatchUpSearchTool())
