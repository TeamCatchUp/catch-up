import type { ChannelTalkChannel, ChannelTalkDocumentSpace } from '../types/channelTalkModel';

// 채널 secret(key + secret + webhook) 모두 채워졌는지 (whitespace 제외)
export function isChannelSecretsFilled(channel: ChannelTalkChannel): boolean {
  return Boolean(channel.accessKey.trim() && channel.accessSecret.trim() && channel.webhookToken.trim());
}

// 도큐먼트 스페이스 secret(key + secret) 모두 채워졌는지 — webhook 불요
export function isDocumentSpaceSecretsFilled(ds: ChannelTalkDocumentSpace): boolean {
  return Boolean(ds.accessKey.trim() && ds.accessSecret.trim());
}
