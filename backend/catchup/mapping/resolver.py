import logging
from sqlalchemy.orm import Session

from catchup.db.models import PreMappingBuffer, SourceType
from catchup.db.user_source_mapping import (
    add_new_mapping, 
    find_external_user_id_by_email,
    find_premapped_user_by_email
)
from catchup.mapping.schemas import OktaUser as OktaUserSchema


logger = logging.getLogger(__name__)

def sync_users_to_pre_mapping_buffer(
    db: Session,
    source_type: SourceType,
    okta_users: list[OktaUserSchema]
) -> dict:
    sync_results = {"success": 0, "failed": 0, "mapping_created": 0, "mapping_updated": 0}
    
    for user in okta_users:
        email = user.email
        okta_uid = user.okta_uid
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
        
        created = _upsert_pre_mapping(
            db,
            okta_uid=okta_uid,
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


def _upsert_pre_mapping(
    db: Session,
    okta_uid: str,
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
        premapped.okta_uid = okta_uid
        premapped.name = name
        return False
    
    else:
        new_entry = PreMappingBuffer(
            okta_uid=okta_uid,
            email=email,
            name=name,
            source_type=source_type,
            external_user_identifier=external_user_id,
            is_registered=False
        )
        add_new_mapping(db, new_entry)
        return True
