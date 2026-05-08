from __future__ import annotations

from enum import StrEnum


class IncrementalSuccessScope(StrEnum):
    PARENT_COHORT = "parent_cohort"
    RECORD = "record"
