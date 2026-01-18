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
import EditMessageInput from '@/components/rag/EditMessageInput';
import ToolTip from '@/components/common/ToolTip';
import TeamSpaceModal from '@/components/rag/modal/TeamSpaceModal';

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
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);

  const initialQuery = searchParams.get('q');

  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');

  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<{ [key: string]: boolean }>({});
  const [isMultiLine, setIsMultiLine] = useState(false);
  const [feedbackSubmittedMap, setFeedbackSubmittedMap] = useState<{ [key: string]: boolean }>({});
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [isSpaceDropDownOpen, setIsSpaceDropDownOpen] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

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
      messages: [{ id: crypto.randomUUID(), role: 'user', content: query, timestamp: new Date().toISOString() }],
    };
    setChatData(initialData);

    try {
      const result = await sendChatQuery(query, sessionId, safeRepo);

      const finalData = {
        ...initialData,
        messages: [
          ...initialData.messages,
          {
            id: crypto.randomUUID(),
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

    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: newInput,
      timestamp: new Date().toISOString(),
    };
    const updatedData = {
      ...chatData,
      messages: [...(chatData.messages || []), userMessage],
    };

    setChatData(updatedData);
    setNewInput('');
    setIsLoading(true);
    setIsMultiLine(false);

    // textarea 높이 초기화
    if (textAreaRef.current) {
      textAreaRef.current.style.height = '26px';
    }

    try {
      const result = await sendChatQuery(newInput, sessionId, safeRepo);

      const assistantMessage = {
        id: crypto.randomUUID(),
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

    const messageIndex = chatData.messages.findIndex((m: any) => m.id === messageId);
    if (messageIndex === -1) return;

    // 수정된 메시지 이후의 모든 메시지 삭제
    const newMessages = chatData.messages.slice(0, messageIndex);

    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: newContent,
      timeStamp: new Date().toISOString(),
    };

    const updatedData = {
      ...chatData,
      messages: [...newMessages, userMessage],
    };

    setChatData(updatedData);
    setEditingMessageId(null);
    setIsLoading(true);

    try {
      const safeRepo = repo || chatData.repo || '';
      const result = await sendChatQuery(newContent, sessionId, safeRepo);

      const assistantMessage = {
        id: crypto.randomUUID(),
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
    } catch (err) {
      setIsError(true);
    } finally {
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
                    {/* <div className={`mb-3 rounded-xl ${isFilterOpen ? 'border-neutral-3 border' : ''} `}> */}
                    <div className={`mb-3 rounded-xl`}>
                      {!isFilterOpen ? (
                        // <div className="flex items-center gap-1">
                        //   <div className="icon-button-only-gray flex cursor-pointer items-center gap-1">
                        //     <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                        //       스페이스명 text text text
                        //     </div>
                        //     <DropDown className="text-gray-70 relative bottom-px h-4 w-4 shrink-0" />
                        //   </div>
                        //   <Divider className="text-neutral-4 h-6 w-6 shrink-0" />
                        //   <div className="flex shrink-0 items-center gap-3">
                        //     <span className="text-body-xsmall text-gray-50">답변 세부 필터</span>
                        //     <button onClick={() => setIsFilterOpen(true)} className="cursor-pointer">
                        //       <ToggleOff />
                        //     </button>
                        //   </div>
                        // </div>
                        <div className="relative flex items-center gap-1">
                          <div className="group relative flex items-center gap-1">
                            <div
                              onClick={(e) => {
                                e.stopPropagation();
                                setIsSpaceDropDownOpen((prev) => !prev);
                              }}
                              className={clsx(
                                'icon-button-only-gray flex cursor-pointer items-center gap-1 px-2 py-1',
                                isSpaceDropDownOpen ? 'bg-neutral-3' : 'icon-button-only-gray',
                              )}
                            >
                              <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                                스페이스명 text text text
                              </div>
                              <DropDown
                                className={clsx(
                                  'text-gray-70 relative bottom-px h-4 w-4 shrink-0',
                                  isSpaceDropDownOpen ? 'rotate-180' : '',
                                )}
                              />
                            </div>
                            <div className="absolute bottom-12.5 left-23.75">
                              <ToolTip text={'답변 기준 팀스페이스 변경하기'} />
                            </div>
                          </div>
                          {/* TeamSpace 드롭다운 모달 */}
                          {isSpaceDropDownOpen && (
                            <div className="absolute top-10.5 z-100">
                              <TeamSpaceModal
                                onClose={() => {
                                  setIsSpaceDropDownOpen(false);
                                }}
                              />
                            </div>
                          )}
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
                          {/* <div className="icon-button-only-gray flex cursor-pointer items-center gap-1">
                            <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                              스페이스명 text text text
                            </div>
                            <DropDown className="text-gray-70 relative bottom-px h-4 w-4 shrink-0" />
                          </div> */}
                          <div className="relative flex gap-1">
                            <div className="group relative w-fit gap-1">
                              <div
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setIsSpaceDropDownOpen((prev) => !prev);
                                }}
                                className={clsx(
                                  'flex cursor-pointer items-center gap-1 px-2 py-1',
                                  isSpaceDropDownOpen ? 'bg-neutral-3 rounded-lg' : 'icon-button-only-gray',
                                )}
                              >
                                <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                                  스페이스명 text text text
                                </div>
                                <DropDown
                                  className={clsx(
                                    'text-gray-70 relative bottom-px h-4 w-4 shrink-0',
                                    isSpaceDropDownOpen ? 'rotate-180 rounded-lg' : '',
                                  )}
                                />
                              </div>
                              <div className="absolute bottom-10.5 left-23.75">
                                <ToolTip text={'답변 기준 팀스페이스 변경하기'} />
                              </div>
                            </div>
                            {/* TeamSpace 드롭다운 모달 */}
                            {isSpaceDropDownOpen && (
                              <div className="absolute top-10 z-100">
                                <TeamSpaceModal
                                  onClose={() => {
                                    setIsSpaceDropDownOpen(false);
                                  }}
                                />
                              </div>
                            )}
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
                      messageIdx={msg.id}
                      feedbackVisibleMap={feedbackVisibleMap}
                      setFeedbackVisibleMap={setFeedbackVisibleMap}
                    />
                    {feedbackVisibleMap[msg.id] && (
                      <div
                        ref={feedbackRef}
                        className="border-neutral-4 mx-auto flex w-193.25 flex-col gap-4 rounded-xl border p-4"
                      >
                        {feedbackSubmittedMap[msg.id] ? (
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
                                onClick={() => setFeedbackVisibleMap((prev) => ({ ...prev, [msg.id]: false }))}
                                className="icon-button-only-gray flex cursor-pointer items-center rounded-full p-0.5"
                              >
                                <Cancel className="h-4.5 w-4.5 text-gray-50" />
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-x-2.5 gap-y-1.5">
                              {feedback.map((feedbackItem, feedbackIdx) => {
                                return (
                                  <button
                                    key={feedbackIdx}
                                    onClick={() => {
                                      setFeedbackSubmittedMap((prev) => ({ ...prev, [msg.id]: true }));
                                      setTimeout(() => {
                                        setFeedbackVisibleMap((prev) => ({
                                          ...prev,
                                          [msg.id]: false,
                                        }));
                                      }, 3000);
                                    }}
                                    className="box-button-outline-gray border-neutral-3 text-xsmall text-gray-80 cursor-pointer rounded-lg border px-2 py-1"
                                  >
                                    {feedbackItem.content}
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
              {/* <div className="no-scrollbar flex justify-start gap-2.5 overflow-x-auto">
                {[
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
                ))}
              </div> */}

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
                  {!newInput.trim() && (
                    <div className="box-button-outline-gray flex h-7 cursor-pointer items-center justify-center gap-1 px-1.5 py-1">
                      <Filter className="relative top-0.5 h-4.5 w-4.5" />
                      <span className="text-body-xsmall text-gray-50">필터</span>
                    </div>
                  )}
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
