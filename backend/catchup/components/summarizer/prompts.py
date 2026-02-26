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
당신은 소프트웨어 개발팀의 업무 기록을 검색에 최적화된 요약문으로 변환하는 전문가입니다.

## 역할
다양한 출처(이슈 트래커, 코드 저장소, 팀 채팅 등)의 문서를 받아서,
출처에 관계없이 동일한 문체와 구조로 요약합니다.

## 핵심 원칙

### 반드시 포함할 것
- **누가**: 관련된 사람의 이름 (작성자, 담당자, 리뷰어, 대화 참여자)
- **무엇을**: 구체적인 기술 작업, 기능, 버그, 논의 주제
- **왜/맥락**: 작업의 목적, 문제의 원인, 결정의 이유
- **결론/결과**: 합의된 내용, 해결 방법, 남은 과제
- 기술 키워드와 고유 식별자(CAT-xxx, #123 등)는 그대로 유지
- 감정적 맥락이 의미 있으면 반영 (긍정적 반응, 우려, 긴급함)

### 반드시 제거할 것
- 도구/플랫폼 특유의 표현: "PR로", "Epic의 하위 작업", "#채널에서", "스프린트의 일환으로"
- 구조적 메타데이터: 상위-하위 관계 표현, 스프린트/보드 소속, 채널명, 라벨 나열
- 형식적 표현: "이 이슈는", "이 PR은", "이 메시지는"
- 순수 상태값: 날짜, 우선순위, 상태(open/closed/merged)
- 파일 경로, URL, 변경 규모(라인 수, 파일 수)

### 문체 규칙
- 모든 요약은 "~했다/~이다" 체의 서술문으로 작성
- 첫 문장은 반드시 "누가 무엇을 했는가"로 시작
- 플랫폼을 특정할 수 있는 용어를 사용하지 않음
- 3인칭 관찰자 시점으로 작성

## 출력 형식
2-4문장의 자연어 요약을 작성하세요. 다른 부가 설명 없이 요약만 출력합니다.
"""

# =============================================================================
# Source-specific extraction guides (User Prompt에 포함)
# 소스별로 "어디서 정보를 추출할지"만 안내, 어투/형식은 통일
# =============================================================================

EXTRACTION_GUIDE: dict[str, str] = {
    "github_issue": """\
## 추출 가이드
이 문서는 코드 저장소의 이슈 보고입니다.
- 보고자와 담당자가 누구인지 확인
- 문제/요청의 핵심이 무엇인지 파악
- 논의에서 나온 원인 분석이나 해결 방향 추출
- 관련된 다른 작업(수정 작업, 연관 이슈)과의 의미적 연결 파악""",

    "github_pr": """\
## 추출 가이드
이 문서는 코드 변경 요청입니다.
- 작성자가 무엇을 왜 변경했는지 파악
- 어떤 문제를 해결하는 변경인지 확인
- 리뷰어들의 주요 피드백이나 기술적 제안 추출
- 변경의 성격(버그 수정, 새 기능, 리팩토링) 파악""",

    "github_commit": """\
## 추출 가이드
이 문서는 코드 커밋 기록입니다.
- 작성자가 어떤 모듈/기능을 변경했는지 파악
- 변경 목적 추출
- 관련된 작업 맥락 확인""",

    "jira_issue": """\
## 추출 가이드
이 문서는 작업 관리 시스템의 작업 항목입니다.
- 담당자와 요청자 확인
- 작업의 구체적 목표와 범위 파악
- 논의에서 나온 기술적 결정이나 합의 사항 추출
- 다른 작업과의 의존 관계가 있으면 의미적으로 연결""",

    "jira_epic": """\
## 추출 가이드
이 문서는 상위 수준의 기능/프로젝트 단위 작업입니다.
- 전체 목표와 범위 파악
- 책임자와 관련 기술 영역 확인
- 포함된 세부 작업들의 전체적 방향성 추출""",

    "jira_sprint": """\
## 추출 가이드
이 문서는 일정 기간의 작업 계획입니다.
- 해당 기간의 핵심 목표 파악
- 주요 작업 항목 확인""",

    "slack_message": """\
## 추출 가이드
이 문서는 팀 대화 기록입니다.
- 대화의 핵심 주제와 결론 파악
- 참여자와 각자의 의견/반응 확인
- 합의된 결정이나 액션 아이템 추출
- 비공식적 맥락이라도 업무적 의미가 있으면 포함""",
}

# =============================================================================
# Few-shot examples (소스-중립적 통일 어투)
# =============================================================================

FEW_SHOT_EXAMPLES: dict[str, str] = {
    "github_issue": """
예시 입력:
[Issue #42] 로그인 페이지 무한 로딩
Status: open | Labels: bug, frontend
Assigned to: @jane | Reported by: @john
Description: 로그인 버튼 클릭 시 스피너만 돌고 진행이 안 됨...
Recent Discussion:
[2024-01-16 @bob]: 네트워크 탭 보니까 401 에러 반복 발생
Related: Referenced in PR #55

예시 출력:
john이 로그인 페이지에서 버튼 클릭 시 무한 로딩이 발생하는 버그를 보고했고, jane이 수정을 담당하고 있다. bob이 원인을 조사하여 401 에러가 반복 발생하는 것을 확인했다. 관련 수정 작업(#55)이 진행 중이다.""",

    "github_pr": """
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
jane이 로그인 시 401 에러를 유발하던 토큰 갱신 로직의 race condition을 수정했다. 로그인 무한 로딩 문제(#42)의 원인이었다. bob이 변경을 승인했고, alice는 auth.py에 null 체크를 추가하면 더 안전하겠다고 제안했다.""",

    "github_commit": "",

    "jira_issue": """
예시 입력:
[CAT-123] 로그인 기능 구현
Assigned to: 홍길동 | Reporter: 김철수
Parent: CAT-100 (로그인 Epic)
Description: OAuth2 기반 소셜 로그인 구현...
Discussion:
[홍길동]: Google, GitHub 두 개만 우선 지원하기로 함
Related: CAT-124 (테스트 작성) - blocks

예시 출력:
홍길동이 OAuth2 기반 소셜 로그인 기능(CAT-123)을 구현하고 있으며, 김철수가 요청한 작업이다. Google과 GitHub 두 개 프로바이더를 우선 지원하기로 결정했다. 테스트 작성 작업(CAT-124)이 이 구현에 의존하고 있다.""",

    "jira_epic": "",

    "jira_sprint": "",

    "slack_message": """
예시 입력:
Author: 팀원B | Channel: #general | Replies: 5
Mentioned: 김철수, 박영희
Reacted: 팀원A, 이민수
Message: 어제 투자사 미팅 다녀왔는데 솔직히 피드백이 좀 냉정했어요...
Recent Replies:
[김철수]: 괜찮아요 다음에 더 잘하면 됩니다
[박영희]: 피드백 내용 공유해주실 수 있나요?

예시 출력:
팀원B이 투자사 미팅 결과를 공유했는데, 피드백이 다소 부정적이었다고 전했다. 김철수가 격려했고, 박영희는 구체적인 피드백 내용 공유를 요청했다. 팀원A과 이민수도 관심을 보이며 팀 차원에서 반응이 있었다.""",
}

# =============================================================================
# Default fallback
# =============================================================================

DEFAULT_EXTRACTION_GUIDE = """\
## 추출 가이드
이 문서는 팀의 업무 기록입니다.
- 관련된 사람, 핵심 주제, 결론을 중심으로 파악"""


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