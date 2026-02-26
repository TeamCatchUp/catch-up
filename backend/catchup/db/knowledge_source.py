from sqlalchemy.orm import Session

from catchup.db.models import KnowledgeSource


def add_knowledge_source(
    db: Session,
    new_source: KnowledgeSource
) -> KnowledgeSource:
    db.add(new_source)
    return new_source
    