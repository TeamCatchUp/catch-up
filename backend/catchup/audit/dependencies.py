from catchup.audit.export import AuditLogExportService
from catchup.audit.s3_reader import AuditLogS3Reader
from catchup.components.aws.s3 import S3Client


# Singleton
_export_service: AuditLogExportService | None = None

def get_export_service() -> AuditLogExportService:
    global _export_service
    if _export_service is None:
        s3_client = S3Client()
        reader = AuditLogS3Reader(s3_client=s3_client)
        _export_service = AuditLogExportService(reader=reader)
    return _export_service