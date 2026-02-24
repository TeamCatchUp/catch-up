import logging
from sqlalchemy.orm import Session

from catchup.db.models import PreMappingBuffer, SourceType
from catchup.db.user_source_mapping import (
    add_new_mapping, 
    find_external_user_id_by_email,
    find_premapped_user_by_email
)
from catchup.db.users import get_user_by_sub
from catchup.mapping.schemas import OAuthUserSchema


logger = logging.getLogger(__name__)

def sync_users_to_pre_mapping_buffer(
    db: Session,
    source_type: SourceType,
    oauth_users: list[OAuthUserSchema]
) -> dict:
    sync_results = {"success": 0, "failed": 0, "mapping_created": 0, "mapping_updated": 0}
    
    for user in oauth_users:
        email = user.email
        sub = user.sub
        display_name = user.name  # 추후 임베딩에 활용되는 이름
        
        if not email:
            sync_results["failed"] += 1
            continue
        
        external_user_id = find_external_user_id_by_email(
            db=db,
            source_type=source_type,
            email=email
        )
        
        if not external_user_id:
            continue
        
        created = upsert_pre_mapping(
            db,
            sub=sub,
            email=email,
            name=display_name,
            source_type=source_type,
            external_user_id=external_user_id              
        )
        
        if created:
            sync_results["mapping_created"] += 1
        else:
            sync_results["mapping_updated"] += 1
        
        sync_results["success"] += 1
    
    logger.info(f"Sync Result: {sync_results}")
    
    return sync_results


def upsert_pre_mapping(
    db: Session,
    sub: str,
    email: str,
    name: str,
    source_type: SourceType,
    external_user_id: str
):
    """기존 매핑이 있으면 갱신하고, 없으면 새로 생성한다."""
    
    premapped = find_premapped_user_by_email(
        db=db,
        email=email,
        source_type=source_type
    )
    
    if premapped:
        premapped.external_user_identifier = external_user_id
        if name:
            premapped.name = name
        if sub not in ["FILE_IMPORTED"]:
            premapped.sub = sub
        return False
    
    else:
        existing = get_user_by_sub(db, sub)
        is_registered = False
        if existing:
            is_registered = True
                
        new_entry = PreMappingBuffer(
            sub=sub,
            email=email,
            name=name,
            source_type=source_type,
            external_user_identifier=external_user_id,
            is_registered=is_registered
        )
        add_new_mapping(db, new_entry)
        return True
    