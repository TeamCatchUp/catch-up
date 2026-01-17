'use client';

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
import Copy from '/public/icons/icon/copy.svg';
import ThumbsDown from '/public/icons/icon/thumbs-down.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import Cancel from '/public/icons/icon/cancel.svg';
import Filter from '/public/icons/icon/filter-2.svg';
import FilterComponent from '@/components/rag/answerComponent/Filter';
import RagContentHeader from '@/components/rag/answerComponent/RagContentHeader';
import RagRightAdditionalHeader from '@/components/rag/rightComponent/sourceComponent/RagRightAdditionalHeader';
import SourceComponent from '@/components/rag/rightComponent/sourceComponent/SourceComponent';
import DetailedTasksComponent from '@/components/rag/rightComponent/detailedTasksComponent/DetailedTasksComponent';
import { useParams, useSearchParams } from 'next/navigation';
import { sendChatQuery } from 'src/util/sendChatQuery';
import AnswerActionButtons from '@/components/rag/answerComponent/AnswerActionButtons';
import RagAnswerSkeleton from '@/components/Skeleton/RagAnswerSkeleton';
import ErrorResponse from '@/components/rag/answerComponent/ErrorResponse';

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
  const [isError, setIsError] = useState(false);

  const params = useParams();
  const searchParams = useSearchParams();
  const sessionId = params.sessionId as string;
  const repo = searchParams.get('repo');
  const [chatData, setChatData] = useState<any>(null);

  const initialQuery = searchParams.get('q');

  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');

  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<{ [key: number]: boolean }>({});
  const [isMultiLine, setIsMultiLine] = useState(false);
  const [feedbackSubmittedMap, setFeedbackSubmittedMap] = useState<{ [key: number]: boolean }>({});
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const [activeTab, setActiveTab] = useState<'source' | 'detail'>('source');

  const [newInput, setNewInput] = useState('');
  const previousLengthRef = useRef(0);

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
      setIsError(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!newInput.trim() || isLoading || !chatData) return;

    const safeRepo = repo || chatData.repo || '';

    const userMessage = { role: 'user', content: newInput, timestamp: new Date().toISOString() };
    const updatedData = {
      ...chatData,
      messages: [...(chatData.messages || []), userMessage],
    };

    setChatData(updatedData);
    setNewInput('');
    setIsMultiLine(false);
    setIsLoading(true);
    previousLengthRef.current = 0;

    if (textAreaRef.current) {
      textAreaRef.current.style.height = 'auto';
    }

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
      setIsError(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewInput(e.target.value);

    const currentLength = e.target.value.length;
    const isTyping = currentLength > previousLengthRef.current;
    previousLengthRef.current = currentLength;

    // !multiLine의 maxHeight(26px) 제약에서 스크롤이 생기는지 확인
    e.target.style.height = 'auto';
    e.target.style.maxHeight = '26px'; // !multiLine의 maxHeight
    const hasOverflow = e.target.scrollHeight > e.target.clientHeight;

    // 높이 복원
    e.target.style.maxHeight = isMultiLine ? '114px' : '26px';
    e.target.style.height = 'auto';
    const finalHeight = e.target.scrollHeight;
    e.target.style.height = Math.min(finalHeight, 114) + 'px';

    let shouldBeMultiLine;

    if (!isMultiLine) {
      // !multiLine 상태: 스크롤 생기면 multiLine으로
      shouldBeMultiLine = hasOverflow;
    } else {
      // multiLine 상태: 삭제 중일 때만 스크롤 없으면 !multiLine으로
      if (isTyping) {
        shouldBeMultiLine = true; // 입력 중이면 multiLine 유지
      } else {
        shouldBeMultiLine = hasOverflow; // 삭제 중: 스크롤 없으면 !multiLine으로
      }
    }

    if (shouldBeMultiLine !== isMultiLine) {
      setIsMultiLine(shouldBeMultiLine);
      setTimeout(() => {
        if (textAreaRef.current) {
          textAreaRef.current.focus();
          const length = textAreaRef.current.value.length;
          textAreaRef.current.setSelectionRange(length, length);
        }
      }, 0);
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

            {chatData.messages.map((msg: any, idx: number) => (
              <div key={idx} className="mx-auto flex w-193.25 flex-col gap-6">
                {msg.role === 'user' ? (
                  <div className="flex flex-col gap-4">
                    <div className="group relative max-w-full">
                      <span className="text-heading-xlarge text-gray-70 mr-5">{msg.content}</span>
                      <button className="border-neutral-3 box-button-outline-gray inline-flex translate-y-1 cursor-pointer justify-center gap-1 rounded-lg border px-2 py-1 opacity-0 transition-opacity group-hover:opacity-100">
                        <EditPencil className="text-gray-70 h-5 w-5" />
                        <span className="text-body-xsmall text-gray-80 whitespace-nowrap">수정하기</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <div className={`mb-3 rounded-xl ${isFilterOpen ? 'border-neutral-3 border' : ''} `}>
                      {!isFilterOpen ? (
                        <div className="flex items-center gap-1">
                          <div className="icon-button-only-gray flex cursor-pointer items-center gap-1">
                            <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                              스페이스명 text text text
                            </div>
                            <DropDown className="text-gray-70 relative bottom-px h-4 w-4 shrink-0" />
                          </div>
                          <Divider className="text-neutral-4 h-6 w-6 shrink-0" />
                          <div className="flex shrink-0 items-center gap-3">
                            <span className="text-body-xsmall text-gray-50">답변 세부 필터</span>
                            <button onClick={() => setIsFilterOpen(true)} className="cursor-pointer">
                              <ToggleOff />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-2">
                          <div className="icon-button-only-gray flex cursor-pointer items-center gap-1">
                            <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                              스페이스명 text text text
                            </div>
                            <DropDown className="text-gray-70 relative bottom-px h-4 w-4 shrink-0" />
                          </div>
                          <FilterComponent isOpen={isFilterOpen} onClose={() => setIsFilterOpen(false)} />
                        </div>
                      )}
                    </div>
                    <div className="text-gray-80 prose prose-neutral max-w-none break-words">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content.replace(/\\n/g, '\n')}</ReactMarkdown>
                    </div>
                    <div className="text-body-small text-gray-30">
                      질문과 연관된 {msg.sources?.length || 0}개의 핵심 자료를 선별했어요.
                    </div>

                    <AnswerActionButtons
                      icons={icon}
                      messageIdx={idx}
                      feedbackVisibleMap={feedbackVisibleMap}
                      setFeedbackVisibleMap={setFeedbackVisibleMap}
                    />
                    {feedbackVisibleMap[idx] && (
                      <div
                        ref={feedbackRef}
                        className="border-neutral-4 mx-auto flex w-193.25 flex-col gap-4 rounded-xl border p-4"
                      >
                        {feedbackSubmittedMap[idx] ? (
                          <div className="text-body-small flex items-center justify-center text-gray-50">
                            피드백을 주셔서 감사합니다!
                          </div>
                        ) : (
                          <>
                            <div className="flex justify-between">
                              <span className="text-body-small text-gray-50">
                                답변이 마음에 들지 않은 이유가 무엇인가요?
                              </span>
                              <div
                                onClick={() => setFeedbackVisibleMap((prev) => ({ ...prev, [idx]: false }))}
                                className="icon-button-only-gray flex cursor-pointer items-center rounded-full p-0.5"
                              >
                                <Cancel className="h-4.5 w-4.5 text-gray-50" />
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-x-2.5 gap-y-1.5">
                              {feedback.map((feedback, idx) => {
                                return (
                                  <button
                                    key={idx}
                                    onClick={() => {
                                      setFeedbackSubmittedMap((prev) => ({ ...prev, [idx]: true }));
                                      setTimeout(() => {
                                        setFeedbackVisibleMap((prev) => ({
                                          ...prev,
                                          [idx]: false,
                                        }));
                                      }, 3000);
                                    }}
                                    className="box-button-outline-gray border-neutral-3 text-xsmall text-gray-80 cursor-pointer rounded-lg border px-2 py-1"
                                  >
                                    {feedback.content}
                                  </button>
                                );
                              })}
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {isLoading && !isError && (
              <div className="text-gray-40 mx-auto w-193.25 animate-pulse pb-10">
                <RagAnswerSkeleton />
              </div>
            )}

            {!isLoading && isError && (
              <div className="mx-auto w-193.25 pb-10">
                <ErrorResponse
                  icons={icon}
                  messageIdx={chatData.messages.length}
                  feedbackVisibleMap={feedbackVisibleMap}
                  setFeedbackVisibleMap={setFeedbackVisibleMap}
                />
              </div>
            )}
          </div>

          <div className="w-full flex-none bg-white px-24 pt-4 pb-8">
            <div className="mx-auto w-193.25">
              <div className="no-scrollbar flex justify-start gap-2.5 overflow-x-auto">
                {/* {[
                  '임직원이 가장 많이 물어보는 질문',
                  '프로젝트 검색하기',
                  '최근 변경사항 요약',
                  '이 업무 한 줄 요약',
                ].map((item, index) => (
                  <button
                    key={index}
                    className="border-blue-30 bg-blue-1 text-body-small hover:bg-blue-5 active:border-blue-45 text-blue-55 cursor-pointer rounded-full border px-3 py-1.5 whitespace-nowrap"
                  >
                    {item}
                  </button>
                ))} */}
              </div>

              {!isMultiLine ? (
                <div className="border-neutral-4 shadow-rag-bar flex items-center gap-2 rounded-full border bg-white px-3 py-2.5">
                  <div className="group relative">
                    <button className="icon-button-only-gray cursor-pointer rounded-full! p-1.5">
                      <Add className="text-gray-70 h-7 w-7" />
                    </button>
                    <div className="shadow-tooltip bg-alpha-black-75 text-label-small pointer-events-none absolute top-11 left-1/2 -translate-x-1/2 rounded-lg px-2.5 py-1.5 whitespace-nowrap text-white opacity-0 transition-opacity group-hover:opacity-100">
                      파일 추가 및 기타
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
                    className="text-body-medium placeholder:text-gray-30 flex-1 resize-none overflow-hidden outline-none"
                    style={{ height: 'auto', minHeight: '26px', maxHeight: '26px' }}
                  />
                  <div className="flex shrink-0 items-center gap-3">
                    <div className="box-button-outline-gray flex h-7 cursor-pointer items-center justify-center gap-1 px-1.5 py-1">
                      <Filter className="relative top-0.5 h-4.5 w-4.5" />
                      <span className="text-body-xsmall text-gray-50">필터</span>
                    </div>
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
              ) : (
                <div className="border-neutral-4 shadow-rag-bar flex flex-col gap-2 rounded-3xl border bg-white px-3 py-2.5">
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
                    className="text-body-medium placeholder:text-gray-30 w-full resize-none overflow-hidden overflow-y-auto px-2.5 outline-none"
                    style={{ height: 'auto', minHeight: '26px', maxHeight: '114px' }}
                  />
                  <div className="flex w-full items-center">
                    <div className="group relative">
                      <button className="icon-button-only-gray cursor-pointer rounded-full! p-1.5">
                        <Add className="text-gray-70 h-7 w-7" />
                      </button>
                      <div className="shadow-tooltip bg-alpha-black-75 text-label-small pointer-events-none absolute top-11 left-1/2 -translate-x-1/2 rounded-lg px-2.5 py-1.5 whitespace-nowrap text-white opacity-0 transition-opacity group-hover:opacity-100">
                        파일 추가 및 기타
                      </div>
                    </div>
                    <div className="flex-1" />
                    <div className="flex shrink-0 items-center gap-3">
                      <div className="box-button-outline-gray flex h-7 cursor-pointer items-center justify-center gap-1 px-1.5 py-1">
                        <Filter className="relative top-0.5 h-4.5 w-4.5" />
                        <span className="text-body-xsmall text-gray-50">필터</span>
                      </div>
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
              )}
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
