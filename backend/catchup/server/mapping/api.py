from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
import logging

from catchup.mapping.file import process_mapping_file_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/mapping", tags=["mapping"])


@router.post("/upload")
async def upload_github_mapping_file(
    file: UploadFile = File(...),
):
    filename = file.filename.lower()
    
    if not filename.endswith(('.csv', '.xlsx', '.xls')):
        logger.warning(f"[MAPPING][GITHUB] Invalid file extension attempted: {filename}")
        raise HTTPException(status_code=400, detail="CSV 또는 Excel(xlsx, xls) 파일만 업로드 가능합니다.")
    
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"[MAPPING][GITHUB] File Read Error: {e}")
        raise HTTPException(status_code=400, detail="파일을 읽는 중 오류가 발생했습니다.")
    finally:
        await file.close()

    try:
        stats = await run_in_threadpool(process_mapping_file_sync, filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return {
        "status": "success",
        "file_type": "excel" if filename.endswith(('.xlsx', '.xls')) else "csv",
        "stats": stats
    }