/** 온보딩 제출 요청 함수. 응답은 서버 DTO 그대로 돌려준다. */

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  KnowledgeMaintenanceSettingDto,
  KnowledgeMaintenanceSettingRequest,
  WikiChannelOnboardingDto,
  WikiChannelOnboardingRequest,
} from './onboardingDto';

/** 채널·정의·kind별 폴더가 한 번에 만들어진다. 이름 중복은 409다. */
export async function createWikiChannelByOnboarding(
  body: WikiChannelOnboardingRequest,
): Promise<WikiChannelOnboardingDto> {
  const res = await api.post<WikiChannelOnboardingDto>(API.wiki.channelsOnboarding, body);
  return res.data;
}

/** 수집 설정은 채널톡 credential 단위로 저장된다 — 채널이 여럿이면 그 수만큼 호출한다. */
export async function updateKnowledgeMaintenanceSetting(
  credentialId: number,
  body: KnowledgeMaintenanceSettingRequest,
): Promise<KnowledgeMaintenanceSettingDto> {
  const res = await api.put<KnowledgeMaintenanceSettingDto>(API.wiki.knowledgeMaintenanceSettings(credentialId), body);
  return res.data;
}
