import pandas as pd
import logging
from io import BytesIO

from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.mapping.resolver import upsert_pre_mapping 

logger = logging.getLogger(__name__)


def process_mapping_file_sync(filename: str, content: bytes) -> dict:
    """
    업로드된 github 사용자 정보 파일 바이너리를 파싱하여 DB에 매핑 데이터를 동기화한다.
    """
    
    if filename.endswith('.csv'):
        try:
            df = pd.read_csv(BytesIO(content), encoding="utf-8-sig")
        except UnicodeDecodeError:
            logger.warning(f"[MAPPING][GITHUB] utf-8-sig failed for {filename}, trying cp949")
            df = pd.read_csv(BytesIO(content), encoding="cp949")
    else:
        df = pd.read_excel(BytesIO(content), engine='openpyxl')

    required_columns = {'github_id', 'company_email'}
    actual_columns = set(df.columns)
    
    if not required_columns.issubset(actual_columns):
        missing = required_columns - actual_columns
        logger.warning(f"[MAPPING][GITHUB] Missing columns in {filename}. Required: {required_columns}, Found: {actual_columns}")
        raise ValueError(f"필수 컬럼이 누락되었습니다: {', '.join(missing)}")

    with SessionLocal() as db:
        stats = {"created": 0, "updated": 0, "skipped": 0}
        index = 0
        
        try:
            for idx, row in df.iterrows():
                index = idx
                
                if pd.isna(row.get('company_email')) or pd.isna(row.get('github_id')):
                    stats["skipped"] += 1
                    continue
                    
                github_id = str(row['github_id']).strip()
                company_email = str(row['company_email']).strip().lower()
                full_name = str(row.get('full_name', '')).strip() if pd.notna(row.get('full_name')) else ''

                if not company_email or not github_id or github_id.lower() == 'nan':
                    stats["skipped"] += 1
                    continue
                
                is_created = upsert_pre_mapping(
                    db=db,
                    sub="FILE_IMPORTED",
                    email=company_email,
                    name=full_name,
                    source_type=SourceType.GITHUB,
                    external_user_id=github_id
                )
                
                if is_created:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
                
            db.commit()
            logger.info(f"[MAPPING][GITHUB] Sync Completed. Stats: {stats}")
            return stats
    
        except Exception as e:
            db.rollback()
            logger.error(f"[MAPPING][GITHUB] DB Sync Error at row {index}: {e}", exc_info=True)
            raise RuntimeError("데이터베이스 저장 중 내부 오류가 발생했습니다.")