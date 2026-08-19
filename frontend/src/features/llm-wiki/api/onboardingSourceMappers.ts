import type { AutomationCredentialItem } from '@/shared/types/automationApi';

import type { ChannelTalkChannel, OnboardingChannelRow } from '../types/llmWikiOnboarding';

/** 연결된 채널톡 채널 하나. credential_id가 수집 설정 저장 경로의 키다. */
export function mapChannelTalkChannel(dto: AutomationCredentialItem): ChannelTalkChannel {
  return {
    credentialId: dto.credential_id,
    name: dto.display_name,
    externalId: dto.external_id,
    isConfigured: dto.is_configured,
  };
}

/** 온보딩 채널 표의 행. "최근 수정일"은 대응 필드가 없어 비운다. */
export function mapOnboardingChannelRows(dtos: readonly AutomationCredentialItem[]): OnboardingChannelRow[] {
  return dtos.map((dto) => ({ channel: mapChannelTalkChannel(dto), lastModifiedLabel: '' }));
}
