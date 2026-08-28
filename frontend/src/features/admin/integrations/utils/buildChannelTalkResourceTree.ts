import type { ConnectorResource } from '../types/integrationModel';
import type { AdminConnectorTargetRangeResponse } from '../types/syncModel';
import { formatEmbeddingRange } from './embeddingUtils';

/**
 * 채널톡 target을 채널 → 도큐먼트 스페이스 2단으로 묶는다.
 *
 * `GET /admin/connector/status?source=channel_talk` 는 평면 배열을 주지만
 * 계층 단서를 두 개 갖고 있다 — `scope_id`가 채널 id이고(임베딩 요청도
 * `scope_id: channel.channel_id`로 나간다), `target_type`이 `channel`/`space`다.
 * 실측 응답:
 *
 * ```
 * scope=229395 type=space   id=16957  Catch Up Guide
 * scope=229395 type=channel id=229395 Catch Up | 캐치업
 * scope=229395 type=space   id=18234  도큐먼트 스페이스 2
 * ```
 *
 * 채널이 space보다 뒤에 올 수 있으므로 순서에 기대지 않고 두 번 훑는다.
 * 채널의 등장 순서는 그 scope의 **첫 target** 위치로 정한다 — 응답 순서를
 * 그대로 유지해야 새로고침마다 줄이 튀지 않는다.
 *
 * `target_type`은 선택 필드다(구 응답엔 없다). 없으면 `target_id === scope_id`
 * 인 것을 채널로 본다 — 실측에서 채널의 두 값이 같았다.
 *
 * 채널 target 없이 space만 온 scope는 채널명을 알 수 없다. 이름을 지어내지 않고
 * 그 space들을 최상위 줄로 올린다 — 묶을 근거가 없다고 해서 목록에서 빠지면
 * 임베딩된 대상이 화면에서 사라진다.
 */
export const buildChannelTalkResourceTree = (
  targets: readonly AdminConnectorTargetRangeResponse[],
): ConnectorResource[] => {
  const toResource = (t: AdminConnectorTargetRangeResponse): ConnectorResource => ({
    // scope를 붙이는 이유: space id는 scope 안에서만 유일하다고 보는 게 안전하다
    id: `${t.scope_id}-${t.target_id}`,
    name: t.target_name,
    dateRange: formatEmbeddingRange(t.oldest, t.latest),
  });

  const isChannel = (t: AdminConnectorTargetRangeResponse) =>
    t.target_type ? t.target_type === 'channel' : t.target_id === t.scope_id;

  // 1) scope 등장 순서 고정 + 채널 target 찾기
  const scopeOrder: string[] = [];
  const channelByScope = new Map<string, AdminConnectorTargetRangeResponse>();
  for (const target of targets) {
    if (!scopeOrder.includes(target.scope_id)) scopeOrder.push(target.scope_id);
    if (isChannel(target)) channelByScope.set(target.scope_id, target);
  }

  // 2) space를 scope별로 모은다
  const spacesByScope = new Map<string, AdminConnectorTargetRangeResponse[]>();
  for (const target of targets) {
    if (isChannel(target)) continue;
    const list = spacesByScope.get(target.scope_id);
    if (list) list.push(target);
    else spacesByScope.set(target.scope_id, [target]);
  }

  return scopeOrder.flatMap((scopeId) => {
    const spaces = spacesByScope.get(scopeId) ?? [];
    const channel = channelByScope.get(scopeId);
    if (!channel) return spaces.map(toResource);
    return [{ ...toResource(channel), children: spaces.map(toResource) }];
  });
};
