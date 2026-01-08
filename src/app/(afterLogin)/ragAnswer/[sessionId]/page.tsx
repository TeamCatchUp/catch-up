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
  const [isLoading, setIsLoading] = useState(false);
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
              <span className="text-body-xsmall px-1.5 py-1 text-gray-50">
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
                      <button className="border-neutral-3 box-button-outline-gray flex cursor-pointer items-center justify-center gap-1 self-end rounded-lg border px-2 py-1">
                        <EditPencil className="text-gray-70 h-5 w-5" />
                        <span className="text-body-xsmall text-gray-80">수정하기</span>
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
                            className={`icon-button-outline-gray cursor-pointer p-1.5 ${activeClass}`}
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
                            className="box-button-outline-gray flex cursor-pointer items-center rounded-full p-0.5"
                          >
                            <Cancel className="relative bottom-[0.5px] h-4.5 w-4.5 text-gray-50" />
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-x-2.5 gap-y-1.5">
                          {feedback.map((feedback, idx) => {
                            return (
                              <button
                                key={idx}
                                className="box-button-outline-gray border-neutral-3 text-xsmall text-gray-80 cursor-pointer rounded-lg border px-2 py-1"
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

            {isLoading && (
              <div className="text-gray-40 mx-auto w-193.25 animate-pulse pb-10">
                <RagAnswerSkeleton />
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
                <button className="box-button-outline-gray cursor-pointer rounded-full p-1.5">
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
