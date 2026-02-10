"""
Embedding-optimized summary prompts by source type.

각 소스 타입별로 검색에 최적화된 자연어 요약을 생성하기 위한 프롬프트.
"""

BASE_RULES = """
공통 규칙:
1. 형식적 구조(대괄호, 파이프, 키-값 쌍)를 모두 제거하고 자연어 문장으로 작성
2. 사람 이름은 반드시 포함 (작성자, 담당자, 리뷰어, 멘션된 사람 등)
3. 기술 키워드, 기능명, 이슈 번호(CAT-xxx)는 그대로 유지
4. 다른 이슈/PR/메시지와의 연결 관계가 있으면 자연어로 녹여서 포함
5. 감정적 톤이나 팀 내 맥락이 있으면 반영 (긍정적 반응, 우려, 긴급함 등)
6. 날짜, 상태값, 우선순위 등 순수 메타데이터는 제외
"""

GITHUB_ISSUE_PROMPT = f"""
당신은 GitHub Issue를 검색 가능한 요약으로 변환하는 전문가입니다.

{BASE_RULES}

추가 규칙:
- 이슈가 다루는 문제/요청의 핵심을 명확히 서술
- 논의(Discussion)에서 중요한 결론이나 의견 충돌이 있으면 포함
- 관련 PR이나 다른 이슈와의 연결 관계를 자연어로 포함
- 라벨이 문맥상 의미 있으면 자연어로 녹여서 포함 (예: "버그로 보고된", "프론트엔드 관련")

출력: 3-5문장의 자연어 요약

예시 입력:
[Issue #42] 로그인 페이지 무한 로딩
Status: open | Labels: bug, frontend
Assigned to: @jane | Reported by: @john
Description: 로그인 버튼 클릭 시 스피너만 돌고 진행이 안 됨...
Recent Discussion:
[2024-01-16 @bob]: 네트워크 탭 보니까 401 에러 반복 발생
Related: Referenced in PR #55

예시 출력:
john이 보고한 프론트엔드 버그로, 로그인 페이지에서 버튼 클릭 시 무한 로딩이 발생하는 문제다. jane이 담당하고 있으며, bob이 네트워크 탭에서 401 에러가 반복 발생하는 것을 확인했다. 이 문제는 PR #55에서 수정이 시도되고 있다.
"""

GITHUB_PR_PROMPT = f"""
당신은 GitHub PR을 검색 가능한 요약으로 변환하는 전문가입니다.

{BASE_RULES}

추가 규칙:
- 무엇을 왜 변경했는지 핵심을 서술
- 코드 리뷰에서 나온 주요 피드백이나 논의 포인트를 포함
- 리뷰어의 반응(승인, 변경 요청, 주요 코멘트)을 자연어로 포함
- 연결된 이슈(Closes)가 있으면 어떤 문제를 해결하는지 맥락 포함
- 변경 규모(파일 수, 라인 수)는 제외하되, 변경의 성격(리팩토링, 신규 기능, 버그 수정)은 포함

출력: 3-5문장의 자연어 요약

예시 입력:
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

예시 출력:
jane이 로그인 시 발생하던 401 에러를 수정한 PR로, 토큰 갱신 로직의 race condition이 원인이었다. Issue #42에서 보고된 로그인 무한 로딩 문제를 해결한다. bob은 승인했고, alice는 auth.py의 null 체크 추가를 제안했다.
"""

GITHUB_COMMIT_PROMPT = f"""
당신은 GitHub Commit을 검색 가능한 요약으로 변환하는 전문가입니다.

{BASE_RULES}

추가 규칙:
- 커밋의 목적과 변경 내용을 간결하게 서술
- 연결된 PR이 있으면 맥락 포함
- 변경된 파일 목록은 제외하되, 어떤 모듈/기능이 변경됐는지는 포함

출력: 1-3문장의 자연어 요약
"""

JIRA_ISSUE_PROMPT = f"""
당신은 Jira Issue를 검색 가능한 요약으로 변환하는 전문가입니다.

{BASE_RULES}

추가 규칙:
- 작업의 목적과 범위를 명확히 서술
- 상위 Epic이나 관련 이슈와의 관계를 자연어로 포함 (예: "사용자 인증 시스템 Epic의 하위 작업으로")
- Discussion에서 중요한 결정 사항이나 기술적 논의가 있으면 포함
- 컴포넌트/라벨이 기술적 맥락을 제공하면 자연어로 녹여서 포함
- 차단 관계(blocks/is blocked by)가 있으면 포함

출력: 3-5문장의 자연어 요약

예시 입력:
[CAT-123] 로그인 기능 구현
Assigned to: 홍길동 | Reporter: 김철수
Parent: CAT-100 (로그인 Epic)
Description: OAuth2 기반 소셜 로그인 구현...
Discussion:
[홍길동]: Google, GitHub 두 개만 우선 지원하기로 함
Related: CAT-124 (테스트 작성) - blocks

예시 출력:
홍길동이 담당하는 로그인 기능 구현 작업(CAT-123)으로, 사용자 인증 시스템 Epic(CAT-100)의 하위 작업이다. OAuth2 기반 소셜 로그인을 구현하며, 김철수가 요청했다. 홍길동이 Google과 GitHub 두 개 프로바이더를 우선 지원하기로 결정했으며, 테스트 작성 작업 CAT-124가 이 작업에 의존하고 있다.
"""

JIRA_EPIC_PROMPT = f"""
당신은 Jira Epic을 검색 가능한 요약으로 변환하는 전문가입니다.

{BASE_RULES}

추가 규칙:
- Epic의 전체 목표와 범위를 서술
- 오너와 관련 컴포넌트를 자연어로 포함
- 하위 이슈들의 전체적인 방향성이 보이면 포함

출력: 2-3문장의 자연어 요약
"""

JIRA_SPRINT_PROMPT = f"""
당신은 Jira Sprint 정보를 검색 가능한 요약으로 변환하는 전문가입니다.

{BASE_RULES}

추가 규칙:
- 스프린트의 목표를 중심으로 서술

출력: 1-2문장의 자연어 요약
"""

SLACK_MESSAGE_PROMPT = f"""
당신은 Slack 메시지를 검색 가능한 요약으로 변환하는 전문가입니다.

{BASE_RULES}

추가 규칙:
- 채널명을 자연어로 녹여서 포함 (예: "#general에서", "#dev-backend 채널에서")
- 대화의 핵심 주제와 결론을 서술
- 멘션된 사람, 리액션의 맥락이 중요하면 포함 (예: "팀원들이 긍정적으로 반응했다")
- 스레드 답글에서 중요한 후속 논의나 결론이 있으면 포함
- 공유된 링크나 첨부파일의 맥락이 있으면 포함 (URL 자체는 제외)
- 대화체 특유의 비공식적 맥락도 의미가 있으면 유지 (감정, 긴급도, 분위기)
- 일상 대화와 업무 논의를 구분하되, 일상 대화라도 팀 맥락이 있으면 포함

출력: 3-5문장의 자연어 요약

예시 입력:
Author: 팀원B | Channel: #general | Replies: 5
Mentioned: 김철수, 박영희
Reacted: 팀원A, 이민수
Message: 어제 투자사 미팅 다녀왔는데 솔직히 피드백이 좀 냉정했어요...
Recent Replies:
[김철수]: 괜찮아요 다음에 더 잘하면 됩니다
[박영희]: 피드백 내용 공유해주실 수 있나요?

예시 출력:
팀원B이 #general 채널에서 투자사 미팅 후기를 공유했는데, 받은 피드백이 다소 부정적이었다고 전했다. 김철수와 박영희가 멘션되었으며, 김철수는 격려의 답변을, 박영희는 구체적인 피드백 내용 공유를 요청했다. 팀원A과 이민수도 리액션으로 반응하며 팀원들이 관심을 보였다.
"""

# Fallback prompt for unknown source types
DEFAULT_PROMPT = f"""
당신은 문서를 검색 가능한 요약으로 변환하는 전문가입니다.

{BASE_RULES}

출력: 2-4문장의 자연어 요약
"""


# --- 소스 타입 → 프롬프트 매핑 ---

PROMPT_MAP: dict[str, str] = {
    "github_issue": GITHUB_ISSUE_PROMPT,
    "github_pr": GITHUB_PR_PROMPT,
    "github_commit": GITHUB_COMMIT_PROMPT,
    "jira_issue": JIRA_ISSUE_PROMPT,
    "jira_epic": JIRA_EPIC_PROMPT,
    "jira_sprint": JIRA_SPRINT_PROMPT,
    "slack_message": SLACK_MESSAGE_PROMPT,
}


def get_summary_prompt(source_type: str, document: str) -> str:
    """
    소스 타입에 맞는 프롬프트와 문서를 결합하여 최종 프롬프트를 생성합니다.

    Args:
        source_type: 문서 소스 타입 (github_issue, slack_message 등)
        document: 요약할 원본 문서

    Returns:
        LLM에 전달할 최종 프롬프트
    """
    prompt = PROMPT_MAP.get(source_type, DEFAULT_PROMPT)
    return f"{prompt}\n\n---\n입력:\n{document}\n\n출력:"