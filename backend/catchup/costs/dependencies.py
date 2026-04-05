from catchup.components.aws.cloudwatch import CloudWatchMetrics
from catchup.components.aws.factory import get_cloudwatch_metrics
from catchup.configs.config import settings


def cloudwatch_metrics_dependency() -> CloudWatchMetrics:
    return get_cloudwatch_metrics(
        region_name=settings.AWS_EMBEDDING_MODEL_REGION
    )
