'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Add from '/public/icons/icon/add_small.svg';
import Share from '/public/icons/icon/share_2.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';
import EditPencil from '/public/icons/icon/edit_pencil.svg';
import ArrowSend from '/public/icons/icon/arrow_send.svg';
import Copy from '/public/icons/icon/copy.svg';
import ThumbsDown from '/public/icons/icon/thumbs-down.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import Cancel from '/public/icons/icon/cancel.svg';
import Filter from '@/components/rag/answerComponent/Filter';
import RagContentHeader from '@/components/rag/answerComponent/RagContentHeader';
import RagRightAdditionalHeader from '@/components/rag/rightComponent/sourceComponent/RagRightAdditionalHeader';
import SourceComponent from '@/components/rag/rightComponent/sourceComponent/SourceComponent';
import DetailedTasksComponent from '@/components/rag/rightComponent/detailedTasksComponent/DetailedTasksComponent';
import { useParams, useSearchParams } from 'next/navigation';
import { sendChatQuery } from 'src/util/sendChatQuery';
import RagAnswerSkeleton from '@/components/Skeleton/RagAnswerSkeleton';

const icon = [
  { name: 'Copy', icon: Copy },
  { name: 'Share', icon: Share },
  { name: 'ThumbsDown', icon: ThumbsDown },
  { name: 'Rotate', icon: Rotate },
  { name: 'Kebeb', icon: Kebeb },
];

const feedback = [
  { id: 1, content: '존재하지 않는 자료를 참고했어요' },
  { id: 2, content: '최신 내용이 반영되지 않았어요' },
  { id: 3, content: '답변의 출처가 없어요' },
  { id: 4, content: '중요한 정보가 누락되었어요' },
  { id: 5, content: '유용하지 않은 정보를 참고해요' },
  { id: 6, content: '내가 원하는 내용이 아니에요' },
  { id: 7, content: '답변이 너무 길어요' },
  { id: 8, content: '더 자세히...' },
];

export default function Page() {
<<<<<<< Updated upstream
  const [isLoading, setIsLoading] = useState(false);
=======
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [currentStep, setCurrentStep] = useState<RagStepKey | null>('router');
  const [hasGithubPR, setHasGithubPR] = useState(false);

>>>>>>> Stashed changes
  const params = useParams();
  const searchParams = useSearchParams();
  const sessionId = params.sessionId as string;
  const repo = searchParams.get('repo');
  const [chatData, setChatData] = useState<any>(null);

  const initialQuery = searchParams.get('q'); // URL에서 질문 추출

  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');

  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<{ [key: number]: boolean }>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);

  // 오른쪽 컴포넌트 헤더
  const [activeTab, setActiveTab] = useState<'source' | 'detail'>('source');

  const [newInput, setNewInput] = useState('');

<<<<<<< Updated upstream
=======
  // 임시용
  // const test = '**bold**\n\n\n- bold\n\n\n1. 하이\n\n\n```코드```\n\n\n- [ ] checklist\n\n\n### 제목3\n\n\n# 제목1';

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

  // 로컬 테스트용 단계별 Skeleton
  // useEffect(() => {
  //   if (!isLoading) return;

  //   setCurrentStep('router');
  //   const timers = [
  //     setTimeout(() => setCurrentStep('retrieve'), 500),
  //     setTimeout(() => setCurrentStep('rerank'), 1000),
  //     setTimeout(() => {
  //       setHasGithubPR(true);
  //       setCurrentStep('github_pr_mcp');
  //     }, 1500),
  //   ];

  //   return () => timers.forEach(clearTimeout);
  // }, [isLoading]);

>>>>>>> Stashed changes
  useEffect(() => {
    if (showFeedback && scrollRef.current) {
      const scrollEl = scrollRef.current;
      const searchBarHeight = 100;
      scrollEl.scrollTo({
        top: scrollEl.scrollHeight - scrollEl.clientHeight + searchBarHeight,
        behavior: 'smooth',
      });
    }
  }, [showFeedback]);

  useEffect(() => {
    if (scrollRef.current) {
      const { scrollHeight, clientHeight } = scrollRef.current;
      scrollRef.current.scrollTo({
        top: scrollHeight - clientHeight,
        behavior: 'smooth',
      });
    }
  }, [chatData?.messages, isLoading]);

  useEffect(() => {
    const saved = localStorage.getItem(`chat_${sessionId}`);

    if (saved) {
      setChatData(JSON.parse(saved));
    } else if (initialQuery) {
      fetchFirstAnswer(initialQuery);
    }
  }, [sessionId]);

  const fetchFirstAnswer = async (query: string) => {
    setIsLoading(true);
    const safeRepo = repo || '';

    const initialData = {
      sessionId,
      title: query,
      repo: safeRepo,
      messages: [{ role: 'user', content: query, timestamp: new Date().toISOString() }],
    };
    setChatData(initialData);

    try {
      const result = await sendChatQuery(query, sessionId, safeRepo);

      const finalData = {
        ...initialData,
        messages: [
          ...initialData.messages,
          {
            role: 'assistant',
            content: result.answer,
            sources: result.sources || [],
            timestamp: new Date().toISOString(),
          },
        ],
      };
      setChatData(finalData);
      localStorage.setItem(`chat_${sessionId}`, JSON.stringify(finalData));
    } catch (error) {
      console.error(error);
      alert('답변을 가져오는데 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!newInput.trim() || isLoading || !chatData) return; // chatData 체크 추가

    const safeRepo = repo || chatData.repo || ''; // 현재 상태의 repo 활용

    const userMessage = { role: 'user', content: newInput, timestamp: new Date().toISOString() };
    const updatedData = {
      ...chatData,
      messages: [...(chatData.messages || []), userMessage],
    };

    setChatData(updatedData);
    setNewInput('');
    setIsLoading(true);
    try {
      const result = await sendChatQuery(newInput, sessionId, safeRepo);

      const assistantMessage = {
        role: 'assistant',
        content: result.answer,
        sources: result.sources || [],
        timestamp: new Date().toISOString(),
      };

      const finalData = {
        ...updatedData,
        messages: [...updatedData.messages, assistantMessage],
      };

      setChatData(finalData);
      localStorage.setItem(`chat_${sessionId}`, JSON.stringify(finalData));
    } catch (error) {
      alert('답변을 가져오지 못했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!chatData) return <div className="p-10 text-center">대화 내용을 불러오는 중...</div>;

  // 가장 마지막 답변의 출처 개수 계산
  const lastAssistantMessage = [...chatData.messages].reverse().find((m) => m.role === 'assistant');
  const currentSources = lastAssistantMessage?.sources || [];
  return (
    <div className="flex h-screen w-full overflow-hidden bg-white">
      {/* 왼쪽 메인 영역 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <RagContentHeader />

        <div className="border-neutral-3 relative flex flex-1 flex-col overflow-hidden border-r">
          <div
            ref={scrollRef}
            className="flex flex-1 flex-col items-center gap-10 overflow-y-auto scroll-smooth px-24 py-9"
          >
            {/* 날짜 표시 */}
            <div className="flex w-192.75 items-center justify-center gap-4">
              <div className="border-neutral-4 flex-1 border-t" />
              <span className="text-body-xsmall outline-gray cursor-pointer rounded-full px-1.5 py-1 text-gray-50">
                {month}.{day}
              </span>
              <div className="border-neutral-4 flex-1 border-t" />
            </div>

            {/* 채팅 내용 순회 */}
            {chatData.messages.map((msg: any, idx: number) => (
              <div key={idx} className="mx-auto flex w-193.25 flex-col gap-6">
                {msg.role === 'user' ? (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                      <div className="text-heading-xlarge text-gray-70 flex-1">{msg.content}</div>
                      <button className="border-neutral-3 outline-gray flex cursor-pointer items-center justify-center gap-1 self-end rounded-lg border px-2 py-1">
                        <EditPencil className="text-gray-70 h-5 w-5" />
                        <span className="text-body-xsmall text-gray-80 outline-gray">수정하기</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-5">
                    <div className="border-neutral-3 mb-3 rounded-xl border">
                      <Filter />
                    </div>
                    <div className="text-body-medium text-gray-80 prose prose-neutral max-w-none break-words">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    </div>
                    <div className="text-body-small text-gray-30">
                      질문과 연관된 {msg.sources?.length || 0}개의 핵심 자료를 선별했어요.
                    </div>

                    <div className="flex gap-1">
                      {icon.map((item, i) => {
                        const isThumbsDown = item.name === 'ThumbsDown';
                        const activeClass = isThumbsDown && showFeedback ? 'bg-neutral-3 border-neutral-5' : '';
                        return (
                          <button
                            key={i}
                            onClick={() => {
                              if (isThumbsDown) {
                                setFeedbackVisibleMap((prev) => ({
                                  ...prev,
                                  [idx]: !prev[idx],
                                }));
                              }
                            }}
                            className={`outline-gray cursor-pointer rounded-lg p-1.5 ${activeClass}`}
                          >
                            <item.icon className="h-6 w-6 text-gray-50" />
                          </button>
                        );
                      })}
                    </div>
                    {/* 피드백 */}
                    {feedbackVisibleMap[idx] && (
                      <div
                        ref={feedbackRef}
                        className="border-neutral-4 mx-auto flex w-193.25 flex-col gap-4 rounded-xl border p-4"
                      >
                        <div className="flex justify-between">
                          <span className="text-body-small text-gray-50">
                            답변이 마음에 들지 않은 이유가 무엇인가요?
                          </span>
                          <div
                            onClick={() => setFeedbackVisibleMap((prev) => ({ ...prev, [idx]: false }))}
                            className="outline-gray flex cursor-pointer items-center rounded-full p-0.5"
                          >
                            <Cancel className="relative bottom-[0.5px] h-4.5 w-4.5 text-gray-50" />
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-x-2.5 gap-y-1.5">
                          {feedback.map((feedback, idx) => {
                            return (
                              <button
                                key={idx}
                                className="outline-gray border-neutral-3 text-xsmall text-gray-80 cursor-pointer rounded-lg border px-2 py-1"
                              >
                                {feedback.content}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

<<<<<<< Updated upstream
            {isLoading && (
              <div className="text-gray-40 mx-auto w-193.25 animate-pulse pb-10">
                <RagAnswerSkeleton />
=======
            {/* <div className="text-gray-40 mx-auto w-193.25 animate-pulse pb-10"> */}
            {/* <RagAnswerSkeleton /> */}
            {/* </div> */}
            {isLoading && !isError && (
              <div className="mx-auto w-193.25">
                <RagAnswerSkeleton
                  currentStep={currentStep}
                  hasGithubPR={hasGithubPR}
                  setCurrentStep={setCurrentStep}
                />
>>>>>>> Stashed changes
              </div>
            )}
          </div>

          <div className="w-full flex-none bg-white px-24 py-4">
            <div className="mx-auto w-193.25">
              {/* <div className="no-scrollbar mb-4 flex justify-start gap-2.5 overflow-x-auto">
                {['연차 신청', '근태 관리', '비용 정산'].map((item, index) => (
                  <button
                    key={index}
                    className="border-blue-30 bg-blue-1 text-body-small hover:bg-blue-5 active:border-blue-45 text-blue-55 cursor-pointer rounded-full border px-3 py-1.5 whitespace-nowrap"
                  >
                    {item}
                  </button>
                ))}
              </div> */}

              {/* 입력바 */}
              <div className="border-neutral-4 shadow-rag-bar flex items-center gap-2 rounded-full border bg-white px-3 py-2.5">
                <button className="outline-gray cursor-pointer rounded-full p-1.5">
                  <Add className="text-gray-70 h-7 w-7" />
                </button>
                <textarea
                  className="text-body-medium max-h-[26px] flex-1 resize-none overflow-hidden overflow-y-auto outline-none"
                  placeholder="추가 질문을 입력하세요"
                  value={newInput}
                  onChange={(e) => {
                    setNewInput(e.target.value);
                    e.target.style.height = 'auto';
                    e.target.style.height = Math.min(e.target.scrollHeight, 26) + 'px';
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                />
<<<<<<< Updated upstream
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
=======

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
>>>>>>> Stashed changes
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 우측 사이드바 */}
      <div className="border-neutral-3 flex w-101.25 flex-none flex-col border-l bg-white">
        <RagRightAdditionalHeader activeTab={activeTab} onChange={setActiveTab} sourceCount={currentSources.length} />
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'source' && <SourceComponent sources={currentSources} isLoading={isLoading} />}
          {activeTab === 'detail' && <DetailedTasksComponent />}
        </div>
      </div>
    </div>
  );
}
