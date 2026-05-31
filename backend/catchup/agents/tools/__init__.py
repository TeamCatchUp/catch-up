from catchup.agents.tools.external.channel_talk import ChannelTalkTool
from catchup.agents.tools.internal.search import CatchUpKnowledgeBaseTool
from catchup.agents.tools.registry import ToolRegistry


def init_agent_tool_registry() -> None:
    """Execution Agent가 사용할 툴을 ToolRegistry에 등록한다.

    이 단계는 사용 가능한 tool catalog 등록만 수행한다.
    실제 실행 컨텍스트는 Agent Spec의 tools 목록에 있는 tool에만 바인딩된다.
    """
    ToolRegistry.register(CatchUpKnowledgeBaseTool())
    ToolRegistry.register(ChannelTalkTool())
