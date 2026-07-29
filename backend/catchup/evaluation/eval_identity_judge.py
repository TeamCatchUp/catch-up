"""identity judge의 판별력을 golden set으로 잰다.

`run_resolution_pipeline.py`가 DB의 실제 후보를 판정한다면, 이 스크립트는
정답을 아는 고정 픽스처만으로 judge를 직접 호출한다. DB 상태와 무관하게
몇 번을 돌려도 같은 입력이 들어가므로, 프롬프트를 고칠 때마다 돌려서
회귀를 잡는 계기판이다.

케이스는 세 성격으로 나뉜다.

- 동명이의 반례: 같은 이름이 다른 대상을 가리킨다. 정답 same=false.
  과병합은 불가역이므로 여기서 틀리면 가장 위험하다.
- 속성 모순 양성: 같은 대상인데 출처마다 속성 값이 다르다. 정답
  same=true. 모순은 Claim 충돌 감지의 일이지 identity의 일이 아니다.
- 평범한 양성: 같은 대상이 type 라벨만 다르게 뽑혔다. 정답 same=true.

발췌는 `experiments/channel_talk/raw`의 합성 상담에서 따온 고정
문자열이다. 원문이 바뀌어도 이 픽스처는 흔들리지 않는다.

LLM은 비결정적이므로 `--repeat`로 같은 케이스를 여러 번 물어 흔들림을
잴 수 있다. 개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.eval_identity_judge
    uv run python -m catchup.evaluation.eval_identity_judge --repeat 3
"""

from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    BedrockIdentityJudge,
)
from catchup.knowledge_maintenance.ports.identity_judge import JudgeCandidate


@dataclass(frozen=True, slots=True)
class EvalCase:
    """정답을 아는 판정 케이스 하나를 표현한다.

    Attributes:
        key: 결과 표에 찍을 짧은 이름을 나타낸다.
        kind: 케이스 성격(homonym·contradiction·positive)을 나타낸다.
        expected_same: 정답 판정을 나타낸다.
        members: (type, name, excerpt) 튜플의 목록을 담는다.
    """

    key: str
    kind: str
    expected_same: bool
    members: tuple[tuple[str, str, str], ...]


CASES: tuple[EvalCase, ...] = (
    EvalCase(
        key="아틀라스",
        kind="homonym",
        expected_same=False,
        members=(
            (
                "system",
                "아틀라스",
                "고객: 아틀라스라고 부르는 시스템이에요. 저희가 자체 개발한 "
                "창고관리 시스템이고, 재고랑 입출고 기록이 전부 여기에 있어요.\n"
                "상담원: 아틀라스가 REST API를 제공하나요?",
            ),
            (
                "project",
                "아틀라스",
                "고객: 저희 세종에듀는 지금 아틀라스라는 프로젝트를 진행 "
                "중이에요. 레거시 학사 데이터를 새 플랫폼으로 옮기는 이관 "
                "프로젝트인데요.\n고객: 올해 9월 말 종료 목표예요.",
            ),
        ),
    ),
    EvalCase(
        key="머큐리",
        kind="homonym",
        expected_same=False,
        members=(
            (
                "service",
                "머큐리",
                "고객: 머큐리라는 결제 서비스예요. 온라인 가맹점 결제를 "
                "대행하고 있고, CS팀이 거래 내역을 매번 관리자 페이지에서 "
                "찾느라 오래 걸려요.",
            ),
            (
                "chatbot",
                "머큐리",
                "고객: 머큐리라고 부르는 사내 챗봇이에요. 인사팀이 규정 문서 "
                "기반으로 답변 시나리오를 손으로 만들어서 운영하고 있어요.",
            ),
        ),
    ),
    EvalCase(
        key="캐치업 오픈 API",
        kind="contradiction",
        expected_same=True,
        members=(
            (
                "api",
                "캐치업 오픈 API",
                "고객: 캐치업 오픈 API를 쓰려고 하는데 호출 한도가 어떻게 "
                "되나요?\n상담원: 캐치업 오픈 API의 호출 한도는 분당 "
                "60회입니다. 첨부파일은 최대 10MB까지 업로드할 수 있습니다. "
                "SSO는 현재 지원하지 않습니다.",
            ),
            (
                "api",
                "캐치업 오픈 API",
                "고객: 캐치업 오픈 API 호출 한도를 확인하고 싶어요.\n상담원: "
                "캐치업 오픈 API의 호출 한도는 분당 120회입니다. 첨부파일은 "
                "최대 25MB까지 업로드할 수 있습니다. SSO를 지원합니다.",
            ),
        ),
    ),
    EvalCase(
        key="Slack",
        kind="positive",
        expected_same=True,
        members=(
            (
                "platform",
                "Slack",
                "고객: Slack이랑 Jira를 연결하면 비공개 채널이나 비공개 "
                "프로젝트 내용도 검색되나요?",
            ),
            (
                "integration",
                "Slack",
                "상담원: Slack 연결은 관리자 계정으로 워크스페이스를 연동한 "
                "뒤 검색 범위를 고르는 방식입니다.",
            ),
            (
                "data_source",
                "Slack",
                "고객: 저희는 Slack 대화가 주요 데이터인데, 과거 메시지도 "
                "동기화되나요?",
            ),
        ),
    ),
    EvalCase(
        key="캐치업",
        kind="positive",
        expected_same=True,
        members=(
            (
                "product",
                "캐치업",
                "고객: 캐치업을 도입하면 사내 문서 검색을 어디까지 자동화할 "
                "수 있나요?",
            ),
            (
                "system",
                "캐치업",
                "고객: 저희 사내 창고관리 시스템이 있는데, 캐치업이랑 연동할 "
                "수 있나요?",
            ),
            (
                "service",
                "캐치업",
                "고객: 사내 문의용 챗봇을 자체 운영 중인데, 캐치업으로 "
                "대체가 가능한지 알고 싶어요.",
            ),
        ),
    ),
    EvalCase(
        # 실제 파이프라인 발췌를 그대로 쓴 어려운 양성이다. 발췌가 다른
        # 시스템(아틀라스·머큐리) 얘기 중심이라, 문서의 주제와 이름의
        # 지시 대상을 혼동하면 갈라놓게 된다. 첫 베이스라인에서 0/5로
        # 실패했고, 주제·지시 대상 구분 규칙을 프롬프트에 넣어 잡았다.
        # 이 규칙의 회귀 감시 케이스다.
        key="캐치업(노이즈 발췌)",
        kind="hard-positive",
        expected_same=True,
        members=(
            (
                "system",
                "캐치업",
                "고객: 팀 회의 녹화 영상이 많이 쌓여 있는데 이것도 캐치업에서 "
                "검색할 수 있나요?\n상담원: 영상 파일 자체를 연결하려는 건가요, "
                "아니면 회의 도구에서 제공하는 자막이나 녹취록이 있나요?\n고객: "
                "Google Drive에 mp4 파일만 있습니다.\n상담원: 영상은 문서와 "
                "처리 방식이 달라서 바로 검색 가능한지 확인이 필요합니다.\n"
                "고객: 음성을 자동으로 글로 바꿔주는 기능도 있나요?\n상담원: "
                "영상의 음성을 텍스트로 바꾸는 전사 과정이 먼저 필요합니다. "
                "현재 지원 범위와 파일 제한을 확인해드릴게요.\n고객: 영상 "
                "하나가 보통 1시간이고 2G",
            ),
            (
                "system",
                "캐치업",
                "고객: 저희 한빛물류에서 쓰는 사내 창고관리 시스템이 있는데, "
                "캐치업이랑 연동할 수 있나요?\n상담원: 안녕하세요. 어떤 "
                "시스템인지 조금 더 알려주실 수 있을까요?\n고객: 아틀라스라고 "
                "부르는 시스템이에요. 저희가 자체 개발한 창고관리 시스템이고, "
                "재고랑 입출고 기록이 전부 여기에 있어요.\n상담원: 아틀라스가 "
                "REST API를 제공하나요? 외부에서 데이터를 읽어올 수 있는 "
                "경로가 있어야 연동 검토가 가능합니다.\n고객: 네, 아틀라스에 "
                "조회용 API는 있어요. 사내망에서만 열려 있긴 하지만요.\n"
                "상담원: 그렇다면 아틀라스의 API 명세와 ",
            ),
            (
                "product",
                "캐치업",
                "고객: 저희 세종에듀는 지금 아틀라스라는 프로젝트를 진행 "
                "중이에요. 레거시 학사 데이터를 새 플랫폼으로 옮기는 이관 "
                "프로젝트인데요.\n상담원: 안녕하세요. 아틀라스 프로젝트가 진행 "
                "중이시군요. 캐치업 도입과 어떤 관계가 있는지 여쭤봐도 "
                "될까요?\n고객: 아틀라스가 끝나야 데이터가 한곳에 모이거든요. "
                "그 전에 캐치업을 붙이면 옮기다 만 데이터를 검색하게 될까 봐 "
                "걱정이에요.\n상담원: 합리적인 걱정입니다. 아틀라스의 완료 "
                "예정 시점이 언제인가요?\n고객: 올해 9월 말 종료 목표예요. "
                "아틀라스 종료 후 10월에 캐치업을 도입하고 싶어요.\n상",
            ),
            (
                "service",
                "캐치업",
                "고객: 저희 페이루트에서 운영하는 결제 서비스가 있는데, 거래 "
                "문의 대응에 캐치업을 쓸 수 있을지 궁금해요.\n상담원: "
                "안녕하세요. 어떤 서비스인지 알려주시겠어요?\n고객: 머큐리라는 "
                "결제 서비스예요. 온라인 가맹점 결제를 대행하고 있고, CS팀이 "
                "거래 내역을 매번 관리자 페이지에서 찾느라 오래 걸려요.\n"
                "상담원: 머큐리의 거래 데이터를 캐치업이 검색하려면, 머큐리 "
                "쪽에서 거래 조회 API를 열어주셔야 합니다. 결제 데이터라 "
                "개인정보 마스킹 정책도 함께 정해야 하고요.\n고객: 머큐리에 "
                "정산·거래 조회 API는 이미 있어요. 카드번호 같은",
            ),
            (
                "product",
                "캐치업",
                "고객: 저희 다온컴퍼니는 사내 문의용 챗봇을 자체 운영 중인데, "
                "캐치업으로 대체가 가능한지 알고 싶어요.\n상담원: 안녕하세요. "
                "지금 운영 중인 챗봇에 대해 조금 더 알려주시겠어요?\n고객: "
                "머큐리라고 부르는 사내 챗봇이에요. 인사팀이 규정 문서 "
                "기반으로 답변 시나리오를 손으로 만들어서 운영하고 있어요.\n"
                "상담원: 머큐리가 시나리오 기반이라면, 문서가 바뀔 때마다 "
                "시나리오를 다시 만들어야 하는 부담이 있으셨겠네요.\n고객: "
                "맞아요. 머큐리 시나리오 관리에 인사팀 한 명이 거의 붙어 "
                "있어요. 그래서 문서만 연결하면 알아서 답하는 방식을 찾고",
            ),
        ),
    ),
    EvalCase(
        key="보안팀",
        kind="positive",
        expected_same=True,
        members=(
            (
                "team",
                "보안팀",
                "고객: 우선 전용 VPC를 선호하지만 보안팀은 온프레미스도 같이 "
                "검토하자고 합니다.",
            ),
            (
                "organizational_unit",
                "보안팀",
                "고객: 네, 보안팀 확인 받고 전달드릴게요.",
            ),
        ),
    ),
)


def _judge_case(
    judge: BedrockIdentityJudge,
    case: EvalCase,
) -> tuple[bool | None, str]:
    """케이스 하나를 판정하고 (판정, 이유)를 돌려준다. 실패는 None이다."""
    group = tuple(
        JudgeCandidate(
            candidate_id=uuid.uuid4(),
            proposed_type=member_type,
            proposed_name=member_name,
            excerpt=excerpt,
        )
        for member_type, member_name, excerpt in case.members
    )
    try:
        verdict = judge.judge(group)
    except Exception as error:
        return None, f"{type(error).__name__}: {error}"
    return verdict.same, verdict.reason


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="각 케이스를 몇 번 물을지 정한다. 비결정성 흔들림 측정용이다.",
    )
    parser.add_argument(
        "--capacity",
        choices=[capacity.value for capacity in ModelCapacity],
        default=ModelCapacity.LARGE.value,
    )
    args = parser.parse_args()

    service = get_llm_service(
        provider=LlmProvider.AWS_BEDROCK,
        model_capacity=ModelCapacity(args.capacity),
        streaming=False,
    )
    judge = BedrockIdentityJudge(service.get_llm())

    total = 0
    correct = 0
    print(f"=== identity judge golden set ({len(CASES)}케이스 × {args.repeat}회) ===")
    for case in CASES:
        outcomes: list[bool | None] = []
        last_reason = ""
        for _ in range(args.repeat):
            same, reason = _judge_case(judge, case)
            outcomes.append(same)
            last_reason = reason
        hits = sum(1 for same in outcomes if same is case.expected_same)
        total += args.repeat
        correct += hits
        mark = "✓" if hits == args.repeat else "✗"
        print(
            f"  {mark} [{case.kind:<13}] {case.key:<12} "
            f"정답 {'same' if case.expected_same else 'diff'} · "
            f"적중 {hits}/{args.repeat}"
        )
        if hits < args.repeat:
            print(f"      마지막 이유: {last_reason[:160]}")

    print(f"\n정확도 {correct}/{total} ({correct / total:.0%})")


if __name__ == "__main__":
    main()
