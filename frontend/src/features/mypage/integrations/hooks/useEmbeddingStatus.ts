'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import type { IntegrationService } from '@/shared/types/integrationService';

import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type {
  ConfluenceSyncStatusItem,
  GithubSyncStatusResponse,
  JiraSyncStatusItem,
  SlackSyncStatusItem,
  SyncStatusValue,
} from '../types/api';

// ─── SessionStorage 키 / 유틸 ───

const STORAGE_KEY_PREFIX = 'catchup:embedding:';
const POLL_INTERVAL = 15_000; // 15초
const TIMEOUT_MS = 30 * 60_000; // 30분

interface StoredEmbedding {
  parentIds: string[];
  startedAt: number;
  serviceName: string;
}

const getStorageKey = (service: IntegrationService) => `${STORAGE_KEY_PREFIX}${service}`;

const loadStored = (service: IntegrationService): StoredEmbedding | null => {
  try {
    const raw = sessionStorage.getItem(getStorageKey(service));
    return raw ? (JSON.parse(raw) as StoredEmbedding) : null;
  } catch {
    return null;
  }
};

const saveStored = (service: IntegrationService, data: StoredEmbedding) => {
  sessionStorage.setItem(getStorageKey(service), JSON.stringify(data));
};

const removeStored = (service: IntegrationService) => {
  sessionStorage.removeItem(getStorageKey(service));
};

// ─── Sync Status → "진행 중?" 판별 ───

const ACTIVE_STATUSES: SyncStatusValue[] = ['pending', 'in_progress'];

const isGithubSyncing = (data: GithubSyncStatusResponse): boolean =>
  data.repositories.some((repo) =>
    Object.values(repo.entities).some(
      (e) => e.status != null && ACTIVE_STATUSES.includes(e.status as SyncStatusValue),
    ),
  );

const isServiceSyncing = (items: Array<{ last_sync_status: SyncStatusValue | null }>): boolean =>
  items.some((item) => item.last_sync_status != null && ACTIVE_STATUSES.includes(item.last_sync_status));

// ─── 타입 ───

export type EmbeddingState = 'idle' | 'syncing' | 'completed';

interface EmbeddingEntry {
  service: IntegrationService;
  parentIds: string[];
  serviceName: string;
  startedAt: number;
}

const ALL_SERVICES: IntegrationService[] = ['github', 'jira', 'slack', 'confluence'];

// ─── Hook ───

export const useEmbeddingStatus = () => {
  const queryClient = useQueryClient();

  // ─── Connector Status로 초기 완료 상태 판별 ───
  const { data: githubConnector } = useQuery(adminConnectorQueries.githubStatus());
  const { data: jiraConnector } = useQuery(adminConnectorQueries.jiraStatus());
  const { data: slackConnector } = useQuery(adminConnectorQueries.slackStatus());
  const { data: confluenceConnector } = useQuery(adminConnectorQueries.confluenceStatus());

  /** connector status의 latest 필드로 "임베딩 완료 여부" 판별 */
  const connectorSynced = new Set<IntegrationService>();
  if (githubConnector?.latest) connectorSynced.add('github');
  if (jiraConnector?.latest) connectorSynced.add('jira');
  if (slackConnector?.latest) connectorSynced.add('slack');
  if (confluenceConnector?.latest) connectorSynced.add('confluence');

  // ─── 활성 임베딩 (sessionStorage 복원) ───

  const [activeEmbeddings, setActiveEmbeddings] = useState<Map<IntegrationService, EmbeddingEntry>>(() => {
    const initial = new Map<IntegrationService, EmbeddingEntry>();
    for (const service of ALL_SERVICES) {
      const stored = loadStored(service);
      if (stored && Date.now() - stored.startedAt < TIMEOUT_MS) {
        initial.set(service, { service, ...stored });
      } else if (stored) {
        removeStored(service);
      }
    }
    return initial;
  });

  /** 폴링으로 감지된 완료 (세션 내 상태) */
  const [justCompleted, setJustCompleted] = useState<Set<IntegrationService>>(new Set());

  /** 완료 모달 */
  const [completionModal, setCompletionModal] = useState<{
    open: boolean;
    serviceName: string;
  }>({ open: false, serviceName: '' });

  // ─── Sync Status 폴링 (활성 임베딩만) ───

  const activeEntries = Array.from(activeEmbeddings.values());

  const syncStatusQueries = useQueries({
    queries: activeEntries.flatMap((entry) =>
      entry.parentIds.map((parentId) => {
        const base = (() => {
          switch (entry.service) {
            case 'github':
              return adminConnectorQueries.githubSyncStatus(parentId);
            case 'jira':
              return adminConnectorQueries.jiraSyncStatus(parentId);
            case 'slack':
              return adminConnectorQueries.slackSyncStatus(parentId);
            case 'confluence':
              return adminConnectorQueries.confluenceSyncStatus(parentId);
          }
        })();
        return {
          ...base,
          refetchInterval: POLL_INTERVAL,
        };
      }),
    ),
  });

  // ─── 폴링 결과로 완료 감지 ───

  const prevSyncingRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (activeEntries.length === 0) return;

    let queryIdx = 0;
    const nowSyncing = new Set<string>();

    for (const entry of activeEntries) {
      let serviceStillSyncing = false;

      for (let i = 0; i < entry.parentIds.length; i++) {
        const query = syncStatusQueries[queryIdx + i];
        if (!query || query.isLoading || !query.data) {
          serviceStillSyncing = true;
          continue;
        }

        const data = query.data;
        const syncing =
          entry.service === 'github'
            ? isGithubSyncing(data as GithubSyncStatusResponse)
            : isServiceSyncing(
                data as (JiraSyncStatusItem | SlackSyncStatusItem | ConfluenceSyncStatusItem)[],
              );

        if (syncing) serviceStillSyncing = true;
      }

      queryIdx += entry.parentIds.length;

      if (serviceStillSyncing) {
        nowSyncing.add(entry.service);
      }
    }

    for (const entry of activeEntries) {
      const wasSyncing = prevSyncingRef.current.has(entry.service) || activeEmbeddings.has(entry.service);
      const isNowSyncing = nowSyncing.has(entry.service);

      if (wasSyncing && !isNowSyncing) {
        removeStored(entry.service);
        setActiveEmbeddings((prev) => {
          const next = new Map(prev);
          next.delete(entry.service);
          return next;
        });
        setJustCompleted((prev) => new Set(prev).add(entry.service));
        setCompletionModal({ open: true, serviceName: entry.serviceName });

        // connector status 등 관련 쿼리 무효화 → latest 갱신
        queryClient.invalidateQueries({ queryKey: adminConnectorQueries.all() });
      }
    }

    prevSyncingRef.current = nowSyncing;
  }, [syncStatusQueries, activeEntries, activeEmbeddings, queryClient]);

  // ─── 타임아웃 ───

  useEffect(() => {
    if (activeEmbeddings.size === 0) return;

    const interval = setInterval(() => {
      const now = Date.now();
      for (const [service, entry] of activeEmbeddings) {
        if (now - entry.startedAt >= TIMEOUT_MS) {
          removeStored(service);
          setActiveEmbeddings((prev) => {
            const next = new Map(prev);
            next.delete(service);
            return next;
          });
          toast.error(`${entry.serviceName} 임베딩 상태를 확인할 수 없습니다.`);
        }
      }
    }, 60_000);

    return () => clearInterval(interval);
  }, [activeEmbeddings]);

  // ─── Public API ───

  const startEmbedding = useCallback(
    (service: IntegrationService, parentIds: string[], serviceName: string) => {
      const entry: EmbeddingEntry = { service, parentIds, serviceName, startedAt: Date.now() };
      saveStored(service, { parentIds, startedAt: entry.startedAt, serviceName });
      setActiveEmbeddings((prev) => new Map(prev).set(service, entry));
    },
    [],
  );

  /**
   * 서비스별 임베딩 상태:
   * 1. 폴링으로 방금 완료됨 → 'completed'
   * 2. 활성 폴링 중 → 'syncing'
   * 3. connector status latest가 존재 → 'completed' (이전에 임베딩 완료)
   * 4. 그 외 → 'idle'
   */
  const getStatus = useCallback(
    (service: IntegrationService): EmbeddingState => {
      if (justCompleted.has(service)) return 'completed';
      if (activeEmbeddings.has(service)) return 'syncing';
      if (connectorSynced.has(service)) return 'completed';
      return 'idle';
    },
    [justCompleted, activeEmbeddings, connectorSynced],
  );

  const closeCompletionModal = useCallback(() => {
    setCompletionModal({ open: false, serviceName: '' });
  }, []);

  return {
    startEmbedding,
    getStatus,
    completionModal,
    closeCompletionModal,
  };
};
