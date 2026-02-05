/**
 * RagPage Context
 * 하위 컴포넌트 간 상태 공유를 위한 Context Provider
 * Compound Component 패턴의 핵심 - 모든 상태를 중앙에서 관리
 */

'use client';

import {
  createContext,
  useContext,
  useRef,
  useState,
  useMemo,
  useCallback,
  type PropsWithChildren,
} from 'react';
import useRagChat from '@/hooks/ragAnswer/useRagChat';
import useRagPagination from '@/hooks/ragAnswer/useRagPagination';
import useRagFilters from '@/hooks/ragAnswer/useRagFilters';
import useWheelNavigation from '@/hooks/common/useWheelNavigation';
import { TEAM_SPACES, type TeamSpace } from '@/constants/ragAnswer/config';

/** Context Value 타입 정의 */
interface RagPageContextValue {
  sessionId: string;
  chat: ReturnType<typeof useRagChat>;
  pagination: ReturnType<typeof useRagPagination>;
  filters: ReturnType<typeof useRagFilters>;
  refs: {
    scroll: React.RefObject<HTMLDivElement | null>;
    answerScroll: React.RefObject<HTMLDivElement | null>;
    feedback: React.RefObject<HTMLDivElement | null>;
    textArea: React.RefObject<HTMLTextAreaElement | null>;
  };
  ui: {
    editingMessageId: string | null;
    setEditingMessageId: (id: string | null) => void;
    feedbackVisibleMap: Record<string, boolean>;
    setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
    filterOpenMap: Record<string, boolean>;
    setFilterOpenMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
    spaceDropDownOpenMap: Record<string, boolean>;
    toggleSpaceDropdown: (answerId: string) => void;
    closeSpaceDropdown: (answerId: string) => void;
    selectedTeamSpace: TeamSpace;
    setSelectedTeamSpaceId: (id: string) => void;
    activeTab: 'source' | 'detail';
    setActiveTab: React.Dispatch<React.SetStateAction<'source' | 'detail'>>;
    newInput: string;
    setNewInput: (value: string) => void;
    isMultiLine: boolean;
    setIsMultiLine: (value: boolean) => void;
  };
}

const RagPageContext = createContext<RagPageContextValue | null>(null);

/** Context 접근 훅 */
export const useRagPageContext = () => {
  const context = useContext(RagPageContext);
  if (!context) {
    throw new Error('useRagPageContext must be used within RagPage.Provider');
  }
  return context;
};

/** Provider Props */
interface RagPageProviderProps extends PropsWithChildren {
  sessionId: string;
  repo?: string | null;
  initialQuery?: string | null;
}

/** Context Provider - 모든 상태와 로직을 하위 컴포넌트에 제공 */
export const RagPageProvider = ({
  sessionId,
  repo,
  initialQuery,
  children,
}: RagPageProviderProps) => {
  // Refs
  const scrollRef = useRef<HTMLDivElement>(null);
  const answerScrollRef = useRef<HTMLDivElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  // 커스텀 훅 - 핵심 비즈니스 로직
  const chat = useRagChat({
    sessionId,
    repo: repo ?? null,
    initialQuery: initialQuery ?? null,
  });

  const pagination = useRagPagination({
    sessionId,
    messages: chat.chatData?.messages ?? [],
    isLoading: chat.isLoading,
  });

  const filters = useRagFilters();

  // 휠 네비게이션 (사이드 이펙트 전용)
  useWheelNavigation({
    containerRef: scrollRef,
    excludeRefs: [answerScrollRef, feedbackRef],
    totalPages: pagination.qaPairs.length,
    currentPage: pagination.currentPage,
    disabled: chat.isLoading,
    onPageChange: pagination.setCurrentPage,
    onSlideDirectionChange: pagination.setSlideDirection,
  });

  // UI 상태
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<Record<string, boolean>>({});
  const [filterOpenMap, setFilterOpenMap] = useState<Record<string, boolean>>({});
  const [spaceDropDownOpenMap, setSpaceDropDownOpenMap] = useState<Record<string, boolean>>({});
  const [selectedTeamSpaceId, setSelectedTeamSpaceId] = useState<string>(TEAM_SPACES[0].id);

  const selectedTeamSpace = useMemo(
    () => TEAM_SPACES.find((t) => t.id === selectedTeamSpaceId) ?? TEAM_SPACES[0],
    [selectedTeamSpaceId],
  );

  const toggleSpaceDropdown = useCallback((answerId: string) => {
    setSpaceDropDownOpenMap((prev) => {
      const nextOpen = !prev?.[answerId];
      return nextOpen ? { [answerId]: true } : {};
    });
  }, []);

  const closeSpaceDropdown = useCallback((answerId: string) => {
    setSpaceDropDownOpenMap((prev) => {
      if (!prev?.[answerId]) return prev;
      const copied = { ...prev };
      delete copied[answerId];
      return copied;
    });
  }, []);

  const [activeTab, setActiveTab] = useState<'source' | 'detail'>('source');
  const [newInput, setNewInput] = useState('');
  const [isMultiLine, setIsMultiLine] = useState(false);

  // 메모이제이션 - 불필요한 리렌더링 방지
  const refs = useMemo(
    () => ({
      scroll: scrollRef,
      answerScroll: answerScrollRef,
      feedback: feedbackRef,
      textArea: textAreaRef,
    }),
    [],
  );

  const ui = useMemo(
    () => ({
      editingMessageId,
      setEditingMessageId,
      feedbackVisibleMap,
      setFeedbackVisibleMap,
      filterOpenMap,
      setFilterOpenMap,
      spaceDropDownOpenMap,
      toggleSpaceDropdown,
      closeSpaceDropdown,
      selectedTeamSpace,
      setSelectedTeamSpaceId,
      activeTab,
      setActiveTab,
      newInput,
      setNewInput,
      isMultiLine,
      setIsMultiLine,
    }),
    [
      editingMessageId,
      feedbackVisibleMap,
      filterOpenMap,
      spaceDropDownOpenMap,
      toggleSpaceDropdown,
      closeSpaceDropdown,
      selectedTeamSpace,
      activeTab,
      newInput,
      isMultiLine,
    ],
  );

  const value: RagPageContextValue = useMemo(
    () => ({ sessionId, chat, pagination, filters, refs, ui }),
    [sessionId, chat, pagination, filters, refs, ui],
  );

  return (
    <RagPageContext.Provider value={value}>
      {children}
    </RagPageContext.Provider>
  );
};

export default RagPageContext;
