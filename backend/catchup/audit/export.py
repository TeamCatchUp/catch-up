import csv
import io
import json
from typing import Generator

import structlog

from catchup.audit.s3_reader import AuditLogS3Reader
from catchup.configs.config import settings

# TODO: "catchup.audit"으로 인식되는 문제
logger = structlog.get_logger()


AUDIT_CSV_HEADER = [
    "timestamp",
    "level", 
    "event",
    "status",
    "actor",
    "metadata",
    "trace_id",
    "service",
    "environment",
    "version",
]

class AuditLogExportService:
    def __init__(
        self,
        reader: AuditLogS3Reader
    ) -> None:
        self.reader = reader
    
    def stream_as_csv(
        self,
        keys: list[str],
    ) -> Generator[str, None, None]:
        
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        
        # CSV Header
        writer.writerow(AUDIT_CSV_HEADER)
        yield "\ufeff" + buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
        
        for key in keys:
            chunks = self.reader.s3_client.get_object(
                bucket=settings.AWS_S3_AUDIT_BUCKET_NAME,
                object_key=key
            )
            leftover = ""
            
            for chunk in chunks:
                text = leftover + chunk.decode("utf-8")
                lines = text.split("\n")
                leftover = lines.pop()
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        record: dict = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("jsonl_parse_failed")
                        continue
                    
                    writer.writerow(record.get(field, "") for field in AUDIT_CSV_HEADER)
                    yield buffer.getvalue()
                    buffer.seek(0)
                    buffer.truncate()
                    
                if leftover.strip():
                    try:
                        record = json.loads(leftover.strip())
                        writer.writerow(record.get(field, "") for field in AUDIT_CSV_HEADER)
                        yield buffer.getvalue()
                        buffer.seek(0)
                        buffer.truncate()
                    except json.JSONDecodeError:
                        logger.warning("jsonl_last_line_parse_failed", line=leftover[:200])

        logger.info("audit_csv_export_completed", file_count=len(keys))
