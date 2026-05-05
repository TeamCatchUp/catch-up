import type { ChannelTalkChannel, ChannelTalkDocumentSpace } from '../types/channelTalkModel';

/** 채널의 모든 secret(Access Key + Access Secret + Webhook Token)이 채워졌는지 — 화이트스페이스 제외 */
export function isChannelSecretsFilled(channel: ChannelTalkChannel): boolean {
  return Boolean(channel.accessKey.trim() && channel.accessSecret.trim() && channel.webhookToken.trim());
}

/** 도큐먼트 스페이스의 모든 secret(Access Key + Access Secret)이 채워졌는지 — Webhook Token 없음 */
export function isDocumentSpaceSecretsFilled(ds: ChannelTalkDocumentSpace): boolean {
  return Boolean(ds.accessKey.trim() && ds.accessSecret.trim());
}
