from typing import NamedTuple
import pandas as pd
import logging
from io import BytesIO

from sqlalchemy.orm import Session

from catchup.db.models import SourceType
from catchup.db.user_source_mapping import update_tool_user_email
from catchup.mapping.resolver import sync_users_to_pre_mapping_buffer 

logger = logging.getLogger(__name__)


class RequiredColumns(NamedTuple):
    id_col: str
    email_col: str

COLUMN_MAP = {
        "slack": RequiredColumns(id_col='userid', email_col='email'),
        "atlassian": RequiredColumns(id_col='User id', email_col='email'),
        "github": RequiredColumns(id_col='github_id', email_col='company_email')
    }

VENDOR_SOURCE_MAP = {
    "github": [SourceType.GITHUB],
    "slack": [SourceType.SLACK],
    "atlassian": [SourceType.JIRA, SourceType.CONFLUENCE]
}


def process_mapping_file_sync(
    db: Session,
    vendor_type: str,
    filename: str,
    content: bytes
) -> dict:
    
    # 인코딩 전략
    if filename.endswith('.csv'):
        try:
            df = pd.read_csv(BytesIO(content), encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(BytesIO(content), encoding="cp949")
    else:
        df = pd.read_excel(BytesIO(content), engine='openpyxl')
        
    # vendor type 호환성 체크
    if vendor_type not in COLUMN_MAP:
        raise ValueError(f"지원하지 않는 협업 툴 Vendor입니다: {vendor_type}")
    
    required_cols = COLUMN_MAP[vendor_type]
    required_cols_set = {required_cols.id_col, required_cols.email_col}
    actual_cols = set(df.columns)
    
    if not required_cols_set.issubset(actual_cols):
        missing = required_cols_set - actual_cols
        raise ValueError(f"필수 컬럼이 누락되었습니다: {', '.join(missing)}")
    
    vendor_key = vendor_type.lower()
    target_sources = VENDOR_SOURCE_MAP[vendor_key]
    
    # 협업 툴 User의 email을 업로드한csv 파일 기준으로 업데이트한 결과
    stats = {"updated": 0, "skipped": 0}
    try:
        for _, row in df.iterrows():
            external_user_id = str(row.get(required_cols.id_col, '')).strip()
            external_email = str(row.get(required_cols.email_col, '')).strip().lower()
            
            if (not external_user_id or not external_email) or (external_user_id == 'nan' or external_email == 'nan'):
                stats["skipped"] += 1
                continue
            
            for source in target_sources:
                # 협업 툴 유저의 email을 어드민이 업로드한 csv에 기입된 것으로 갱신
                # TODO: row 수만큼 쿼리를 수행함에 따라 발생하는 성능 이슈 개선
                success = update_tool_user_email(
                    db=db, 
                    source_type=source,
                    external_user_id=external_user_id,
                    external_email=external_email
                )
                if success:
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
                    logger.warning("update_tool_user_email_failed: user not found in tool users table. - Skip")

        db.commit()
        
        final_stats = {
            "csv_rows_total": len(df),
            "csv_rows_skipped": stats["skipped"],
            "email_updated_count": stats["updated"],
            "total_success": 0,
            "total_failed": 0,
            "new_mappings": 0,
            "updated_mappings": 0
        }
        
        for source in target_sources:
            # oauth user와 협업 툴 user를 매핑해서 pre_mapping_buffer를 업데이트
            mapping_result = sync_users_to_pre_mapping_buffer(
                db=db,
                source_type=source
            )
            
            final_stats["total_success"] += mapping_result["success"]
            final_stats["total_failed"] += mapping_result["failed"]
            final_stats["new_mappings"] += mapping_result["mapping_created"]
            final_stats["updated_mappings"] += mapping_result["mapping_updated"]
            
        db.commit()
        logger.info(f"File sync completed for {vendor_key}: {final_stats}")        
        return final_stats
    
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"데이터베이스 저장 중 내부 오류가 발생했습니다: {e}")
