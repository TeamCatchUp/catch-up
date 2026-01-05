'use client';

import { useState, useRef, useEffect } from 'react';
import Add from '/public/icons/icon/add_small.svg';
import Share from '/public/icons/icon/share_2.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';
import EditPencil from '/public/icons/icon/edit_pencil.svg';
// import Delete from '/public/icons/icon/detete_2.svg';
// import Reset from '/public/icons/icon/reset.svg';
import ArrowSend from '/public/icons/icon/arrow_send.svg';
import Copy from '/public/icons/icon/copy.svg';
import ThumbsDown from '/public/icons/icon/thumbs-down.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import Cancel from '/public/icons/icon/cancel.svg';
import Github from '/public/icons/logo/GitHub.svg';
import ArrowRight from '/public/icons/icon/arrow_right.svg';
import RagContentHeader from '@/components/rag/RagContentHeader';
import RagRightAdditionalHeader from '@/components/rag/RagRightAdditionalHeader';
import SourceComponent from '@/components/rag/SourceComponent';
import DetailedTaskComponent from '@/components/rag/DetailedTaskComponent';

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

const sources = [
  {
    id: 1,
    title: '잠재 파트너사 컨택 관련',
    subtitle: '일본 시장 진출 Kick-off 회의록 text text text text text text',
    content:
      '일본의 DX(Digital Transformation) 수요 증가에 따른 시장 기회 포착.- Goal: 2024년 3분기 내 일본 법인 설립 여부 결정을 위한 근거 데이터(Quantitative/Qualitative) 확보.',
    date: '2025.12.15',
  },
  {
    id: 2,
    title: '잠재 파트너사 컨택 관련',
    subtitle: '일본 시장 진출 Kick-off 회의록',
    content: '일본의 DX(Digital Transformation) 수요 증가에 따른 시장 기회 포착',
    date: '2026.01.02',
  },
];

export default function Page() {
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');

  const [showFeedback, setShowFeedback] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);

  // 오른쪽 컴포넌트 헤더
  const [activeTab, setActiveTab] = useState<'source' | 'detail'>('source');

  // 더미데이터
  const content = {
    title: '지금 일본 시장 진출 프로젝트에서 가장 큰 걸림돌(Blocker)이 뭐야? 그리고 어떻게 해결하고 있어?',
    content: '현재 논의된 핵심 이슈는 일본 경쟁사 A사의 가격 정책에 포함된 숨겨진 비용입니다.',
  };

  const keyword = ['임직원이 가장 많이 물어보는 질문', '프로젝트 검색하기', '최근 변경사항 요약', '이 업무 한 줄 요약'];

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

  return (
    <div className="flex h-screen w-full">
      <div className="flex flex-1 flex-col">
        <div className="flex h-full flex-col bg-white">
          {/* 헤더 */}
          <RagContentHeader />

          {/* 답변 콘텐츠 영역 */}
          <div className="border-r-neutral-3 relative flex flex-1 flex-col justify-center border-r">
            {/* 답변 내용 */}
            <div className="flex flex-1 flex-col gap-8 px-24 pt-3 pb-9">
              {/* 날짜 */}
              <div className="flex h-7 items-center justify-center gap-4">
                <div className="text-neutral-4 w-[347.5px] border" />
                <span className={`body-xsmall outline-gray cursor-pointer rounded-full px-1.5 py-1 text-gray-50`}>
                  {month}.{day}
                </span>
                <div className="text-neutral-4 w-[347.5px] border" />
              </div>

              <div ref={scrollRef} className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 150px)' }}>
                {/* 제목 */}
                <div className="mx-auto mb-8 flex w-[773px] items-center justify-center gap-3">
                  <div className="text-heading-xlarge text-gray-70 h-auto w-[674px] flex-1">{content.title}</div>
                  <button
                    className={`outline-gray border-neutral-3 flex h-7.5 items-center justify-center gap-1 self-end rounded-lg border px-2 py-1`}
                  >
                    <div className="text-gray-70 cursor-pointer">
                      <EditPencil className="text-gray-70 h-5 w-5" />
                    </div>
                    <span className="text-body-xsmall text-gray-80 cursor-pointer">수정하기</span>
                  </button>
                </div>

                {/* 필터링 */}
                <div className="border-neutral-3 mx-auto h-[211px] w-[773px] rounded-xl border"></div>

                {/* 내용 */}
                <div className="mx-auto mt-8 flex h-auto w-[773px] flex-col gap-5">
                  <div className="text-body-medium text-gray-80">{content.content}</div>
                  <div className="text-body-small text-gray-30">질문과 연관된 39개의 핵심 자료를 선별했어요.</div>
                </div>
                {/* 피드백 */}
                <div className="mx-auto mt-5 flex w-[773px] gap-1">
                  {icon.map((item, index) => {
                    const Icon = item.icon;
                    const isThumbsDown = item.name === 'ThumbsDown';
                    const activeClass = isThumbsDown && showFeedback ? 'bg-neutral-3 border-neutral-5' : '';
                    return (
                      <button
                        key={index}
                        onClick={() => {
                          if (isThumbsDown) setShowFeedback((prev) => !prev);
                        }}
                        className={`outline-gray cursor-pointer rounded-lg p-1.5 ${activeClass}`}
                      >
                        <Icon className="h-6 w-6 text-gray-50" />
                      </button>
                    );
                  })}
                </div>
                {showFeedback && (
                  <div
                    ref={feedbackRef}
                    className="border-neutral-4 mx-auto mt-5 flex w-[773px] flex-col gap-4 rounded-xl border p-4"
                  >
                    <div className="flex justify-between">
                      <span className="text-body-small text-gray-50">답변이 마음에 들지 않은 이유가 무엇인가요?</span>
                      <div
                        onClick={() => setShowFeedback(false)}
                        className={`$outline-gray flex cursor-pointer items-center rounded-full p-0.5`}
                      >
                        <Cancel className={`relative bottom-[0.5px] h-4.5 w-4.5 text-gray-50`} />
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-x-2.5 gap-y-1.5">
                      {feedback.map((feedback, idx) => {
                        return (
                          <button
                            key={idx}
                            className={`outline-gray border-neutral-3 text-xsmall text-gray-80 cursor-pointer rounded-lg border px-2 py-1`}
                          >
                            {feedback.content}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
            {/* 검색 */}
            <div className="sticky bottom-0 mx-auto flex w-[773px] flex-col justify-center gap-3 bg-white pb-9">
              <div className="flex justify-start gap-2.5">
                {keyword.map((item, index) => (
                  <div key={index} className="flex pt-4">
                    <button className="border-blue-30 bg-blue-1 hover:bg-blue-5 active:border-blue-45 text-body-small text-blue-55 cursor-pointer rounded-full border px-3 py-1.5">
                      {item}
                    </button>
                  </div>
                ))}
              </div>
              <div className="border-neutral-4 shadow-rag-bar flex w-[773px] items-center gap-2 rounded-full border px-3 py-2.5">
                <button className={`outline-gray flex cursor-pointer items-center rounded-full p-1.5`}>
                  <Add className="text-gray-70 h-7 w-7" />
                </button>
                <input className="flex-1 outline-none" placeholder="업무 흐름이나 인수인계 내용을 질문해보세요" />
                <button className="border-neutral-2 bg-neutral-1 flex cursor-pointer items-center rounded-full border p-2">
                  <ArrowSend className="text-gray-30 h-6 w-6" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 출처 컴포넌트 */}
      <div className="ml-auto flex h-screen w-[405px] justify-end">
        <div className="flex w-full flex-col">
          <RagRightAdditionalHeader activeTab={activeTab} onChange={setActiveTab} sourceCount={sources.length} />
          {/* 컴포넌트 내용 */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === 'source' && <SourceComponent sources={sources} />}
            {activeTab === 'detail' && <DetailedTaskComponent />}
          </div>
        </div>
      </div>
    </div>
  );
}
