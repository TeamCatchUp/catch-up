import pytest
from pydantic import ValidationError

from catchup.schemas.structures import PipelinePlan


def test_reuse_pipeline_type_rejected():
    with pytest.raises(ValidationError):
        PipelinePlan(pipeline_type="reuse", max_iterations=0)


def test_cache_turn_numbers_accepted():
    plan = PipelinePlan(pipeline_type="standard", cache_turn_numbers=[1, 2])
    assert plan.cache_turn_numbers == [1, 2]


def test_reuse_history_turn_numbers_no_longer_exists():
    plan = PipelinePlan(pipeline_type="standard")
    assert not hasattr(plan, "reuse_history_turn_numbers")
