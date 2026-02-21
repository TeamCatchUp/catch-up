import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { integrationQueries } from '@/shared/queries/integration.queries';

import { INTEGRATION_ACCOUNTS } from '../constants/integrations';
import type {
  IntegrationService,
  MemberIntegrationCardItem,
  MemberIntegrationRow,
  MemberIntegrationStatus,
  MemberIntegrationViewModel,
} from '../types/integrations';
import { parseConnected } from '../utils/integrationParsers';

type ConnectorAccount = {
  id: string;
  name: string;
  email: string;
  picture?: string | null;
};

type ConnectorResponse = {
  jira?: ConnectorAccount[];
  github?: ConnectorAccount[];
  slack?: ConnectorAccount[];
};

const ALL_SERVICES: IntegrationService[] = ['jira', 'github', 'slack', 'confluence'];

/** 이용자 연동 탭에서 필요한 데이터를 기존 API 기반으로 조합 */
export const useMemberIntegrationViewModel = (): MemberIntegrationViewModel => {
  const { data: jiraStatus } = useQuery(integrationQueries.jira.status());
  const { data: slackStatus } = useQuery(integrationQueries.slack.status());
  const { data: githubInstallations } = useQuery(integrationQueries.github.installations());
  // TODO: 커넥터 계정 조회 API 백엔드 구현 후 연동
  const connectors: ConnectorResponse = {};

  const serviceConnected = useMemo<Record<IntegrationService, boolean>>(
    () => ({
      jira: parseConnected(jiraStatus, false),
      github: parseConnected(githubInstallations, false),
      slack: parseConnected(slackStatus, false),
      confluence: false,
    }),
    [jiraStatus, githubInstallations, slackStatus],
  );

  const rows = useMemo<MemberIntegrationRow[]>(() => {
    const userMap = new Map<string, MemberIntegrationRow>();
    const jiraAccounts = Array.isArray(connectors?.jira) ? connectors.jira : [];
    const githubAccounts = Array.isArray(connectors?.github) ? connectors.github : [];
    const slackAccounts = Array.isArray(connectors?.slack) ? connectors.slack : [];

    const putAccount = (service: 'jira' | 'github' | 'slack', account: ConnectorAccount) => {
      const key = account.email?.trim().toLowerCase() || `${account.name}:${account.id}`;
      const existing = userMap.get(key);

      if (existing) {
        existing.accountIdByService[service] = account.id;
        if (!existing.picture && account.picture) {
          existing.picture = account.picture;
        }
        return;
      }

      userMap.set(key, {
        userKey: key,
        userName: account.name,
        email: account.email || '-',
        phone: '-',
        department: '-',
        teamSizeLabel: '-',
        picture: account.picture ?? null,
        accountIdByService: { [service]: account.id },
        statusByService: {
          jira: '미등록',
          github: '미등록',
          slack: '미등록',
          confluence: '미사용',
        },
      });
    };

    jiraAccounts.forEach((account) => putAccount('jira', account));
    githubAccounts.forEach((account) => putAccount('github', account));
    slackAccounts.forEach((account) => putAccount('slack', account));

    return Array.from(userMap.values())
      .map((row) => {
        const statusByService = ALL_SERVICES.reduce<Record<IntegrationService, MemberIntegrationStatus>>(
          (acc, service) => {
            if (!serviceConnected[service]) {
              acc[service] = '미사용';
              return acc;
            }

            acc[service] = row.accountIdByService[service] ? '완료' : '미등록';
            return acc;
          },
          {
            jira: '미등록',
            github: '미등록',
            slack: '미등록',
            confluence: '미사용',
          },
        );

        return {
          ...row,
          statusByService,
        };
      })
      .sort((a, b) => a.userName.localeCompare(b.userName, 'ko'));
  }, [connectors, serviceConnected]);

  const cards = useMemo<MemberIntegrationCardItem[]>(
    () =>
      INTEGRATION_ACCOUNTS.map((account) => {
        const totalCount = rows.length;
        const completedCount = rows.filter((row) => row.statusByService[account.service] === '완료').length;
        const completionRate = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

        return {
          ...account,
          completedCount,
          totalCount,
          completionRate,
        };
      }),
    [rows],
  );

  return {
    cards,
    rows,
  };
};
