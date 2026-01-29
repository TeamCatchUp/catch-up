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

  const [currentPage, setCurrentPage] = useState(0); // 현재 보고 있는 질문 인덱스 (pagination 상태)
  const [slideDirection, setSlideDirection] = useState<'down' | 'up' | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const answerScrollRef = useRef<HTMLDivElement>(null); // 답변 영역 스크롤
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const sseRef = useRef<EventSource | null>(null);
  const stoppedRef = useRef(false); // 로딩 중 질문 중지

  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');

  // 질문/답변 쌍 (user + assistant 하나의 페이지)
  const getQAPairs = () => {
    if (!chatData?.messages) return [];

    const pairs: Array<{ question: Message; answer?: Message; index: number }> = [];

    for (let i = 0; i < chatData.messages.length; i++) {
      const msg = chatData.messages[i];
      if (msg.role === 'user') {
        const nextMsg = chatData.messages[i + 1];
        pairs.push({
          question: msg,
          answer: nextMsg?.role === 'assistant' ? nextMsg : undefined,
          index: pairs.length,
        });
      }
    }

    return pairs;
  };

  const qaPairs = getQAPairs();
  const currentQA = qaPairs[currentPage];

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

  // currentPage 유효성 검증 (qaPairs 길이 변경 시)
  useEffect(() => {
    if (qaPairs.length > 0 && currentPage >= qaPairs.length) {
      setCurrentPage(qaPairs.length - 1);
    }
  }, [qaPairs.length, currentPage]);

  // 답변 영역 스크롤 초기화 (답변 변경 시)
  useEffect(() => {
    if (answerScrollRef.current) {
      answerScrollRef.current.scrollTop = 0;
    }
  }, [currentPage]);

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

    // 새 쿼리 전송 -> 새 페이지로 이동 (animation)
    setSlideDirection('up');
    setTimeout(() => {
      const newPageIndex = Math.floor(updated.messages.length / 2);
      setCurrentPage(newPageIndex);
      setSlideDirection(null);
    }, 300);

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

  // 스크롤 debounce를 위한 ref
  const isScrolling = useRef(false);
  const scrollTimeout = useRef<NodeJS.Timeout | null>(null);

  // 외부 스크롤로 페이지 전환
  const handleWheel = useCallback(
    (e: WheelEvent) => {
      // 로딩 중이거나 이미 스크롤 중이면 무시
      if (isLoading || isScrolling.current) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }

      // 답변 영역 스크롤 체크
      if (answerScrollRef.current) {
        const { scrollTop, scrollHeight, clientHeight } = answerScrollRef.current;
        const isScrollable = scrollHeight > clientHeight;

        // 스크롤 가능한 경우
        if (isScrollable) {
          // 답변 영역 내부에서 발생한 이벤트인지 체크
          const isInsideAnswer = answerScrollRef.current.contains(e.target as Node);

          if (isInsideAnswer) {
            // 스크롤 경계 체크 (여유 10px)
            const isAtTop = scrollTop <= 10;
            const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10;

            // 경계가 아니면 페이지 전환 차단
            if (e.deltaY > 0 && !isAtBottom) return;
            if (e.deltaY < 0 && !isAtTop) return;
          }
        }
      }

      // 페이지 전환 (스크롤 방향: 위로 올리면(deltaY < 0) 다음/최신 질문, 아래로 내리면(deltaY > 0) 이전 질문)
      // 다음 질문
      if (e.deltaY > 0 && currentPage < qaPairs.length - 1) {
        e.preventDefault();
        e.stopPropagation();

        // 즉시 잠금
        isScrolling.current = true;

        // 기존 타임아웃 클리어
        if (scrollTimeout.current) {
          clearTimeout(scrollTimeout.current);
        }

        setSlideDirection('up'); // 컨텐츠가 위로 올라가는 효과
        setTimeout(() => {
          setCurrentPage((prev) => Math.min(prev + 1, qaPairs.length - 1));
          setSlideDirection(null);
        }, 300);

        // 1초 후 잠금 해제
        scrollTimeout.current = setTimeout(() => {
          isScrolling.current = false;
        }, 1000);
      }

      // 아래로 스크롤 (이전 질문으로)
      else if (e.deltaY < 0 && currentPage > 0) {
        e.preventDefault();
        e.stopPropagation();

        // 즉시 잠금
        isScrolling.current = true;

        // 기존 타임아웃 클리어
        if (scrollTimeout.current) {
          clearTimeout(scrollTimeout.current);
        }

        setSlideDirection('down'); // 컨텐츠가 아래로 내려가는 효과
        setTimeout(() => {
          setCurrentPage((prev) => Math.max(prev - 1, 0));
          setSlideDirection(null);
        }, 300);

        // 1초 후 잠금 해제
        scrollTimeout.current = setTimeout(() => {
          isScrolling.current = false;
        }, 1000);
      }
    },
    [currentPage, qaPairs.length, isLoading],
  );

  useEffect(() => {
    const container = scrollRef.current;
    if (container) {
      container.addEventListener('wheel', handleWheel, { passive: false });
      return () => container.removeEventListener('wheel', handleWheel);
    }
  }, [handleWheel]);

  // 컴포넌트 언마운트 시 SSE 연결 정리
  useEffect(() => {
    return () => {
      closeSSEConnection();
      if (scrollTimeout.current) {
        clearTimeout(scrollTimeout.current);
      }
    };
  }, [closeSSEConnection]);

  if (!chatData) {
    return <div className="p-10 text-center">대화 내용을 불러오는 중...</div>;
  }

  const currentSources = currentQA?.answer?.sources || [];
  const currentDetailedTasks = currentQA?.answer?.detailedTasks || [];

  return (
    <div className="flex h-screen w-full overflow-hidden bg-white">
      <div className="flex min-w-0 flex-1 flex-col">
        <RagContentHeader title={chatData.title} />
        {/* 여기 gap도 */}
        <div className="border-neutral-3 relative flex flex-1 flex-col overflow-hidden border-r-0">
          <div
            ref={scrollRef}
            className="flex flex-1 flex-col items-center overflow-y-auto scroll-smooth px-24 pt-3 pb-9"
          >
            <div className="mb-8 flex w-192.75 items-center justify-center gap-4">
              <div className="border-neutral-4 flex-1 border-t" />
              <span className="text-body-xsmall px-1.5 py-1 text-gray-50">
                {month}.{day}
              </span>
              <div className="border-neutral-4 flex-1 border-t" />
            </div>
            <div
              className={`mx-auto w-193.25 flex-1 overflow-hidden transition-all duration-300 ${
                slideDirection === 'down'
                  ? 'translate-y-full opacity-0'
                  : slideDirection === 'up'
                    ? '-translate-y-full opacity-0'
                    : 'translate-y-0 opacity-100'
              }`}
            >
              {currentQA && (
                <div className="flex h-full flex-col gap-6">
                  {/* 질문 영역 (고정) */}
                  <div className="flex-none">
                    {editingMessageId === currentQA.question.id ? (
                      <EditMessageInput
                        initialContent={currentQA.question.content}
                        onCancel={() => setEditingMessageId(null)}
                        onSubmit={(newContent) => handleSubmitEdit(currentQA.question.id, newContent)}
                      />
                    ) : (
                      <div className="group relative max-w-full">
                        <span className="text-heading-xlarge text-gray-70 mr-5">{currentQA.question.content}</span>
                        {/* 마지막 질문(페이지)일 때만 수정 버튼 표시 */}
                        {currentPage === qaPairs.length - 1 && (
                          <button
                            onClick={() => setEditingMessageId(currentQA.question.id)}
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
                        )}
                      </div>
                    )}
                  </div>

                  {/* 답변 영역 (스크롤 가능) */}
                  <div ref={answerScrollRef} className="flex-1 overflow-y-auto">
                    {currentQA.answer ? (
                      <div className="flex flex-col gap-2">
                        {/* 필터 및 스페이스 드롭다운 */}
                        <div className="mb-3 rounded-xl">
                          {!filterOpenMap[currentQA.answer.id] ? (
                            <div className="relative flex items-center gap-1">
                              <div className="group relative flex items-center gap-1">
                                <div
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSpaceDropDownOpenMap((prev) => ({
                                      ...prev,
                                      [currentQA.answer!.id]: !prev?.[currentQA.answer!.id],
                                    }));
                                  }}
                                  className={clsx(
                                    'icon-button-only-gray flex cursor-pointer items-center gap-1 px-2 py-1',
                                    spaceDropDownOpenMap?.[currentQA.answer!.id] && 'bg-neutral-3 rounded-lg',
                                  )}
                                >
                                  <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                                    스페이스명 text text text
                                  </div>
                                  <DropDown
                                    className={clsx(
                                      'text-gray-70 relative bottom-px h-4 w-4 shrink-0',
                                      spaceDropDownOpenMap?.[currentQA.answer!.id] && 'rotate-180',
                                    )}
                                  />
                                </div>
                                <div className="absolute bottom-12.5 left-23.75">
                                  <ToolTip text={'답변 기준 팀스페이스 변경하기'} />
                                </div>
                              </div>

                              {spaceDropDownOpenMap?.[currentQA.answer!.id] && (
                                <div className="absolute top-10.5 z-100">
                                  <TeamSpaceModal
                                    onClose={() => {
                                      setSpaceDropDownOpenMap((prev) => ({ ...prev, [currentQA.answer!.id]: false }));
                                    }}
                                  />
                                </div>
                              )}

                              <Divider className="text-neutral-4 h-6 w-6 shrink-0" />

                              <div className="flex shrink-0 items-center gap-3">
                                <span className="text-body-xsmall text-gray-50">답변 세부 필터</span>
                                <button
                                  onClick={() =>
                                    setFilterOpenMap((prev) => ({ ...prev, [currentQA.answer!.id]: true }))
                                  }
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
                                        [currentQA.answer!.id]: !prev?.[currentQA.answer!.id],
                                      }));
                                    }}
                                    className={clsx(
                                      'flex cursor-pointer items-center gap-1 px-2 py-1',
                                      spaceDropDownOpenMap?.[currentQA.answer!.id]
                                        ? 'bg-neutral-3 rounded-lg'
                                        : 'icon-button-only-gray',
                                    )}
                                  >
                                    <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                                      스페이스명 text text text
                                    </div>
                                    <DropDown
                                      className={clsx(
                                        'text-gray-70 relative h-4 w-4 shrink-0',
                                        spaceDropDownOpenMap?.[currentQA.answer!.id]
                                          ? 'rotate-180 rounded-lg'
                                          : 'bottom-px',
                                      )}
                                    />
                                  </div>
                                  <div className="absolute bottom-12.5 left-23.75">
                                    <ToolTip text={'답변 기준 팀스페이스 변경하기'} />
                                  </div>
                                </div>

                                {spaceDropDownOpenMap?.[currentQA.answer!.id] && (
                                  <div className="absolute top-10.5 z-100">
                                    <TeamSpaceModal
                                      onClose={() => {
                                        setSpaceDropDownOpenMap((prev) => ({ ...prev, [currentQA.answer!.id]: false }));
                                      }}
                                    />
                                  </div>
                                )}
                              </div>

                              <div>
                                <FilterComponent
                                  isOpen={filterOpenMap[currentQA.answer!.id]}
                                  onClose={() =>
                                    setFilterOpenMap((prev) => ({ ...prev, [currentQA.answer!.id]: false }))
                                  }
                                />
                              </div>
                            </div>
                          )}
                        </div>

                        {currentQA.answer.content ? (
                          <>
                            <div className="markdown-body max-w-192.75 break-words">
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm, remarkBreaks]}
                                components={MarkDownComponents(currentQA.answer.sources)}
                              >
                                {formatMarkdownString(currentQA.answer.content)}
                              </ReactMarkdown>
                            </div>

                            <div className="text-body-small text-gray-30">
                              질문과 연관된 {currentQA.answer.sources?.length || 0}개의 핵심 자료를 선별했어요.
                            </div>

                            <AnswerActionButtons
                              icons={icon}
                              messageId={currentQA.answer.id}
                              feedbackVisibleMap={feedbackVisibleMap}
                              setFeedbackVisibleMap={setFeedbackVisibleMap}
                            />

                            {feedbackVisibleMap[currentQA.answer.id] && (
                              <FeedbackSection
                                messageId={currentQA.answer.id}
                                chatHistoryId={currentQA.answer.chatHistoryId}
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
                    ) : (
                      // 답변 로딩 중
                      <>
                        {showPRSelection ? (
                          <GithubPRStepSkeleton
                            onContinue={handlePRContinue}
                            prList={prList}
                            onRefetch={handlePRRefetch}
                          />
                        ) : isLoading ? (
                          <RagAnswerSkeleton currentStep={currentStep} />
                        ) : isError ? (
                          <ErrorResponse
                            icons={icon}
                            messageId={`error_${sessionId}`}
                            feedbackVisibleMap={feedbackVisibleMap}
                            setFeedbackVisibleMap={setFeedbackVisibleMap}
                            feedbackSubmittedMap={feedbackSubmittedMap}
                            setFeedbackSubmittedMap={setFeedbackSubmittedMap}
                          />
                        ) : null}
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* 페이지 인디케이터 */}
            {qaPairs.length > 1 && (
              <div className="mt-10 flex items-center gap-2">
                {qaPairs.map((_, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      if (isScrolling.current || idx === currentPage) return;
                      isScrolling.current = true;

                      // 기존 타임아웃 클리어
                      if (scrollTimeout.current) {
                        clearTimeout(scrollTimeout.current);
                      }

                      // 다음 페이지(더 큰 인덱스)로 가면 up, 이전 페이지로 가면 down
                      setSlideDirection(idx > currentPage ? 'up' : 'down');
                      setTimeout(() => {
                        setCurrentPage(idx);
                        setSlideDirection(null);
                        // 스크롤 잠금 해제
                        scrollTimeout.current = setTimeout(() => {
                          isScrolling.current = false;
                        }, 1000);
                      }, 300);
                    }}
                    disabled={isLoading}
                    className={clsx(
                      'h-2 w-2 rounded-full transition-all',
                      currentPage === idx ? 'w-6 bg-blue-50' : 'bg-gray-30',
                    )}
                  />
                ))}
              </div>
            )}
          </div>

          {/* 입력창 */}
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

      {/* 우측 사이드바 */}
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
