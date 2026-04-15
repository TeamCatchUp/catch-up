from datetime import datetime
from datetime import timezone

REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS = 3.0
REDIS_SOCKET_TIMEOUT_SECONDS = 10.0
REDIS_STREAM_SOCKET_TIMEOUT_SECONDS = 15.0
REDIS_PING_TIMEOUT_SECONDS = 5.0
REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30

# 0.3.0 배포 전까지 LangGraph state reducer 버그로 인해
# 세션 내 토큰 사용량이 턴마다 누적 합산되는 과대 집계 문제가 있었음.
# (버그 수정 커밋: 55e9be19, 프로덕션 배포: 2026-04-15 KST)
# 이 시각 이전 데이터는 Rate Limiting 등 토큰 사용량 집계에서 제외하기 위해 도입
TOKEN_USAGE_RELIABLE_FROM = datetime(2026, 4, 14, 15, 0, 0, tzinfo=timezone.utc)
