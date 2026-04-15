from pathlib import Path
from typing import Iterator

import boto3
import structlog
from botocore.exceptions import ClientError

logger = structlog.get_logger()

class S3Client:
    """AWS S3 I/O를 담당하는 인프라 래퍼 클래스"""
    
    def __init__(self) -> None:
        self._boto3_client = boto3.client("s3")
        
    
    def get_paginator(self, operation: str):
        return self._boto3_client.get_paginator(operation)
        
    def upload_file(
        self, 
        file_path: str | Path, 
        bucket: str, 
        object_key: str
    ) -> None:
        """
        로컬 파일을 S3의 지정된 버킷과 키로 업로드한다.
        성공 시 아무것도 반환하지 않으며, 실패 시 boto3 예외를 던진다.
        """
        target_path = Path(file_path)
        if not target_path.exists():
            logger.warning(
                "upload_file_not_found", 
                file_path=str(target_path)
            )
            raise FileNotFoundError(f"File not found: {target_path}")

        with open(target_path, "rb") as f:
            self._boto3_client.upload_fileobj(f, bucket, object_key)

    def get_object(
        self,
        bucket: str,
        object_key: str,
    ) -> Iterator[bytes]:
        """
        S3 오브젝트를 64KB 청크 단위의 이터레이터로 반환한다.
        전체 파일을 메모리에 올리지 않아 대용량 파일 핸들링에 적합하다.
        """
        try:
            response = self._boto3_client.get_object(
                Bucket=bucket,
                Key=object_key
            )
            return response["Body"].iter_chunks(chunk_size=64 * 1024)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "NoSuchKey":
                logger.warning(
                    "s3_object_not_found",
                    bucket=bucket,
                    object_key=object_key
                )
                raise FileNotFoundError(f"S3 object not found: {object_key}")
            raise