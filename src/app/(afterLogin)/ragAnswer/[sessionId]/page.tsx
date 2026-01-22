'use client';

import clsx from 'clsx';
import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import Add from '/public/icons/icon/add_small.svg';
import Share from '/public/icons/icon/share_2.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';
import EditPencil from '/public/icons/icon/edit_pencil.svg';
import Divider from '/public/icons/icon/divider.svg';
import DropDown from '/public/icons/icon/dropdown_down.svg';
import ToggleOff from '/public/icons/icon/state=Off.svg';
import ArrowSend from '/public/icons/icon/arrow_send.svg';
import Stop from '/public/icons/icon/stop.svg';
import Copy from '/public/icons/icon/copy.svg';
import ThumbsDown from '/public/icons/icon/thumbs-down.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import Filter from '/public/icons/icon/filter-2.svg';

import FilterComponent from '@/components/rag/answerComponent/Filter';
import RagContentHeader from '@/components/rag/answerComponent/RagContentHeader';
import RagRightAdditionalHeader from '@/components/rag/rightComponent/sourceComponent/RagRightAdditionalHeader';
import SourceComponent from '@/components/rag/rightComponent/sourceComponent/SourceComponent';
import DetailedTasksComponent from '@/components/rag/rightComponent/detailedTasksComponent/DetailedTasksComponent';
import AnswerActionButtons from '@/components/rag/answerComponent/AnswerActionButtons';
import FeedbackSection from '@/components/rag/answerComponent/FeedbackSection';
import RagAnswerSkeleton from '@/components/Skeleton/RagAnswerSkeleton';
import ErrorResponse from '@/components/rag/answerComponent/ErrorResponse';
import EditMessageInput from '@/components/rag/EditMessageInput';
import ToolTip from '@/components/common/ToolTip';
import TeamSpaceModal from '@/components/rag/modal/TeamSpaceModal';
import GithubPRStepSkeleton from '@/components/Skeleton/GithubPRStepSkeleton';

import { useParams, useSearchParams } from 'next/navigation';
import { createSSEConection, sendChatQuery, resumeChatQuery } from 'src/util/sendChatQuery';
import { normalizeSources } from '@/util/normalizeRagSources';
import { normalizeRelatedJiraIssues } from '@/util/normalizeRelatedJiraIssues';

const icon = [
  { name: 'Copy', icon: Copy },
  { name: 'Share', icon: Share },
  { name: 'ThumbsDown', icon: ThumbsDown },
  { name: 'Rotate', icon: Rotate },
  { name: 'Kebeb', icon: Kebeb },
];

// 백엔드 노드 -> UI 단계 매핑
const NODE_TO_UI_STEP: Record<string, RagUIStepKey | null> = {
  router: 'router',
  rewrite: 'router',
  plan: 'retrieve',
  retrieve: 'retrieve',
  rerank: 'rerank',
  manage_pr_context: null,
  grade: 'grade',
  generate: 'generate',
  chitchat: 'generate',
};

// test 하드코딩
const HARD_CODED_INDEX_LIST = ['CatchUp_BE_develop_code', 'CatchUp_BE_develop_pr', 'cu_jira_issue'] as const;

export default function Page() {
  const params = useParams();
  const searchParams = useSearchParams();

  const sessionId = params.sessionId as string;
  const repo = searchParams.get('repo');
  const initialQuery = searchParams.get('q');

  const [chatData, setChatData] = useState<ChatData | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const processingDoneRef = useRef(false); // RAG_DONE 중복 방지

  const [currentStep, setCurrentStep] = useState<RagUIStepKey>('router');
  const [prList, setPrList] = useState<PRPayload[]>([]);
  const [showPRSelection, setShowPRSelection] = useState(false);

  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);

  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<Record<string, boolean>>({});
  const [feedbackSubmittedMap, setFeedbackSubmittedMap] = useState<Record<string, boolean>>({});

  const [filterOpenMap, setFilterOpenMap] = useState<Record<string, boolean>>({});
  const [spaceDropDownOpenMap, setSpaceDropDownOpenMap] = useState<Record<string, boolean>>({});

  const [activeTab, setActiveTab] = useState<'source' | 'detail'>('source');
  const [newInput, setNewInput] = useState('');
  const [isMultiLine, setIsMultiLine] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const sseRef = useRef<EventSource | null>(null);
  const [sseReady, setSseReady] = useState(false);

  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');

  const formatMarkdownString = (text: string) => {
    return text
      .replace(/\\n/g, '\n')
      .replace(/([^\n])\n(#{1,6}\s)/g, '$1\n\n$2')
      .replace(/([^\n])\n(\d+\.\s)/g, '$1\n\n$2')
      .replace(/([^\n])\n([-*+]\s)/g, '$1\n\n$2')
      .replace(/([^\n])\n(-\s\[[x\s]\]\s)/g, '$1\n\n$2')
      .replace(/([^\n])\n(```)/g, '$1\n\n$2')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  };

  const beginAnswerLoading = useCallback(() => {
    setIsLoading(true);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');
    processingDoneRef.current = false; // RAG_DONE 플래그 초기화
  }, []);

  const appendAssistantAnswer = useCallback(
    (answer: string, sources: BackendSource[] = [], relatedJiraIssues: BackendSource[] = []) => {
      setChatData((prev) => {
        if (!prev) return prev;

        // 중복 체크: 마지막 메시지가 동일한 내용이면 무시
        const lastMessage = prev.messages[prev.messages.length - 1];
        if (lastMessage?.role === 'assistant' && lastMessage?.content === answer) {
          console.warn('[appendAssistantAnswer] 중복 답변 무시');
          return prev;
        }

        const uiSources = normalizeSources(sources);
        const detailedTasks = normalizeRelatedJiraIssues(relatedJiraIssues);

        const assistantMessage: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: answer,
          sources: uiSources,
          detailedTasks,
          timestamp: new Date().toISOString(),
        };

        const finalData: ChatData = {
          ...prev,
          messages: [...prev.messages, assistantMessage],
        };

        localStorage.setItem(`chat_${sessionId}`, JSON.stringify(finalData));
        return finalData;
      });

      setIsLoading(false);
      setShowPRSelection(false);
      setCurrentStep('router');
    },
    [sessionId],
  );

  const waitForSSEOpen = async () => {
    if (sseRef.current?.readyState === EventSource.OPEN || sseReady) {
      return;
    }

    return new Promise<void>((resolve, reject) => {
      const start = Date.now();
      const timer = setInterval(() => {
        if (sseRef.current?.readyState === EventSource.OPEN) {
          clearInterval(timer);
          resolve();
          return;
        }

        if (Date.now() - start > 30000) {
          clearInterval(timer);
          reject(new Error('SSE connection timeout'));
        }
      }, 100);
    });
  };

  // SSE 메시지 핸들러 - useCallback으로 메모이제이션
  const handleSSEMessage = useCallback(
    (notification: RagNotification) => {
      if (!notification?.data || notification.data.sessionId !== sessionId) {
        return;
      }

      const { type, data } = notification;

      console.log('[SSE] Event received:', {
        type,
        node: data.node,
        dataType: data.type,
        hasPayload: !!data.payload,
        hasResponse: !!data.response,
      });

      switch (type) {
        case 'RAG_IN_PROGRESS': {
          if (data.type !== 'status') return;

          const mappedStep = NODE_TO_UI_STEP[data.node];
          if (mappedStep === null) return;

          console.log('[SSE] Step update:', data.node, '->', mappedStep);
          setCurrentStep(mappedStep);

          break;
        }

        case 'RAG_INTERRUPT': {
          if (data.node !== 'manage_pr_context' || !data.payload) return;

          console.log('[SSE] RAG_INTERRUPT payload length:', data.payload.length);

          setPrList(data.payload);
          setShowPRSelection(true);
          setIsLoading(false);
          break;
        }

        case 'RAG_DONE': {
          console.log('[SSE] RAG_DONE received:', {
            hasResponse: !!data.response,
            answer: data.response?.answer?.substring(0, 50),
            sourcesCount: data.response?.sources?.length,
            alreadyProcessing: processingDoneRef.current,
          });
          console.log('relatedJiraIssues len', data.relatedJiraIssues?.length);
          console.log(
            'sample sourceType',
            data.relatedJiraIssues?.[0]?.sourceType,
            typeof data.relatedJiraIssues?.[0]?.sourceType,
          );
          console.log('[SSE RAW JSON]', JSON.stringify(notification));
          console.log('normalized tasks', normalizeRelatedJiraIssues(data.relatedJiraIssues ?? []));

          // 중복 처리 방지
          if (processingDoneRef.current) {
            console.warn('[SSE] RAG_DONE already processed, ignoring');
            return;
          }
          processingDoneRef.current = true;

          const response = data.response;
          if (!response) {
            console.error('[SSE] RAG_DONE but no response');
            setIsError(true);
            setIsLoading(false);
            return;
          }

          const related = data.relatedJiraIssues ?? [];

          appendAssistantAnswer(response.answer, response.sources || [], related);
          break;
        }

        default:
          break;
      }
    },
    [sessionId, appendAssistantAnswer],
  );

  // SSE 연결 초기화 - sessionId가 변경될 때만 재연결
  useEffect(() => {
    console.log('[SSE] 세션 초기 연결:', sessionId);

    // 이미 연결되어 있으면 스킵
    if (sseRef.current?.readyState === EventSource.OPEN) {
      console.log('[SSE] 이미 연결됨');
      return;
    }

    setSseReady(false);

    const sse = createSSEConection(
      handleSSEMessage,
      (error) => {
        console.error('[SSE] Error:', error);
        if (sseRef.current?.readyState === EventSource.CLOSED) {
          setIsLoading(false);
        }
      },
      () => {
        console.log('[SSE] 연결');
        setTimeout(() => setSseReady(true), 1000);
        // console.log('[SSE] 연결 1초 after');
      },
    );

    sseRef.current = sse;

    return () => {
      console.log('[SSE] 클린업');
      sseRef.current?.close();
      sseRef.current = null;
      setSseReady(false);
    };
  }, [sessionId]);

  // 자동 하단 스크롤
  useEffect(() => {
    if (scrollRef.current) {
      const { scrollHeight, clientHeight } = scrollRef.current;
      scrollRef.current.scrollTo({
        top: scrollHeight - clientHeight,
        behavior: 'smooth',
      });
    }
  }, [chatData?.messages, isLoading, showPRSelection, currentStep, filterOpenMap]);

  // 초기 데이터 로드
  useEffect(() => {
    const saved = localStorage.getItem(`chat_${sessionId}`);

    if (saved) {
      setChatData(JSON.parse(saved));
      setIsLoading(false);
      return;
    }

    if (initialQuery) {
      fetchFirstAnswer(initialQuery);
      return;
    }

    setChatData({
      sessionId,
      title: '',
      repo: repo || '',
      messages: [],
    });
  }, [sessionId, initialQuery, repo]);

  const fetchFirstAnswer = async (query: string) => {
    beginAnswerLoading();

    // const indexList = repo ? [`${repo}`, `${repo}`, `${repo}`] : [];
    const indexList = [...HARD_CODED_INDEX_LIST];

    const initialData: ChatData = {
      sessionId,
      title: query,
      repo: repo || '',
      messages: [
        {
          id: crypto.randomUUID(),
          role: 'user',
          content: query,
          timestamp: new Date().toISOString(),
        },
      ],
    };

    setChatData(initialData);

    try {
      await waitForSSEOpen();
      await sendChatQuery(query, sessionId, indexList);

      // 30초 타임아웃
      const timeout = setTimeout(() => {
        if (isLoading) {
          setIsError(true);
          setIsLoading(false);
        }
      }, 30000);

      // cleanup은 RAG_DONE에서 처리
      return () => clearTimeout(timeout);
    } catch (err) {
      console.error('[fetchFirstAnswer] Error:', err);
      setIsError(true);
      setIsLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!newInput.trim() || isLoading || !chatData) return;

    // const indexList = repo ? [`${repo}`, `${repo}`, `${repo}`] : [];
    const indexList = [...HARD_CODED_INDEX_LIST];

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: newInput,
      timestamp: new Date().toISOString(),
    };

    const updated: ChatData = {
      ...chatData,
      messages: [...chatData.messages, userMessage],
    };
    setChatData(updated);

    setNewInput('');
    setIsMultiLine(false);
    if (textAreaRef.current) textAreaRef.current.style.height = '26px';

    beginAnswerLoading();

    try {
      await waitForSSEOpen();
      await sendChatQuery(newInput, sessionId, indexList);
    } catch (err) {
      console.error('[handleSendMessage] Error:', err);
      setIsError(false);
      setIsLoading(false);
    }
  };

  const handlePRContinue = async (selectedPrNumbers: number[]) => {
    console.log('[PR CONTINUE] selectedPrNumbers:', selectedPrNumbers);

    setShowPRSelection(false);
    beginAnswerLoading();

    const selectedPRs = selectedPrNumbers
      .map((prNumber) => prList.find((p) => p.prNumber === prNumber))
      .filter((pr): pr is PRPayload => pr !== undefined)
      .map((pr) => ({
        prNumber: pr.prNumber,
        repoName: pr.repoName,
        owner: pr.owner,
      }));

    console.log('[PR CONTINUE] payload to /api/chat/resume:', selectedPRs);

    try {
      await waitForSSEOpen();
      await resumeChatQuery(sessionId, selectedPRs);
    } catch (err) {
      console.error('[handlePRContinue] Error:', err);
      setIsError(true);
      setIsLoading(false);
    }
  };

  const handlePRRefetch = async () => {
    if (!chatData) return;

    const lastUser = [...chatData.messages].reverse().find((m) => m.role === 'user');
    const query = lastUser?.content?.trim();
    if (!query) return;

    console.log('[PR] refetch query:', query);

    beginAnswerLoading(); // PR 화면 다시 닫고 로딩

    try {
      await waitForSSEOpen();
      await sendChatQuery(query, sessionId, [...HARD_CODED_INDEX_LIST]);
    } catch (err) {
      console.error('[handlePRRefetch] Error: ', err);
      setIsError(true);
      setIsLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewInput(e.target.value);

    e.target.style.height = 'auto';
    const newHeight = Math.min(e.target.scrollHeight, 156);
    e.target.style.height = newHeight + 'px';

    setIsMultiLine(e.target.scrollHeight > 26);
  };

  const handleSubmitEdit = async (messageId: string, newContent: string) => {
    if (!chatData) return;

    const idx = chatData.messages.findIndex((m) => m.id === messageId);
    if (idx === -1) return;

    const trimmed = chatData.messages.slice(0, idx);
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: newContent,
      timestamp: new Date().toISOString(),
    };

    const updated: ChatData = {
      ...chatData,
      messages: [...trimmed, userMessage],
    };
    setChatData(updated);
    setEditingMessageId(null);

    beginAnswerLoading();

    // const indexList = repo ? [`${repo}`, `${repo}`, `${repo}`] : [];
    const indexList = [...HARD_CODED_INDEX_LIST];

    try {
      await waitForSSEOpen();
      await sendChatQuery(newContent, sessionId, indexList);
    } catch (err) {
      console.error('[handleSubmitEdit] Error:', err);
      setIsError(true);
      setIsLoading(false);
    }
  };

  if (!chatData) {
    return <div className="p-10 text-center">대화 내용을 불러오는 중...</div>;
  }

  const lastAssistantMessage = [...chatData.messages].reverse().find((m) => m.role === 'assistant');
  const currentSources = lastAssistantMessage?.sources || [];
  const currentDetailedTasks = lastAssistantMessage?.detailedTasks || [];

  const testContent = `
\`\`\`java
@Transactional
public ClientChatResponse checkAndIncrementUsageLimit(Long membermembermembermemberId, UUID sessionsessionsessionsessionsessionsessionId) {
    ChatUsageLimit usageLimit = chatUsageLimitRepository
        .findByMemberIdAndUsageDate(memberId, LocalDate.now())
        .orElse(null);

    if (usageLimit != null && usageLimit.getUsageCount() >= DAILY_CHAT_LIMIT) {
        return ClientChatResponse.of(sessionId, "일일 최대 채팅 횟수를 초과했습니다");
    }

    if (usageLimit == null) {
        usageLimit = ChatUsageLimit.createNewUsage(memberId);
    } else {
        usageLimit.incrementUsageCount();
    }

    chatUsageLimitRepository.save(usageLimit);
    return null;
}
\`\`\`
`;
  return (
    <div className="flex h-screen w-full overflow-hidden bg-white">
      <div className="flex min-w-0 flex-1 flex-col">
        <RagContentHeader />

        <div className="border-neutral-3 relative flex flex-1 flex-col overflow-hidden border-r">
          <div
            ref={scrollRef}
            className="flex flex-1 flex-col items-center gap-8 overflow-y-auto scroll-smooth px-24 pt-3 pb-9"
          >
            <div className="flex w-192.75 items-center justify-center gap-4">
              <div className="border-neutral-4 flex-1 border-t" />
              <span className="text-body-xsmall px-1.5 py-1 text-gray-50">
                {month}.{day}
              </span>
              <div className="border-neutral-4 flex-1 border-t" />
            </div>

            {chatData.messages.map((msg, index) => (
              <div key={msg.id} className="mx-auto flex w-193.25 flex-col gap-6">
                {msg.role === 'user' ? (
                  <div className="flex flex-col gap-4">
                    {editingMessageId === msg.id ? (
                      <EditMessageInput
                        initialContent={msg.content}
                        onCancel={() => setEditingMessageId(null)}
                        onSubmit={(newContent) => handleSubmitEdit(msg.id, newContent)}
                      />
                    ) : (
                      <div className="group relative max-w-full">
                        <span className="text-heading-xlarge text-gray-70 mr-5">{msg.content}</span>
                        <button
                          onClick={() => setEditingMessageId(msg.id)}
                          className="border-neutral-3 box-button-outline-gray inline-flex translate-y-1 cursor-pointer justify-center gap-1 rounded-lg border px-2 py-1 opacity-0 transition-opacity group-hover:opacity-100"
                        >
                          <EditPencil className="text-gray-70 h-5 w-5" />
                          <span className="text-body-xsmall text-gray-80 whitespace-nowrap">수정하기</span>
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <div className="mb-3 rounded-xl">
                      {!filterOpenMap[msg.id] ? (
                        <div className="relative flex items-center gap-1">
                          <div className="group relative flex items-center gap-1">
                            <div
                              onClick={(e) => {
                                e.stopPropagation();
                                setSpaceDropDownOpenMap((prev) => ({
                                  ...prev,
                                  [msg.id]: !prev?.[msg.id],
                                }));
                              }}
                              className={clsx(
                                'icon-button-only-gray flex cursor-pointer items-center gap-1 px-2 py-1',
                                spaceDropDownOpenMap?.[msg.id] && 'bg-neutral-3 rounded-lg',
                              )}
                            >
                              <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                                스페이스명 text text text
                              </div>
                              <DropDown
                                className={clsx(
                                  'text-gray-70 relative bottom-px h-4 w-4 shrink-0',
                                  spaceDropDownOpenMap?.[msg.id] && 'rotate-180',
                                )}
                              />
                            </div>
                            <div className="absolute bottom-12.5 left-23.75">
                              <ToolTip text={'답변 기준 팀스페이스 변경하기'} />
                            </div>
                          </div>

                          {spaceDropDownOpenMap?.[msg.id] && (
                            <div className="absolute top-10.5 z-100">
                              <TeamSpaceModal
                                onClose={() => {
                                  setSpaceDropDownOpenMap((prev) => ({ ...prev, [msg.id]: false }));
                                }}
                              />
                            </div>
                          )}

                          <Divider className="text-neutral-4 h-6 w-6 shrink-0" />

                          <div className="flex shrink-0 items-center gap-3">
                            <span className="text-body-xsmall text-gray-50">답변 세부 필터</span>
                            <button
                              onClick={() => setFilterOpenMap((prev) => ({ ...prev, [msg.id]: true }))}
                              className="cursor-pointer"
                            >
                              <ToggleOff />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-2">
                          <div className="relative flex gap-1">
                            <div className="group relative w-fit gap-1">
                              <div
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSpaceDropDownOpenMap((prev) => ({
                                    ...prev,
                                    [msg.id]: !prev?.[msg.id],
                                  }));
                                }}
                                className={clsx(
                                  'flex cursor-pointer items-center gap-1 px-2 py-1',
                                  spaceDropDownOpenMap?.[msg.id] ? 'bg-neutral-3 rounded-lg' : 'icon-button-only-gray',
                                )}
                              >
                                <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                                  스페이스명 text text text
                                </div>
                                <DropDown
                                  className={clsx(
                                    'text-gray-70 relative h-4 w-4 shrink-0',
                                    spaceDropDownOpenMap?.[msg.id] ? 'rotate-180 rounded-lg' : 'bottom-px',
                                  )}
                                />
                              </div>
                              <div className="absolute bottom-12.5 left-23.75">
                                <ToolTip text={'답변 기준 팀스페이스 변경하기'} />
                              </div>
                            </div>

                            {spaceDropDownOpenMap?.[msg.id] && (
                              <div className="absolute top-10.5 z-100">
                                <TeamSpaceModal
                                  onClose={() => {
                                    setSpaceDropDownOpenMap((prev) => ({ ...prev, [msg.id]: false }));
                                  }}
                                />
                              </div>
                            )}
                          </div>

                          <div onClick={() => setFilterOpenMap((prev) => ({ ...prev, [msg.id]: false }))}>
                            <FilterComponent
                              isOpen={filterOpenMap[msg.id]}
                              onClose={() => setFilterOpenMap((prev) => ({ ...prev, [msg.id]: false }))}
                            />
                          </div>
                        </div>
                      )}
                    </div>

                    {msg.content ? (
                      <>
                        <div
                          className={clsx(
                            "text-gray-80 prose prose-neutral [&_li::marker]:text-gray-70 max-w-none break-words [&>ol]:list-decimal [&>ol]:pl-5 [&>ul]:list-disc [&>ul]:pl-5 [&>ul>li:has(input[type='checkbox'])]:list-none [&>ul>li:has(input[type='checkbox'])]:pl-0",
                            '[&_pre]:overflow-x-auto [&_pre]:break-words [&_pre]:whitespace-pre-wrap',
                            '[&_pre]:bg-neutral-2 [&_pre]:rounded-xl [&_pre]:p-4',
                          )}
                        >
                          {/* <ReactMarkdown remarkPlugins={[remarkGfm]}>{formatMarkdownString(msg.content)}</ReactMarkdown> */}
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{testContent}</ReactMarkdown>
                        </div>

                        <div className="text-body-small text-gray-30">
                          질문과 연관된 {msg.sources?.length || 0}개의 핵심 자료를 선별했어요.
                        </div>

                        <AnswerActionButtons
                          icons={icon}
                          messageId={msg.id}
                          feedbackVisibleMap={feedbackVisibleMap}
                          setFeedbackVisibleMap={setFeedbackVisibleMap}
                        />

                        {feedbackVisibleMap[msg.id] && (
                          <FeedbackSection
                            messageId={msg.id}
                            feedbackVisibleMap={feedbackVisibleMap}
                            setFeedbackVisibleMap={setFeedbackVisibleMap}
                            feedbackSubmittedMap={feedbackSubmittedMap}
                            setFeedbackSubmittedMap={setFeedbackSubmittedMap}
                          />
                        )}
                      </>
                    ) : (
                      <ErrorResponse
                        icons={icon}
                        messageId={`error_${sessionId}`}
                        feedbackVisibleMap={feedbackVisibleMap}
                        setFeedbackVisibleMap={setFeedbackVisibleMap}
                        feedbackSubmittedMap={feedbackSubmittedMap}
                        setFeedbackSubmittedMap={setFeedbackSubmittedMap}
                      />
                    )}
                  </div>
                )}
              </div>
            ))}

            {showPRSelection && (
              <div className="mx-auto w-193.25">
                <GithubPRStepSkeleton onContinue={handlePRContinue} prList={prList} onRefetch={handlePRRefetch} />
              </div>
            )}

            {isLoading && !showPRSelection && (
              <div className="mx-auto w-193.25">
                <RagAnswerSkeleton currentStep={currentStep} />
              </div>
            )}

            {!isLoading && isError && (
              <div className="mx-auto w-193.25 pb-10">
                <ErrorResponse
                  icons={icon}
                  messageId={`error_${sessionId}`}
                  feedbackVisibleMap={feedbackVisibleMap}
                  setFeedbackVisibleMap={setFeedbackVisibleMap}
                  feedbackSubmittedMap={feedbackSubmittedMap}
                  setFeedbackSubmittedMap={setFeedbackSubmittedMap}
                />
              </div>
            )}
          </div>

          <div className="w-full flex-none bg-white px-24 pt-4 pb-8">
            <div className="mx-auto w-193.25">
              <div
                className={clsx(
                  'border-neutral-4 shadow-rag-bar flex gap-2 border bg-white px-3 py-2.5',
                  isMultiLine ? 'items-end rounded-3xl' : 'items-center rounded-full',
                )}
              >
                <div className="group relative flex-shrink-0">
                  <button className="icon-button-only-gray cursor-pointer rounded-full! p-1.5">
                    <Add className="text-gray-70 h-7 w-7" />
                  </button>
                  <div className="relative top-0.5 right-10">
                    <ToolTip text={'파일 추가 및 기타'} />
                  </div>
                </div>

                <textarea
                  ref={textAreaRef}
                  placeholder="업무 흐름이나 인수인계 내용을 질문해보세요"
                  value={newInput}
                  onChange={handleInputChange}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  rows={1}
                  className="text-body-medium placeholder:text-gray-30 flex-1 resize-none overflow-y-auto pr-2.5 outline-none"
                  style={{ height: '26px', maxHeight: '156px' }}
                />

                <div className="flex flex-shrink-0 items-center gap-3">
                  {!newInput.trim() && !isLoading && (
                    <div className="box-button-outline-gray flex h-7 cursor-pointer items-center justify-center gap-1 px-1.5 py-1">
                      <Filter className="relative top-0.5 h-4.5 w-4.5" />
                      <span className="text-body-xsmall text-gray-50">필터</span>
                    </div>
                  )}

                  {isLoading ? (
                    <button className="bg-neutral-3 flex h-10 w-10 items-center justify-center rounded-full">
                      <Stop className="text-gray-70 relative left-px h-6 w-6" />
                    </button>
                  ) : (
                    <button
                      onClick={handleSendMessage}
                      disabled={isLoading || !newInput.trim()}
                      className={`cursor-pointer rounded-full p-2 transition-colors ${
                        newInput.trim() ? 'bg-blue-50' : 'bg-neutral-1 border-neutral-2 border'
                      }`}
                    >
                      <ArrowSend
                        className={`h-6 w-6 cursor-pointer ${newInput.trim() ? 'brightness-0 invert' : 'text-gray-30'}`}
                      />
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        className={`border-neutral-3 flex flex-none flex-col border-l bg-white ${
          activeTab === 'source' ? 'w-101.25' : 'w-125'
        }`}
      >
        <RagRightAdditionalHeader activeTab={activeTab} onChange={setActiveTab} sourceCount={currentSources.length} />
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'source' && (
            <SourceComponent sources={currentSources} isLoading={isLoading} isError={isError} />
          )}
          {activeTab === 'detail' && <DetailedTasksComponent tasks={currentDetailedTasks} isLoading={isLoading} />}
        </div>
      </div>
    </div>
  );
}
