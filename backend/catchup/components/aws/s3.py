import boto3
from pathlib import Path

class S3Uploader:
    """AWS S3 업로드를 위한 유틸리티 클래스"""
    
    def __init__(self) -> None:
        self.s3_client = boto3.client("s3")

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
            raise FileNotFoundError(f"File not found: {target_path}")

        with open(target_path, "rb") as f:
            self.s3_client.upload_fileobj(f, bucket, object_key)