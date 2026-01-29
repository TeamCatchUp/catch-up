'use client';

import clsx from 'clsx';
import { useState, useRef, useEffect, useCallback } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

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
import { MarkDownComponents } from '@/components/rag/answerComponent/markdown/MarkDownComponents';

import { createSSEConnection, sendChatQuery, resumeChatQuery } from '@/util/sendChatQuery';
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
  const stoppedRef = useRef(false); // 로딩 중 질문 중지

  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');

  // MD -> string
  const formatMarkdownString = (text: string) => {
    if (!text) return '';

    // \r\n, \r을 \n으로 통일
    let normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\\n/g, '\n');

    // strong 안의 백틱 코드 앞/뒤에 바로 글자가 오는 경우 띄어쓰기 추가 (**`code`**글자 -> **`code`** 글자)
    normalized = normalized.replace(/(\*\*`[^`]+`\*\*)([^\s*])/g, '$1 $2');

    // 블록 문법 시작(헤딩/리스트/체크박스/코드펜스/인용/테이블) 앞에 빈 줄 보정
    const withSpacing = normalized.replace(
      /([^\n])\n(?=(#{1,6}\s|(\d+)\.\s|[-*+]\s|-\s\[[xX\s]\]\s|```|>\s|\|))/g,
      '$1\n\n',
    );

    return withSpacing.trimEnd();
  };

  // SSE 연결 종료 함수
  const closeSSEConnection = useCallback(() => {
    if (sseRef.current) {
      console.log('[closeSSEConnection] 연결 종료');
      sseRef.current.close();
      sseRef.current = null;
    }
  }, []);

  const beginAnswerLoading = useCallback(() => {
    stoppedRef.current = false;
    setIsLoading(true);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');
  }, []);

  // content='' (error response) -> new 쿼리 생성 시 질문 기록만 남김
  const stripTrailingErrorAssistant = (messages: Message[]) => {
    const last = messages[messages.length - 1];

    if (last?.role === 'assistant' && (last.content ?? '') === '') {
      return messages.slice(0, -1);
    }
    return messages;
  };

  const appendAssistantAnswer = useCallback(
    (
      answer: string,
      sources: BackendSource[] = [],
      relatedJiraIssues: BackendSource[] = [],
      chatHistoryId?: string,
    ) => {
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
          chatHistoryId,
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

  // SSE 메시지 핸들러 - useCallback으로 메모이제이션
  const handleSSEMessage = useCallback(
    (notification: RagNotification) => {
      if (stoppedRef.current) return; // 입력 중지 이후 모든 SSE 무시

      if (!notification?.data || notification.data.sessionId !== sessionId) {
        return;
      }

      const { type, data } = notification;

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

          // 백에서 연결 정리
          console.log('[SSE] RAG_INTERRUPT - 연결 종료');
          closeSSEConnection();
          break;
        }

        case 'RAG_DONE': {
          window.dispatchEvent(new Event('refresh_sidebar'));
          console.log('[SSE] RAG_DONE received:', {
            hasResponse: !!data.response,
            answer: data.response?.answer,
            sourcesCount: data.response?.sources?.length,
            chatHistoryId: data.response?.chatHistoryId,
          });

          const response = data.response;
          if (!response) {
            console.error('[SSE] RAG_DONE but no response');
            setIsError(true);
            setIsLoading(false);
            closeSSEConnection();
            return;
          }

          const related = data.relatedJiraIssues ?? [];

          appendAssistantAnswer(response.answer, response.sources || [], related, response.chatHistoryId);

          closeSSEConnection();
          break;
        }

        default:
          break;
      }
    },
    [sessionId, appendAssistantAnswer, closeSSEConnection],
  );

  // SSE 연결 생성 및 채팅 요청 함수 (1질문 1연결)
  const connectSSEAndSendQuery = useCallback(
    async (query: string, indexList: string[], isResume: boolean = false, resumePayload?: any) => {
      return new Promise<void>((resolve, reject) => {
        console.log('[connectSSEAndSendQuery] SSE 연결 시작');

        // 기존 연결 정리
        closeSSEConnection();

        let sseConnected = false;
        let chatRequestSent = false;

        const timeout = setTimeout(() => {
          if (!chatRequestSent) {
            console.error('[connectSSEAndSendQuery] 타임아웃 - 30초 내 응답 없음');
            closeSSEConnection();
            reject(new Error('SSE connection timeout'));
          }
        }, 30000);

        // SSE 연결
        const sse = createSSEConnection(
          sessionId,
          handleSSEMessage,
          (err) => {
            console.error('[connectSSEAndSendQuery] error:', err);
            if (!chatRequestSent) {
              clearTimeout(timeout);
              closeSSEConnection();
              reject(err);
            }
          },
          async () => {
            console.log('[connectSSEAndSendQuery] 연결 완료 (onOpen)');
            sseConnected = true;

            // 연결 완료 후 즉시 send 채팅 요청
            try {
              if (isResume) {
                console.log('[connectSSEAndSendQuery] Resume 요청 전송');
                await resumeChatQuery(sessionId, resumePayload);
              } else {
                console.log('[connectSSEAndSendQuery[ 채팅 요청 전송:', query);
                await sendChatQuery(query, sessionId, indexList);
              }
              chatRequestSent = true;
              console.log('[connectSSEAndSendQuery] 채팅 요청 완료');
              resolve();
            } catch (err) {
              console.error('[connectSSEAndSendQuery] 채팅 요청 실패:', err);
              clearTimeout(timeout);
              closeSSEConnection();
              reject(err);
            }
          },
        );

        sseRef.current = sse;
      });
    },
    [sessionId, handleSSEMessage, closeSSEConnection],
  );

  // 자동 하단 스크롤
  useEffect(() => {
    if (scrollRef.current) {
      const { scrollHeight, clientHeight } = scrollRef.current;
      scrollRef.current.scrollTo({
        top: scrollHeight - clientHeight,
        behavior: 'smooth',
      });
    }
  }, [chatData?.messages, isLoading, showPRSelection, currentStep]);

  // 초기 데이터 로드
  useEffect(() => {
    const saved = localStorage.getItem(`chat_${sessionId}`);

    // localStorage에서 데이터 복원
    if (saved) {
      const parsedData: ChatData = JSON.parse(saved);

      // 마지막 메시지가 user = 답변 받지 못한 상태 (답변 에러) - 쿼리 자동 재전송 X
      const lastMessage = parsedData.messages[parsedData.messages.length - 1];

      if (lastMessage?.role === 'user') {
        const errorData: ChatData = {
          ...parsedData,
          messages: [
            ...parsedData.messages,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: '', // 빈 content = ErrorResponse 컴포넌트 렌더링
              sources: [],
              detailedTasks: [],
              timestamp: new Date().toISOString(),
            },
          ],
        };

        setChatData(errorData);
        localStorage.setItem(`chat_${sessionId}`, JSON.stringify(errorData));
        setIsLoading(false);
        return;
      }

      // 정상적으로 완료된 대화 복원
      setChatData(parsedData);
      setIsLoading(false);
      return;
    }

    // initialQuery로 첫 질문 실행
    if (initialQuery) {
      fetchFirstAnswer(initialQuery);
      return;
    }

    // 빈 채팅 데이터 생성
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
      await connectSSEAndSendQuery(query, indexList);
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

    // 직전 ErrorResponse(빈 assistant) 제거하고 append
    const cleanedMessages = stripTrailingErrorAssistant(chatData.messages);

    const updated: ChatData = {
      ...chatData,
      messages: [...chatData.messages, userMessage],
    };
    setChatData(updated);
    localStorage.setItem(`chat_${sessionId}`, JSON.stringify(updated));

    const queryToSend = newInput;
    setNewInput('');
    setIsMultiLine(false);
    if (textAreaRef.current) textAreaRef.current.style.height = '26px';

    beginAnswerLoading();

    try {
      await connectSSEAndSendQuery(queryToSend, indexList);
    } catch (err: any) {
      console.error('[handleSendMessage] Error:', err);
      setIsError(true);
      setIsLoading(false);
    }
  };

  const handlePRContinue = async (selectedPrNumbers: number[]) => {
    console.log('[PR CONTINUE] selectedPrNumbers:', selectedPrNumbers);

    setShowPRSelection(false);
    beginAnswerLoading(); // SSE 연결은 RAG_INTERRUPT에서 이미 종료된 상태

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
      // 새로운 SSE 연결 생성 후 resume 요청
      console.log('[handlePRContinue] 새로운 SSE 연결 -> resume 요청');
      await connectSSEAndSendQuery('', [], true, selectedPRs);
    } catch (err) {
      console.error('[handlePRContinue] Error:', err);
      setIsError(true);
      setIsLoading(false);
    }
  };

  // 다시 찾기 기능 아직 로직 X
  const handlePRRefetch = async () => {
    if (!chatData) return;

    const lastUser = [...chatData.messages].reverse().find((m) => m.role === 'user');
    const query = lastUser?.content?.trim();
    if (!query) return;

    console.log('[PR] refetch query:', query);

    // 기존 SSE 연결 종료 후 새로 시작
    closeSSEConnection();
    beginAnswerLoading();

    try {
      await connectSSEAndSendQuery(query, [...HARD_CODED_INDEX_LIST]);
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
    const cleanedTrimmed = stripTrailingErrorAssistant(trimmed);

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
      await connectSSEAndSendQuery(newContent, indexList);
    } catch (err) {
      console.error('[handleSubmitEdit] Error:', err);
      setIsError(true);
      setIsLoading(false);
    }
  };

  const handleStop = useCallback(() => {
    if (!isLoading) return;

    stoppedRef.current = true; // 이후 SSE 무시

    setIsLoading(false);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');

    closeSSEConnection();

    // 답변 : 빈 줄
    appendAssistantAnswer('\n', [], []);
  }, [isLoading, appendAssistantAnswer, closeSSEConnection]);

  // 컴포넌트 언마운트 시 SSE 연결 정리
  useEffect(() => {
    return () => {
      closeSSEConnection();
    };
  }, [closeSSEConnection]);

  if (!chatData) {
    return <div className="p-10 text-center">대화 내용을 불러오는 중...</div>;
  }

  const lastAssistantMessage = [...chatData.messages].reverse().find((m) => m.role === 'assistant');
  const currentSources = lastAssistantMessage?.sources || [];
  const currentDetailedTasks = lastAssistantMessage?.detailedTasks || [];

  return (
    <div className="flex h-screen w-full overflow-hidden bg-white">
      <div className="flex min-w-0 flex-1 flex-col">
        <RagContentHeader />

        <div className="border-neutral-3 relative flex flex-1 flex-col overflow-hidden border-r-0">
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

            {chatData.messages.map((msg) => (
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
                          className={clsx(
                            'border-neutral-3 box-button-outline-gray',
                            'hidden',
                            'group-hover:inline-flex',
                            'translate-y-1 cursor-pointer justify-center gap-1 rounded-lg border px-2 py-1',
                          )}
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

                          <div>
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
                        <div className="markdown-body max-w-192.75 break-words">
                          <ReactMarkdown
                            remarkPlugins={[
                              remarkGfm,
                              remarkBreaks, // \n을 <br/>로 변환
                            ]}
                            components={MarkDownComponents(msg.sources)}
                          >
                            {formatMarkdownString(msg.content)}
                          </ReactMarkdown>
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
                            chatHistoryId={msg.chatHistoryId}
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
                    <button
                      onClick={handleStop}
                      className="bg-neutral-3 flex h-10 w-10 items-center justify-center rounded-full"
                    >
                      <Stop className="text-gray-70 relative left-px h-6 w-6 cursor-pointer" />
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

      <div className={`border-neutral-3 flex w-115 flex-none flex-col border-l bg-white`}>
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

/* 마크다운 문법 적용 예시 */
// import ReactMarkdown from 'react-markdown';
// import remarkGfm from 'remark-gfm';
// import remarkBreaks from 'remark-breaks';
// import { MarkDownComponents } from '@/components/rag/answerComponent/MarkDownComponents';

// const mockMD = `
// # h1 제목

// - 가나다abc \`단독 인라인코드\` \`단어+인라인코드\`랑
// - **\`strong 인라인코드\`** **\`strong 단어+인라인코드\`**랑
// - **\`여기서안되네\`**

// > 인용문1
// > blockquoteblockquo한글한글한글teblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockqublockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockqublockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquoteblockquote

// ### 주요 지표 분석 (ul)
// - 브랜드 지수는 평균 대비 +22% 높게 나타났습니다.
//   - 브랜드 지수는 평균 대비 +22% 높게 나타났습니다. 브랜드 지수는 평균 대비 +22% 높게 나타났습니다. 브랜드 지수는 평균 대비 +22% 높게 나타났습니다. 브랜드 지수는 평균 대비 +22% 높게 나타났습니다. 브랜드 지수는 평균 대비 +22% 높게 나타났습니다. 브랜드 지수는 평균 대비 +22% 높게 나타났습니다.

// ### 주요 지표 분석 (ol)
// -브랜드 지수는 평균 대비 +22% 높게 나타났습니다.
//   -브랜드 지수는 평균 대비 +22% 높게 나타났습니다.

// **strong** strong **strong**아
// - 링크: [naver](https://naver.com)
// - 링크에 \`inline\`도 섞기: [\`/api/chat/resume\` 문서](https://example.com/api-docs)

// ## 리스트 (ul / ol / 중첩)

// - ul 1번
// - ul 2번
//   - ul 2-1 (중첩)
//   - ul 2-2 (중첩)
//     - ul 2-2-1 (더 중첩)
// - ul 3번

// 1. ol 1번
// 2. 브랜드 지수는 평균 대비 +22% 높게 나타났습니다.
//    1. 브랜드 지수는 평균 대비 +22% 높게 나타났습니다.
//    2. 브랜드 지수는 평균 대비 +22% 높게 나타났습니다.
// 3. ol 3번

// ## 코드블럭 (pre > code)

// \`\`\`ts
// type RagNotification = {
//   target: 'CHAT';
//   type: 'RAG_IN_PROGRESS' | 'RAG_INTERRUPT' | 'RAG_DONE';
//   message: string | null;
//   data: {
//     sessionId: string;
//     type: 'status' | 'interrupt' | 'result' | 'interrupt' | 'result'  | 'interrupt' | 'result' | 'interrupt' | 'result' | 'interrupt' | 'result' | 'interrupt' | 'result';
//     node: string;
//     payload?: unknown;
//     response?: {
//       answer: string;
//       sources?: Array<{ sourceType: number; title: string }>;
//     };
//   };
// };

// function demoInlineVsBlock() {
//   const endpoint = '/api/notification/subscribe';
//   console.log('SSE endpoint:', endpoint);
// }
// \`\`\`

// \`\`\`bash
// # curl example
// curl -N -H "Accept:text/event-streamAccept:text/event-streamAccept:text/event-stream" "https://example.com/api/notification/subscribe"
// \`\`\`

// \`\`\`bash
// # curl example
// curl -N -H "Accep"
// \`\`\`

// ## H2: 테이블 (table)

// | 항목 | 설명 | 예시 |
// |---|---|---|
// | sessionId | 세션 식별자 | \`746a8ca1-19d6-4d35-b80e-401f97ecbda8\` |
// | node | RAG 단계 | \`router\`, \`retrieve\`, \`rerank\`, \`generate\` |
// | type | 이벤트 타입 | \`RAG_IN_PROGRESS\`, \`RAG_DONE\` |

// ## H2: 이미지 (img)

// ![테스트 이미지](https://picsum.photos/800/450)

// ## H2: 마무리

// 인라인 코드 \`final_check=true\` 와 **굵게 표시**! **굵게 표시**

// 줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문줄본문 검사검사 본문본문

// 바줄본문 검사검사 본문본문
// 꿈줄본문 검사검사 본문본문
// `;

// export default function Mail() {
//   const formatMarkdownString = (text: string) => {
//     if (!text) return '';

//     // \r\n, \r을 \n으로 통일
//     let normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\\n/g, '\n');

//     // **`code`**글자 형태를 **`code`** 글자로 변환 (띄어쓰기 추가)
//     // strong 안의 백틱 코드 뒤에 바로 글자가 오는 경우 띄어쓰기 추가
//     normalized = normalized.replace(/(\*\*`[^`]+`\*\*)([^\s*])/g, '$1 $2');

//     // 블록 문법 시작(헤딩/리스트/체크박스/코드펜스/인용/테이블) 앞에 빈 줄 보정
//     const withSpacing = normalized.replace(
//       /([^\n])\n(?=(#{1,6}\s|(\d+)\.\s|[-*+]\s|-\s\[[xX\s]\]\s|```|>\s|\|))/g,
//       '$1\n\n',
//     );

//     return withSpacing.trimEnd();
//   };
//   return (
//     <div className="markdown-body max-w-192.75 p-10 break-words">
//       <ReactMarkdown
//         remarkPlugins={[
//           remarkGfm,
//           remarkBreaks, // 문제 5 해결: \n을 <br/>로 변환
//         ]}
//         components={MarkDownComponents}
//       >
//         {formatMarkdownString(mockMD)}
//       </ReactMarkdown>
//     </div>
//   );
// }
