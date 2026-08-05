/**
 * sync target의 프론트 식별 키.
 *
 * 백엔드는 target 유일성을 `(scope_id, target_type, target_id)` 3-튜플로 정의한다 —
 * 채널톡은 channel-123과 space-123처럼 id가 같아도 target_type이 다르면 다른 리소스다.
 * target_id만으로 키를 만들면 이 경우 행 충돌·오조준 재시도가 일어난다.
 * target_type이 없는 커넥터(채널톡 외)는 빈 세그먼트로 통일한다.
 */
export const syncTargetKey = (item: { scope_id: string; target_id: string; target_type?: string }): string =>
  `${item.scope_id}:${item.target_type ?? ''}:${item.target_id}`;
