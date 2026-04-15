from functools import lru_cache

from catchup.components.aws.cloudwatch import CloudWatchMetrics


@lru_cache(maxsize=1)
def get_cloudwatch_metrics(region_name: str) -> CloudWatchMetrics:
    return CloudWatchMetrics(
        region_name=region_name
    )
