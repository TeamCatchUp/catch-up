from typing import Any

from catchup.agents.triggers.policies import TriggerPolicy
from catchup.agents.triggers.policies import parse_policy


class TriggerPolicyValidator:
    """Builder가 생성한 raw Trigger Policy JSON을 검증"""

    def validate_policy(self, condition: dict[str, Any]) -> TriggerPolicy:
        """Trigger condition dict를 지원되는 policy 모델로 파싱한다."""
        return parse_policy(condition)


trigger_policy_validator = TriggerPolicyValidator()
