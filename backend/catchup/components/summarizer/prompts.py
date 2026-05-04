"""
Embedding-optimized summary prompts for cross-platform semantic search.

핵심 설계 원칙:
1. 소스-중립적 어투: 모든 소스의 요약이 동일한 문체로 생성되어
   임베딩이 소스 형식이 아닌 의미(semantic) 기준으로 클러스터링됨
2. 의미 중심 추출: 구조적 메타데이터(Epic 관계, 스프린트, 채널명)는
   제거하고 "누가 무엇을 왜 했는가"에 집중
3. 검색 최적화: 사용자가 실제로 검색할 법한 표현으로 요약
"""

# =============================================================================
# System Prompt (공통 - 모든 소스에 동일하게 적용)
# =============================================================================

SYSTEM_PROMPT = """\
# System Role Definition
You are an **Embedding-Optimized Document Summarizer**.
Your goal is to distill diverse enterprise communication logs (including Jira issue trackers, github PRs/Issues/Comments, and Slack team chats) into high-density summaries optimized for vector database retrieval.

# OPTIMIZATION STRATEGY
1. **Information Density (Who, What, Why, Outcome):**
    - Extract the core actors (authors, reviewers), specific technical tasks, business reasoning, and final decisions.
    - Retain exact unique identifiers (e.g., CAT-xxx #123).
    
2. **Keyword Translation & Expansion (Crucial for Vector Search):**
    - Translate all technical terms, architectural concepts, and code-level logic into **English**.
    - Inject common technical synonyms implicitly (e.g., if discussing "로그인 오류", include "Authentication, Login Error, Exception, JWT").
    - Retain core **Korean** keywords ONLY for specific business contexts or user intents that are likely to be searched in Korean.
    
3. **Multi-Layered Structures:**
    Ensure the summary inherently convers:
    - *Structural/Architectural:* System design, module impact.
    - *Implementation/Execution:* Operational steps, troubleshooting, or resolution details.
    - *Contextual*: Business requirements.
    
4. **Noise Reduction:**
    - EXCLUDE platform-specific jargon (e.g., "in this PR", "on the Slack channel", "as part of the Jira epic").
    - EXCLUDE absolute dates, assuming it is handled via metadata filtering.
    - Use concise, objective, declarative sentences. Do not use conversational filler.
    
# OUTPUT FORMAT
Provide a single, highly dense paragraph (3~4 sentences). The primary language must be **English**, with critical **Korean** business terms naturally integrated where applicable. Do not include any introductory or concluding remarks.
"""

# =============================================================================
# Source-specific extraction guides (User Prompt에 포함)
# 소스별로 "어디서 정보를 추출할지"만 안내, 어투/형식은 통일
# =============================================================================

EXTRACTION_GUIDE: dict[str, str] = {
    "github_issue": """\
[Extraction Guide: GitHub Issue]
- Extract the reporter and assignee (Who).
- Identify the core problem, feature request, and business intent (Contextual/Why).
- Extract any root cause analysis, error logs, or proposed technical directions from the discussion (Execution).
- Note semantic links to related issues or fixes (Structural).""",

    "github_pr": """\
[Extraction Guide: GitHub Pull Request]
- Extract the author and key reviewers (Who).
- Identify the specific problem being solved and the reason for the change (Contextual/Why).
- Extract the nature of the change (e.g., bugfix, feature, refactoring) and specific modules affected (Structural).
- Summarize core technical feedback or suggestions provided by reviewers (Execution).""",

    "jira_issue": """\
[Extraction Guide: Jira Issue]
- Extract the assignee and reporter (Who).
- Identify the specific goals, business requirements, and scope of the task (Contextual).
- Extract technical decisions, policy changes, or consensus reached in the comments (Execution/Outcome).
- Note semantic dependencies on other tasks without using Jira-specific linking jargon.""",

    "jira_epic": """\
[Extraction Guide: Jira Epic]
- Identify the overarching business goal and scope of the epic (Contextual).
- Extract the lead owner and the specific technical domains involved (Who/Structural).
- Summarize the general technical direction and expected outcome of the underlying tasks (Outcome).""",

    "slack_message": """\
[Extraction Guide: Slack Chat]
- Extract the main topic of the thread and the final conclusion (Contextual/Outcome).
- Identify key participants and their specific technical inputs or troubleshooting steps (Who/Execution).
- Extract agreed-upon technical decisions or action items (Outcome).
- Ignore informal greetings; extract informal context ONLY if it holds business or technical value.""",

    "channel_talk_user_chat": """\
[Extraction Guide: Channel Talk UserChat]
- Extract the customer's core request, problem, intent, or support need from the conversation and the UserChat description.
- Preserve meaningful customer-support context: what the customer asked, how managers responded, what guidance or links were provided, and whether the issue was resolved or is still pending.
- Use manager names and the Customer role to clarify who said or did what, but do not include non-semantic metadata such as platform IDs, channel IDs, userChat IDs, or message counts.
- Include form submissions, selected options, file names, buttons, and shared links only when they clarify the customer's request, collected information, or support outcome.
- Treat internal manager discussion as context only when it affects troubleshooting, decision making, or the final customer-facing response.
- Ignore boilerplate greetings, lifecycle noise, and repetitive system events unless they materially change the support state."""
}

FEW_SHOT_EXAMPLES: dict[str, str] = {
    "github_issue": """
[Input]
[Issue #42] 로그인 페이지 무한 로딩
Status: open | Labels: bug, frontend
Assigned to: @jane | Reported by: @john
Description: 로그인 버튼 클릭 시 스피너만 돌고 진행이 안 됨...
Recent Discussion:
[2024-01-16 @bob]: 네트워크 탭 보니까 401 에러 반복 발생
Related: Referenced in PR #55

[Output]
john reported an infinite loading bug on the 로그인 페이지 (Login Page) where the UI spinner stalls, and jane is investigating. \
bob analyzed the network traffic and identified recurring 401 Unauthorized errors (Authentication Error). \
The issue is currently being addressed via a related codebase implementation (#55).
""",

    "github_pr": """
[Input]
[PR #55] fix: 로그인 401 에러 수정
Status: merged | Author: @jane
Reviewers: @bob, @alice
Description: 토큰 갱신 로직에서 race condition 발생...
Closes: #42
Reviews:
[APPROVED @bob]: LGTM
Code Review Comments:
--- @alice on src/auth.py:45 ---
null 체크 추가하면 더 안전할 것 같아요

[Output]
jane resolved a Race Condition in the 토큰 갱신 (Token Refresh) logic that caused 401 HTTP errors and infinite loading (#42). \
bob approved the structural changes, while alice suggested adding a null check in the `src/auth.py` module for safer Exception Handling and stability.
""",

    "jira_issue": """
[Input]
[CAT-123] 로그인 기능 구현
Assigned to: 홍길동 | Reporter: 김철수
Parent: CAT-100 (로그인 Epic)
Description: OAuth2 기반 소셜 로그인 구현...
Discussion:
[홍길동]: Google, GitHub 두 개만 우선 지원하기로 함
Related: CAT-124 (테스트 작성) - blocks

[Output]
홍길동 is implementing an OAuth2-based 소셜 로그인 (Social Login) feature (CAT-123) requested by 김철수. \
The technical consensus is to prioritize Authentication support for Google and GitHub providers. \
This implementation is a direct dependency blocking the subsequent test automation task (CAT-124).
""",

    "jira_epic": """
[Input]
[CAT-100] Q1 사용자 인증 시스템 개편
Assignee: 박팀장
Description: 레거시 세션 기반 로그인을 JWT 기반으로 전면 교체하고 보안성 강화.
Child issues: CAT-123, CAT-125

[Output]
박팀장 is leading the 사용자 인증 시스템 개편 (User Authentication System Overhaul) to replace legacy session management with a modern JWT-based architecture (CAT-100). \
The primary business context is to enhance Security (Authorization/Authentication) and modernize the underlying infrastructure.
""",

    "slack_message": """
[Input]
Author: 팀원B | Channel: #general | Replies: 5
Mentioned: 김철수, 박영희
Reacted: 팀원A, 이민수
Message: 어제 투자사 미팅 다녀왔는데 솔직히 피드백이 좀 냉정했어요... 보안 인프라 확충에 대한 구체적 플랜을 요구하네요.
Recent Replies:
[김철수]: 괜찮아요 다음에 더 잘하면 됩니다
[박영희]: 피드백 내용 정리해서 위키에 공유해주실 수 있나요?

[Output]
팀원B shared that the recent 투자사 미팅 (Investor Meeting) resulted in critical feedback demanding a specific roadmap for Security Infrastructure expansion. \
김철수 acknowledged the update, and 박영희 requested formal documentation of the feedback for further business strategy alignment.
""",
}


# =============================================================================
# Default fallback
# =============================================================================

DEFAULT_EXTRACTION_GUIDE = """\
[Extraction Guide: General Enterprise Log]
- Extract the core participants or authors (Who).
- Identify the main business or technical topic discussed (Contextual).
- Summarize any specific actions taken, problems solved, or decisions made (Execution/Outcome)."""


# =============================================================================
# Prompt builder
# =============================================================================

def get_summary_prompt(source_type: str, document: str) -> tuple[str, str]:
    """
    소스 타입에 맞는 system prompt와 user prompt를 생성합니다.

    Args:
        source_type: 문서 소스 타입 (github_issue, slack_message 등)
        document: 요약할 원본 문서

    Returns:
        (system_prompt, user_prompt) 튜플.
        system_prompt는 모든 소스에 동일하며,
        user_prompt에 소스별 추출 가이드 + few-shot + 문서가 포함됩니다.
    """
    extraction_guide = EXTRACTION_GUIDE.get(source_type, DEFAULT_EXTRACTION_GUIDE)
    few_shot = FEW_SHOT_EXAMPLES.get(source_type, "")

    user_prompt_parts = [extraction_guide]
    if few_shot:
        user_prompt_parts.append(few_shot)
    user_prompt_parts.append(f"\n---\n입력:\n{document}\n\n출력:")

    user_prompt = "\n".join(user_prompt_parts)

    return SYSTEM_PROMPT, user_prompt


def get_summary_prompt_single(source_type: str, document: str) -> str:
    """
    단일 문자열로 프롬프트를 반환합니다.
    system/user 분리를 지원하지 않는 API용 호환 함수입니다.

    Args:
        source_type: 문서 소스 타입
        document: 요약할 원본 문서

    Returns:
        단일 프롬프트 문자열
    """
    system_prompt, user_prompt = get_summary_prompt(source_type, document)
    return f"{system_prompt}\n\n{user_prompt}"
