'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueries, useQueryClient } from '@tanstack/react-query';
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
const LOCAL_COMPLETED_KEY = 'catchup:embedding:completed';
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

/** 완료된 서비스 목록 (localStorage persist — 영구 유지) */
export const loadCompletedServices = (): Set<IntegrationService> => {
  try {
    const raw = localStorage.getItem(LOCAL_COMPLETED_KEY);
    return raw ? new Set(JSON.parse(raw) as IntegrationService[]) : new Set();
  } catch {
    return new Set();
  }
};

const saveCompletedServices = (services: Set<IntegrationService>) => {
  localStorage.setItem(LOCAL_COMPLETED_KEY, JSON.stringify([...services]));
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

  /** 완료된 서비스 (localStorage persist — 영구 유지) */
  const [completedServices, setCompletedServices] = useState<Set<IntegrationService>>(loadCompletedServices);

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
  // 폴링 데이터 변화 → 완료 전이 감지 → 상태 업데이트가 이 effect 내에서만 가능하므로 suppress

  const prevSyncingRef = useRef<Set<string>>(new Set());

  /* eslint-disable react-hooks/set-state-in-effect -- 폴링 완료 감지 후 상태 전이 (외부 시스템 구독 패턴) */
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
        setCompletedServices((prev) => {
          const next = new Set(prev).add(entry.service);
          saveCompletedServices(next);
          return next;
        });
        setCompletionModal({ open: true, serviceName: entry.serviceName });
        queryClient.invalidateQueries({ queryKey: adminConnectorQueries.all() });
      }
    }

    prevSyncingRef.current = nowSyncing;
  }, [syncStatusQueries, activeEntries, activeEmbeddings, queryClient]);
  /* eslint-enable react-hooks/set-state-in-effect */

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
   * 1. 폴링으로 완료 감지됨 → 'completed' (버튼 숨김)
   * 2. 활성 폴링 중 → 'syncing' (버튼 비활성화)
   * 3. 그 외 → 'idle' (버튼 표시)
   *
   * connector status latest는 사용하지 않음:
   * flush(동기화)로도 latest가 갱신되어 풀 임베딩 완료와 구분 불가
   */
  const getStatus = useCallback(
    (service: IntegrationService): EmbeddingState => {
      if (completedServices.has(service)) return 'completed';
      if (activeEmbeddings.has(service)) return 'syncing';
      return 'idle';
    },
    [completedServices, activeEmbeddings],
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
