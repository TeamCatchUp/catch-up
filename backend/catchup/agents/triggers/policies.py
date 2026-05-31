from typing import Annotated
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import PositiveInt
from pydantic import StringConstraints
from pydantic import TypeAdapter
from pydantic import ValidationError
from pydantic import field_validator

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]


class PolicyValidationError(ValueError):
    """Raised when a trigger policy condition is not executable."""


class TriggerPolicyBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str


class ImmediatePolicy(TriggerPolicyBase):
    kind: Literal["immediate"]
    where: dict[str, Any] = Field(default_factory=lambda: {"all": []})


class DebouncePolicy(TriggerPolicyBase):
    kind: Literal["debounce"]
    start_event_type: NonEmptyStr
    reset_event_types: tuple[NonEmptyStr, ...] = Field(min_length=1)
    entity_key_path: NonEmptyStr
    reset_entity_key_path: NonEmptyStr
    quiet_period_seconds: PositiveInt
    run_context: NonEmptyStr = "latest_event"
    where: dict[str, Any] = Field(default_factory=lambda: {"all": []})
    reset_where: dict[str, Any] = Field(default_factory=lambda: {"all": []})

    @field_validator("quiet_period_seconds", mode="before")
    @classmethod
    def _reject_bool_quiet_period(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("quiet_period_seconds must be a positive integer")
        return value


TriggerPolicy = Annotated[
    ImmediatePolicy | DebouncePolicy,
    Field(discriminator="kind"),
]

_TRIGGER_POLICY_ADAPTER = TypeAdapter(TriggerPolicy)


def parse_policy(condition: dict[str, Any]) -> TriggerPolicy:
    try:
        return _TRIGGER_POLICY_ADAPTER.validate_python(condition)
    except ValidationError as exc:
        raise PolicyValidationError(str(exc)) from exc
