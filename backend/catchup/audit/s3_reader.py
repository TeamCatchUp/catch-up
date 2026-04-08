from datetime import datetime

from catchup.components.aws.s3 import S3Client
from catchup.configs.config import settings


class AuditLogS3Reader:
    def __init__(
        self,
        s3_client: S3Client
    ):
        self.s3_client = s3_client
    
    def list_keys_in_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[str]: 
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        
        paginator = self.s3_client.get_paginator("list_objects_v2")
        keys = []
        
        for page in paginator.paginate(
            Bucket=settings.AWS_S3_AUDIT_BUCKET_NAME,
            Prefix=settings.AWS_S3_AUDIT_PREFIX,
        ):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                
                try:
                    ts = int(key.split("/")[-1].split(".")[1])
                except (IndexError, ValueError):
                    continue
                
                if start_ts <= ts <= end_ts:
                    keys.append(key)
        
        return sorted(keys)
