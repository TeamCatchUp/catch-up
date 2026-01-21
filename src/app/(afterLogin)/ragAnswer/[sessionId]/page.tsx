'use client';

import clsx from 'clsx';
import { useState, useRef, useEffect } from 'react';
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

const icon = [
  { name: 'Copy', icon: Copy },
  { name: 'Share', icon: Share },
  { name: 'ThumbsDown', icon: ThumbsDown },
  { name: 'Rotate', icon: Rotate },
  { name: 'Kebeb', icon: Kebeb },
];

// 백 노드 -> UI 단계 매핑
const NODE_TO_UI_STEP: Record<string, RagUIStepKey | 'manage_pr_context'> = {
  router: 'router',
  rewrite: 'router',
  plan: 'retrieve',
  retrieve: 'retrieve',
  manage_pr_context: 'manage_pr_context',
  rerank: 'rerank',
  grade: 'grade',
  generate: 'generate',
  chitchat: 'generate',
};

export default function Page() {
  const params = useParams();
  const searchParams = useSearchParams();

  const sessionId = params.sessionId as string;
  const repo = searchParams.get('repo');
  const initialQuery = searchParams.get('q');

  const [chatData, setChatData] = useState<any>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);

  const [currentStep, setCurrentStep] = useState<RagUIStepKey | 'manage_pr_context' | null>(null);
  const [prList, setPrList] = useState<PRPayload[]>([]);
  const [showPRSelection, setShowPRSelection] = useState(false);

  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);

  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<{ [key: string]: boolean }>({});
  const [feedbackSubmittedMap, setFeedbackSubmittedMap] = useState<{ [key: string]: boolean }>({});
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

  // 마크다운 문법 적용
  const formatMarkdownString = (text: string) => {
    return (
      text
        .replace(/\\n/g, '\n')
        // 마크다운 문법 앞에 빈 줄 추가
        .replace(/([^\n])\n(#{1,6}\s)/g, '$1\n\n$2') // 헤딩
        .replace(/([^\n])\n(\d+\.\s)/g, '$1\n\n$2') // 순서 목록
        .replace(/([^\n])\n([-*+]\s)/g, '$1\n\n$2') // 순서 없는 목록
        .replace(/([^\n])\n(-\s\[[x\s]\]\s)/g, '$1\n\n$2') // 체크박스
        .replace(/([^\n])\n(```)/g, '$1\n\n$2') // 코드블록
        .replace(/\n{3,}/g, '\n\n')
        .trim()
    );
  };

  // 로딩 시작 -> currentStep 기본값 박아둠
  const beginAnswerLoading = () => {
    setIsLoading(true);
    setIsError(false);
    setShowPRSelection(false);
    setCurrentStep('router');
  };

  const appendAssistantAnswer = (answer: string, sources: SourceResponse[] = []) => {
    setChatData((prev: ChatData | null) => {
      if (!prev) return prev;

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: answer,
        sources,
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
    setCurrentStep(null);
  };

  const waitForSSEOpen = async () => {
    // 이미 open이면 바로 통과
    if (sseRef.current?.readyState === EventSource.OPEN) return;
    // sseReady state가 true면 통과 (onopen에서 세팅됨)
    if (sseReady) return;

    await new Promise<void>((resolve, reject) => {
      const start = Date.now();
      const timer = setInterval(() => {
        const rs = sseRef.current?.readyState;

        if (rs === EventSource.OPEN) {
          clearInterval(timer);
          resolve();
          return;
        }

        if (Date.now() - start > 10000) {
          clearInterval(timer);
          reject(new Error('SSE not opened in time'));
        }
      }, 50);
    });
  };

  // SSE 메시지 핸들러
  const handleSSEMessage = (notification: RagNotification) => {
    console.log('SSE 수신:', notification.type, notification.data);

    // CONNECT 등 data=null 이벤트는 무시
    if (!notification?.data) return;
    if (notification.data.sessionId !== sessionId) return;

    // 1) sessionId가 없으면 무시 (방어)
    if (!notification.data.sessionId) {
      console.log('[SSE] ignore: no sessionId', notification);
      return;
    }

    // 2) 이 페이지 sessionId랑 다른 이벤트는 무시
    if (notification.data.sessionId !== sessionId) return;

    console.log('SSE 메시지 수신: ', notification); // 테스트용
    console.log('[SSE]', {
      eventType: notification.type,
      dataType: notification.data?.type,
      node: notification.data?.node,
      msg: notification.data?.message,
      sessionFromServer: notification.data?.sessionId,
      sessionFromURL: sessionId,
      hasResponse: !!notification.data?.response,
      payloadLen: notification.data?.payload?.length,
    });

    // sessionId 체크
    if (notification.data.sessionId !== sessionId) return;
    console.log('session check', {
      // test
      fromServer: notification.data.sessionId,
      fromURL: sessionId,
    });

    switch (notification.type) {
      case 'RAG_IN_PROGRESS': {
        console.log('IN_PROGRESS:', notification.data.node);
        if (notification.data.type !== 'status') return;

        const rawNode = notification.data.node;
        const mappedStep = NODE_TO_UI_STEP[rawNode] ?? 'router';

        setCurrentStep(mappedStep);
        break;
      }

      case 'RAG_INTERRUPT': {
        console.log('INTERRUPT:', notification.data.node);
        if (notification.data.node !== 'manage_pr_context') return;
        if (!notification.data.payload) return;

        setPrList(notification.data.payload);
        setShowPRSelection(true);
        setIsLoading(false);
        break;
      }

      case 'RAG_DONE': {
        console.log('DONE:', notification.data.response);
        const response = notification.data.response;
        if (!response) {
          console.error('DONE이지만 response 없음!');
          return;
        }

        appendAssistantAnswer(response.answer, response.sources || []);
        break;
      }

      default:
        break;
    }
  };

  // SSE 연결 초기화
  useEffect(() => {
    setSseReady(false);

    const sse = createSSEConection(
      handleSSEMessage,
      () => {
        if (sseRef.current?.readyState === EventSource.CLOSED) {
          setIsLoading(false);
        }
      },
      () => setSseReady(true),
    );

    sseRef.current = sse;

    return () => {
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
  }, [chatData?.messages, isLoading, showPRSelection]);

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

    // 아무것도 없으면 기본 구조라도 세팅 (빈 채팅 방)
    setChatData({
      sessionId,
      title: '',
      repo: repo || '',
      messages: [],
    });
  }, [sessionId, initialQuery, repo]);

  const fetchFirstAnswer = async (query: string) => {
    beginAnswerLoading();

    const indexList = repo ? [`${repo}_code`, `${repo}_pr`, `${repo}_jira_issue`] : [];

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
      const res = await sendChatQuery(query, sessionId, indexList);

      // HTTP 응답이 바로 answer를 주면 화면 업데이트 (fallback)
    } catch (err) {
      setIsError(true);
      setIsLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!newInput.trim() || isLoading || !chatData) return;

    const indexList = repo ? [`${repo}_code`, `${repo}_pr`, `${repo}_jira_issue`] : [];

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: newInput,
      timestamp: new Date().toISOString(),
    };

    const updated: ChatData = { ...chatData, messages: [...chatData.messages, userMessage] };
    setChatData(updated);

    setNewInput('');
    setIsMultiLine(false);
    if (textAreaRef.current) textAreaRef.current.style.height = '26px';

    beginAnswerLoading();

    try {
      await waitForSSEOpen();
      const res = await sendChatQuery(newInput, sessionId, indexList);

      // if (res?.answer) appendAssistantAnswer(res.answer, res.sources || []);
    } catch (err) {
      setIsError(true);
      setIsLoading(false);
    }
  };

  const handlePRContinue = async (selectedIds: number[]) => {
    setShowPRSelection(false);
    beginAnswerLoading();

    const selectedPRs = selectedIds
      .map((id) => prList.find((p) => p.prNumber === id) ?? null)
      .filter(Boolean)
      .map((pr) => ({
        prNumber: (pr as PRPayload).prNumber,
        repoName: (pr as PRPayload).repoName,
        owner: (pr as PRPayload).owner,
      }));

    try {
      await waitForSSEOpen();
      const res = await resumeChatQuery(sessionId, selectedPRs);

      // if (res?.answer) appendAssistantAnswer(res.answer, res.sources || []);
    } catch (err) {
      setIsError(true);
      setIsLoading(false);
    }
  };

  // 검색어 입력창 style 제어
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewInput(e.target.value);

    e.target.style.height = 'auto';
    const newHeight = Math.min(e.target.scrollHeight, 156);
    e.target.style.height = newHeight + 'px';

    setIsMultiLine(e.target.scrollHeight > 26);
  };

  // 수정 완료 핸들러
  const handleSubmitEdit = async (messageId: string, newContent: string) => {
    if (!chatData) return;

    const idx = chatData.messages.findIndex((m: any) => m.id === messageId);
    if (idx === -1) return;

    const trimmed = chatData.messages.slice(0, idx);
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: newContent,
      timestamp: new Date().toISOString(),
    };

    const updated: ChatData = { ...chatData, messages: [...trimmed, userMessage] };
    setChatData(updated);
    setEditingMessageId(null);

    beginAnswerLoading();

    const indexList = repo ? [`${repo}_code`, `${repo}_pr`, `${repo}_jira_issue`] : [];

    try {
      await waitForSSEOpen();
      const res = await sendChatQuery(newContent, sessionId, indexList);

      // HTTP fallback
      // if (res?.answer) appendAssistantAnswer(res.answer, res.sources || []);
    } catch {
      setIsError(true);
      setIsLoading(false);
    }
  };

  if (!chatData) return <div className="p-10 text-center">대화 내용을 불러오는 중...</div>;

  const lastAssistantMessage = [...chatData.messages].reverse().find((m) => m.role === 'assistant');
  const currentSources = lastAssistantMessage?.sources || [];

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

            {chatData.messages.map((msg: any) => (
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
                    <div className={`mb-3 rounded-xl`}>
                      {!filterOpenMap[msg.id] ? (
                        <div className="relative flex items-center gap-1">
                          <div className="group relative flex items-center gap-1">
                            <div
                              onClick={(e) => {
                                e.stopPropagation();
                                setSpaceDropDownOpenMap((prev) => ({ ...prev, [msg.id]: !prev?.[msg.id] }));
                              }}
                              className={clsx(
                                'icon-button-only-gray flex cursor-pointer items-center gap-1 px-2 py-1',
                                spaceDropDownOpenMap?.[msg.id] ? 'bg-neutral-3 rounded-lg' : 'icon-button-only-gray',
                              )}
                            >
                              <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                                스페이스명 text text text
                              </div>
                              <DropDown
                                className={clsx(
                                  'text-gray-70 relative bottom-px h-4 w-4 shrink-0',
                                  spaceDropDownOpenMap?.[msg.id] ? 'rotate-180' : 'bottom-px',
                                )}
                              />
                            </div>
                            <div className="absolute bottom-12.5 left-23.75">
                              <ToolTip text={'답변 기준 팀스페이스 변경하기'} />
                            </div>
                          </div>
                          {/* TeamSpace 드롭다운 모달 */}
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
                                  setSpaceDropDownOpenMap((prev) => ({ ...prev, [msg.id]: !prev?.[msg.id] }));
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
                            {/* TeamSpace 드롭다운 모달 */}
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
                        <div className="text-gray-80 prose prose-neutral [&_li::marker]:text-gray-70 max-w-none break-words [&>ol]:list-decimal [&>ol]:pl-5 [&>ul]:list-disc [&>ul]:pl-5 [&>ul>li:has(input[type='checkbox'])]:list-none [&>ul>li:has(input[type='checkbox'])]:pl-0">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{formatMarkdownString(msg.content)}</ReactMarkdown>
                        </div>
                        <div className="text-body-small text-gray-30">
                          질문과 연관된 {msg.sources?.length || 0}개의 핵심 자료를 선별했어요.
                        </div>

                        <AnswerActionButtons
                          icons={icon}
                          messageIdx={msg.id}
                          feedbackVisibleMap={feedbackVisibleMap}
                          setFeedbackVisibleMap={setFeedbackVisibleMap}
                        />
                        {feedbackVisibleMap[msg.id] && (
                          <FeedbackSection
                            messageIdx={msg.id}
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
                        messageIdx={msg.id}
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

            {/* manage_pr_context */}
            {showPRSelection && (
              <div className="mx-auto w-193.25">
                <GithubPRStepSkeleton onContinue={handlePRContinue} prList={prList} />
              </div>
            )}

            {/* 로딩 스켈레톤 */}
            {isLoading && !showPRSelection && (
              <div className="mx-auto w-193.25">
                <RagAnswerSkeleton currentStep={(currentStep as RagUIStepKey) ?? 'router'} />
              </div>
            )}

            {/* 에러 화면 */}
            {!isLoading && isError && (
              <div className="mx-auto w-193.25 pb-10">
                <ErrorResponse
                  icons={icon}
                  messageIdx={chatData.messages.length}
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
              {/* 검색 입력창 */}
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
          {activeTab === 'detail' && <DetailedTasksComponent />}
        </div>
      </div>
    </div>
  );
}
