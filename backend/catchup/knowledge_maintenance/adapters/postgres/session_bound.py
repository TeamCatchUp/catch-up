"""이미 열려 있는 세션 위에 어휘 저장소만 얹는다."""

from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyOntologyRepository,
)


class SessionBoundOntologyUnitOfWork:
    """이미 열려 있는 세션 위에 어휘 저장소만 얹는다.

    `KnowledgeMaintenanceUnitOfWork`는 세션을 직접 열고 빠져나갈 때
    닫는다. 요청 세션은 그 생애를 웹 프레임워크가 쥐고 있어 같은 규약을
    쓸 수 없으므로, 여는 일도 닫는 일도 하지 않는 얇은 자리를 따로 둔다.
    commit이 없는 것이 요점이다 — 채널·정의·어휘를 한 트랜잭션으로 묶는
    호출자가 커밋 시점을 정한다.

    어휘 저장소만 싣는다. 다른 저장소를 얹으면 서버가 이 자리를 통해
    knowledge maintenance 전체를 세션째 만질 수 있게 된다.
    """

    def __init__(self, session: Session) -> None:
        self.ontology = SqlAlchemyOntologyRepository(session)
