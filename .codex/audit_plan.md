## **0) 목적**

- **구조화(JSON) 로그**를 표준 스키마로 남긴다.
- FastAPI 환경에서 **공통 컨텍스트(service/env/version/trace_id/actor)** 를 자동 주입한다.
- AUTH | INTEGRATION | SYNC | CHAT 이벤트를 **상황별 유틸 함수(도메인 로거)** 로 제공해, 호출부가 스키마를 직접 조립하지 않게 한다.
- **필드명 일관성**, **metadata 사이즈 제한**을 중앙에서 강제한다.

---

## **1) 로그 스키마 (표준)**

### **공통 필드 (모든 이벤트에 포함)**

- timestamp (ISO8601, UTC)
- level (INFO|WARNING|ERROR|...)
- version (예: 1.0.0)
- trace_id (요청 단위 추적 ID)
- event_type (AUTH|INTEGRATION|SYNC|CHAT)
- event_action (각 타입별 액션)
- actor (dict) (User or System)
    - user_id (nullable)
    - email (nullable)
    - role (nullable)
    - department (nullable)
- workspace_id (nullable)
- metadata (dict, 이벤트별 추가 정보)

> **주의**: metadata 내부에 토큰/비밀키/원문 Access Token/Refresh Token 절대 금지.
> 

---

## **2) 구현 범위 (What to build)**

### **A. Logging Config 모듈**

- structlog + stdlib logging 통합 구성
- JSON 출력
- contextvars 병합
- timestamp/level 추가
- exception stack 출력

### **B. FastAPI Middleware**

- 요청 시작 시 trace_id 생성/추출하여 contextvars bind
- 가능하면 X-Request-Id 헤더를 존중하고, 없으면 생성
- (선택) 응답 헤더로 X-Request-Id를 내려준다

### **C. 도메인별 유틸(이벤트 로거)**

- audit/auth.py, audit/integration.py, audit/sync.py, audit/chat.py
- 각 함수는 표준 필드 구조를 지키고, 호출자는 “값만” 넘기도록 설계
- event_type, event_action은 Enum/상수로 강제

### **D. 테스트**

- 이벤트 유틸 함수가 생성한 payload의 스키마/필수필드/마스킹/크기제한을 단위 테스트로 검증

---

## **3) 권장 파일 구조**

```python
app/
  logging/
    __init__.py
    config.py              # structlog + logging 설정
    processors.py          # 마스킹/필드정리/크기제한 등 processor 모음
    context.py             # contextvars bind helpers
    enums.py               # EventType, EventAction 상수/Enum
    schema.py              # (선택) Pydantic 모델로 이벤트 스키마 정의
  audit/
    __init__.py
    base.py                # 공통 emit(), actor/workspace helper
    auth.py
    integration.py
    sync.py
    chat.py
  middleware/
    request_context.py     # trace_id/workspace/actor bind
  main.py
```

---

## **4) Logging Config 요구사항 (구현 체크리스트)**

### **4.1 structlog.configure 필수 processor 체인**

- merge_contextvars : async 환경에서 요청별 컨텍스트가 섞이지 않게
- TimeStamper(fmt="iso", utc=True)
- add_log_level
- format_exc_info (+ StackInfoRenderer() optional)
- **custom processors**
    - sanitize_secrets_processor : token/password/authorization 등 제거
    - mask_pii_processor : 이메일/IP 등 마스킹(정책 기반)
    - truncate_large_fields_processor : user_agent/error_summary 등 길이 제한
    - ensure_required_fields_processor : service/environment/version 등 누락 시 기본값/보정
- JSONRenderer()

### **4.2 stdlib logging 통합**

- logging.basicConfig(format="%(message)s", level=...)
- structlog logger_factory: structlog.stdlib.LoggerFactory()

### **4.3 환경변수/설정값**

- SERVICE_NAME
- ENVIRONMENT
- APP_VERSION
- LOG_LEVEL

---

## **5) Middleware 설계 (요청 컨텍스트 자동 주입)**

### **해야 할 일**

- 요청마다 trace_id bind
    - 헤더 우선순위: X-Request-Id 또는 X-Amzn-Trace-Id(있다면 파싱/보존) → 없으면 uuid 생성
- (가능하면) 인증 후 actor bind (user_id/email/role/department)
- workspace_id는 라우팅/토큰/헤더에서 추출 가능하면 bind

### **바인딩 키 표준**

- trace_id
- service
- version
- environment
- workspace_id
- actor (dict)

---

## **6) 도메인 이벤트 유틸 설계 원칙**

### **원칙**

1. 호출부는 **dict 조립 금지**: 유틸 함수가 스키마를 만든다
2. event_type은 모듈이 고정, event_action은 Enum/상수로 강제
3. metadata 키 네이밍은 **snake_case**로 통일
4. PII/비밀정보는 유틸에서 **받더라도** processor에서 최종 필터링되게(이중 안전장치)
5. actor.email은 raw 저장하지 말고 마스킹/해시 저장 정책 선택

### **공통 emit 함수 (audit/base.py)**

- 입력: event_type, event_action, actor, workspace_id, metadata, level
- 내부: structlog logger 호출 logger.info(event_action, event_type=..., event_action=..., actor=..., workspace_id=..., metadata=...)
- timestamp/level/service/env/version/trace_id는 processor/contextvars에서 붙도록 설계

---

## **7) 이벤트별 유틸 함수 목록 (MVP)**

### **AUTH (audit/auth.py)**

- login_attempt(email, provider, result, failure_reason, ip_address, user_agent, token_issued, is_new_user, user_status)
- token_refresh(user_id, email, result, failure_reason, ...)
- logout(user_id, email, ...)

### **INTEGRATION (audit/integration.py)**

- oauth_connect(user_id, email, connector, result, scopes_granted, organization, repositories_count, webhook_registered, failure_reason)
- oauth_disconnect(...)
- oauth_refresh(...)
- webhook_register(...)
- connector_health_check(connector, result, details, failure_reason)

### **SYNC (audit/sync.py)**

- full_sync(connector, sync_type, trigger, resource_type, result, counts, duration_ms, embedding, error_summary)
- incremental_sync(...)
- sync_failure(connector, error_summary, failure_reason, ...)
- schema_drift_detected(connector, resource_type, diff_summary, ...)
- embedding_batch(model, vectors_generated, batch_size, duration_ms, ...)

### **CHAT (audit/chat.py)**

- message_sent(session_id, query_type, rag_pipeline, llm, connectors_searched, citations_count, duration_ms)
- (선택) message_failed(session_id, failure_reason, latency_ms, ...)

---

## **8) 마스킹/삭제 정책 (Processor에서 강제)**

### **반드시 삭제해야 하는 키(어디에 있든)**

- password, passphrase
- authorization, cookie, set-cookie
- access_token, refresh_token, id_token, token
- client_secret, api_key, secret, private_key

### **마스킹 권장**

- actor.email: u***@company.com 형태 또는 SHA256 해시(정책 선택)
- metadata.ip_address: 마지막 옥텟 마스킹(예: 203.0.113.xxx)
- user_agent: 너무 길면 truncate (예: 256~512 chars)

---

## **9) 크기 제한 정책 (추천)**

- metadata 전체 JSON 직렬화 길이 제한 (예: 8KB~32KB)
- 초과 시:
    - 긴 문자열 필드 truncate
    - 배열 길이 제한 (예: nodes_executed 최대 50)
    - error_summary 최대 1KB
- 제한 발생 시 metadata._truncated = true 같은 내부 플래그 추가 가능(선택)

---

## **10) 호출부 예시 (의도한 사용 형태)**

- 라우터/서비스 계층에서:
    - audit.auth.login_attempt(...)
    - audit.integration.oauth_connect(...)
    - audit.sync.full_sync(...)
    - audit.chat.message_sent(...)

호출부는 “값만” 넘기고, 스키마는 유틸이 책임진다.

---

## **11) 로깅 레벨 가이드**

- INFO: 정상 흐름의 감사/추적 이벤트 (login_attempt, oauth_connect, full_sync, message_sent)
- WARNING: 부분 성공/재시도/레이트리밋 등
- ERROR: 실패 + 예외 발생
- logger.exception(...): stacktrace 포함이 필요한 치명 오류

---

## **12) 품질 보장 (테스트 항목)**

1. 모든 이벤트에 event_type/event_action/metadata 존재
2. contextvars bind 후 로그에 trace_id/service/environment/version 자동 포함
3. email/ip/token 등 마스킹/삭제 정상 동작
4. metadata 크기 제한 동작
5. Enum 외 event_action 입력 불가(또는 경고/강제 변환)

---

## **13) 완료 기준 (Acceptance Criteria)**

- 앱 실행 시 structlog JSON 로그가 출력됨
- 요청마다 trace_id가 붙고 응답 헤더로도 내려감(선택)
- AUTH/INTEGRATION/SYNC/CHAT 유틸 함수로 로그를 남길 수 있음
- 토큰/비밀값은 어떤 경로로 들어와도 로그에 남지 않음
- 최소 5개 이상의 단위 테스트로 스키마/마스킹/크기 제한 검증

---

## **14) 구현 우선순위 (Recommended Order)**

1. app/logging/config.py + processors.py로 JSON 로깅 완성
2. middleware/request_context.py로 trace_id bind
3. audit/base.py + 4개 도메인(auth/integration/sync/chat) 유틸 구축
4. 마스킹/크기 제한 고도화
5. 테스트 추가 및 운영 레벨 튜닝(LOG_LEVEL/샘플링 등)

---

## **15) 추가 메모 (운영 팁)**

- “로그를 파일로 직접 쓰기”보다 **stdout JSON** → 런타임(EC2/systemd/docker)에서 수집 → S3/OpenSearch 적재가 단순하고 안전함
- 감사로그는 **안정성/일관성**이 최우선: 스키마가 흔들리면 검색/탐지 룰이 깨짐

---

### **Codex 작업 요청 요약 (한 줄)**

> “FastAPI + structlog JSON 로깅 설정을 만들고, 요청 컨텍스트(trace_id/actor/workspace)를 자동 주입하며, AUTH/INTEGRATION/SYNC/CHAT 이벤트를 표준 스키마로 남기는 도메인별 audit 유틸 함수를 구현하고, 마스킹/크기 제한/필수필드 보정을 processor로 강제해라.”
>