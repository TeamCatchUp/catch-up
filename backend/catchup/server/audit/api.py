
from fastapi import APIRouter
from fastapi import Depends
from fastapi.responses import StreamingResponse

from catchup.audit.dependencies import get_export_service
from catchup.audit.export import AuditLogExportService
from catchup.auth.dependencies import require_admin_user
from catchup.db.models import User
from catchup.server.dependencies import TimeRangeParam
from catchup.server.dependencies import time_range_params

router = APIRouter(
            prefix="/api/v1/audit-logs",
            tags=["Audit Logs"]
        )

@router.get(
    path="/download",
    description="집계 기간 내의 감사로그 CSV 파일을 스트리밍 형식으로 제공한다."
)
def download_audit_logs_as_csv(
    query: TimeRangeParam = Depends(time_range_params(max_days=90)),
    export_service: AuditLogExportService = Depends(get_export_service),
    _require_admin: User = Depends(require_admin_user),
):
    start_time = query.start_time
    end_time = query.end_time
    
    keys = export_service.reader.list_keys_in_range(
        start_time=start_time,
        end_time=end_time,
    )

    filename = f"audit_{start_time.strftime('%Y%m%d')}_{end_time.strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        content=export_service.stream_as_csv(keys=keys),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )