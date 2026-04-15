from datetime import datetime

import boto3
import structlog

from catchup.components.aws.utils import extract_model_id_from_arn

logger = structlog.get_logger()


class CloudWatchMetrics:
    def __init__(
        self,
        region_name: str = "ap-northeast-2"
    ):
        self.client = boto3.client(
            "cloudwatch",
            region_name=region_name
        )
    
    def get_embedding_input_tokens(
        self,
        model_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """
        BedrockEmbeddings 호출로 인한 입력 토큰 사용량을 CloudWatch로부터 집계한다.
        요청 맥락(Ingestion, Query 등)을 구분하지 않고 전체 호출량을 합산하므로,
        조직 전체의 대략적인 총 사용량 파악 용도로만 사용할 수 있다.
        개별 사용자 또는 호출 목적별 세분화된 집계에는 사용할 수 없다.

        Args:
            model_id: Bedrock 임베딩 모델 ID. ARN 형식인 경우 자동으로 파싱된다.
            start_time: 집계 시작 시간 (UTC).
            end_time: 집계 종료 시간 (UTC).
            
        Raises:
            botocore.exceptions.ClientError: CloudWatch API 호출 실패 시.
            
        Returns:
            집계 기간 내 총 입력 토큰 수.
        """
        
        # ARN인 경우 model 식별 부분만 추출
        # (e.g. arn:.../global.cohere.embed-v4:0 -> global.cohere.embed-v4:0)
        # Dimensions의 ModelId는 ARN을 포함한 모델 id를 사용할 수 없음.
        parsed_model_id = extract_model_id_from_arn(model_id)
        
        try:
            response = self.client.get_metric_statistics(
                Namespace="AWS/Bedrock",
                MetricName="InputTokenCount",
                Dimensions=[{"Name": "ModelId", "Value": parsed_model_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=["Sum"]
            )
        except Exception as e:
            logger.error(
                "embeddings_total_tokens_aggregation_failed",
                error=str(e)
            )
            raise
        
        total_tokens = int(sum(point["Sum"] for point in response["Datapoints"]))
        logger.info(
            "embeddings_total_tokens_aggregation_success",
            total_tokens=total_tokens
        )
        return total_tokens

