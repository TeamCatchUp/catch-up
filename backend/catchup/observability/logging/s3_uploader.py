import asyncio
import glob
import os
from pathlib import Path

import structlog

from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import AwsS3AuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.components.aws.s3 import S3Uploader
from catchup.configs.config import settings
from catchup.events.enums import AwsS3EventAction, EventType


logger = structlog.get_logger()


def _process_audit_logs() -> None:
    if not settings.AWS_S3_AUDIT_BUCKET_NAME:
        return

    log_dir = Path(settings.LOG_AUDIT_FILE_PATH).parent
    rolled_files = glob.glob(str(log_dir / "audit.*.jsonl"))

    if not rolled_files:
        return

    uploader = S3Uploader()

    for file_path in rolled_files:
        file_name = os.path.basename(file_path)
        s3_key = f"{settings.AWS_S3_AUDIT_PREFIX.strip('/')}/{file_name}"
        
        try:
            uploader.upload_file(
                file_path=file_path,
                bucket=settings.AWS_S3_AUDIT_BUCKET_NAME,
                object_key=s3_key
            )
            logger.info(
                "audit_log_external_transfer_success",
                file_name=file_name,
                s3_key=s3_key,
                storage="aws_s3"
            )
            
            os.remove(file_path)
            logger.info(
                "audit_file_removed", 
                context="post_s3_upload",
                file_path=file_path                
            )

        except Exception as e:
            logger.exception("audit_file_upload_failed", file_name=file_name)
            
            emit_audit_event(
                event_type=EventType.SYSTEM,
                event_action=AwsS3EventAction.UPLOAD_FAILED,
                level=AuditLevel.CRITICAL,
                metadata=AwsS3AuditMetadata(
                    file_name=file_name,
                    s3_key=s3_key
                ),
                immediate=True,
                error=str(e)
            )
            
        
async def audit_log_uploader_task() -> None:
    """백그라운드에서 주기적으로 _process_audit_log를 실행하는 무한 루프"""
    while True:
        await asyncio.sleep(settings.AWS_S3_AUDIT_UPLOAD_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(_process_audit_logs)
            
        except Exception as e:
            logger.exception("audit_uploader_task_crashed", error=str(e))