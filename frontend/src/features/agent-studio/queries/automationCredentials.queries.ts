import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  AutomationConnector,
  AutomationCredentialsResponse,
  AutomationTargetsResponse,
} from '../types/automationApi';

export const automationCredentialsQueries = {
  all: () => ['agent-studio', 'automation-credentials'] as const,

  credentials: (connector: AutomationConnector) =>
    queryOptions({
      queryKey: [...automationCredentialsQueries.all(), connector] as const,
      queryFn: async (): Promise<AutomationCredentialsResponse> => {
        const res = await api.get<AutomationCredentialsResponse>(API.automations.credentials, {
          params: { connector },
        });
        return res.data;
      },
    }),

  targets: (connector: AutomationConnector, credentialId?: number) =>
    queryOptions({
      queryKey: [...automationCredentialsQueries.all(), connector, 'targets', credentialId] as const,
      queryFn: async (): Promise<AutomationTargetsResponse> => {
        const params =
          credentialId === undefined
            ? { connector }
            : {
                connector,
                credential_id: credentialId,
              };
        const res = await api.get<AutomationTargetsResponse>(API.automations.targets, {
          params,
        });
        return res.data;
      },
      enabled: connector === 'channel_talk' || credentialId !== undefined,
    }),
};
