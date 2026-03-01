from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile
from fastapi.concurrency import run_in_threadpool
import logging

from sqlalchemy.orm import Session

from catchup.auth.dependencies import require_admin_user
from catchup.db.dependencies import get_db
from catchup.db.models import SourceType
from catchup.mapping.file import process_mapping_file_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/mapping", tags=["mapping"])


@router.post(
    path="/{vendor_type}/upload",
    summary="어드민용 협업툴 사용자 리스트 업로드"
)
async def upload_tool_mapping_file(
    vendor_type: str = Path(..., description="협업 툴 vendor 종류 (github, slack, atlassian)"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _check_admin = Depends(require_admin_user)
):
    filename = file.filename.lower()
    
    if not filename.endswith(('.csv', '.xlsx', '.xls')):
        logger.warning(f"Invalid file extension attempted: {filename}")
        raise HTTPException(
            status_code=400,
            detail="CSV 또는 Excel(xlsx, xls) 파일만 업로드 가능합니다."
        )
    
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"File Read Error: {e}")
        raise HTTPException(
            status_code=400,
            detail="파일을 읽는 중 오류가 발생했습니다."
        )
    finally:
        await file.close()

    try:
        stats = await run_in_threadpool(
            process_mapping_file_sync,
            db,
            vendor_type,
            filename,
            content
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return {
        "status": "success",
        "file_type": "excel" if filename.endswith(('.xlsx', '.xls')) else "csv",
        "stats": stats
    }