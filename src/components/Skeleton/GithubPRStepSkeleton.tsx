'use client';

import clsx from 'clsx';
import { useState, useRef, useEffect, useMemo } from 'react';
import GithubIcon from '/public/icons/logo/GitHub.svg';
import SearchData from '/public/icons/icon/searchData.svg';
import FastForward from '/public/icons/icon/fast_forward.svg';
import CheckCircle from '/public/icons/icon/check_circle.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import ArrowForward from '/public/icons/icon/arrow_forward.svg';
import Check from '/public/icons/icon/check.svg';
import { formatDate } from '@/util/formatDate';

interface GithubPRStepSkeletonProps {
  prList: PRPayload[];
  onContinue: (selectedPrNumbers: number[]) => void;
  onRefetch?: () => void; // 다시 찾기
}

const GithubPRStepSkeleton = ({ prList, onContinue, onRefetch }: GithubPRStepSkeletonProps) => {
  const [selectedPrNumbers, setSelectedPrNumbers] = useState<number[]>([]);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const allPrNumbers = useMemo(() => prList.map((pr) => pr.prNumber), [prList]);

  const toggleSelect = (prNumber: number) => {
    setSelectedPrNumbers((prev) =>
      prev.includes(prNumber) ? prev.filter((v) => v !== prNumber) : [...prev, prNumber],
    );
  };

  const toggleAll = () => {
    const isAllSelected = prList.every((pr) => selectedPrNumbers.includes(pr.prNumber));
    setSelectedPrNumbers(isAllSelected ? [] : allPrNumbers);
  };

  const isActive = selectedPrNumbers.length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    });
  }, []);

  return (
    <>
      <div className="bg-rag-github-pr-mcp flex flex-col gap-8 rounded-3xl px-6 py-5">
        {/* 헤더 */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-5">
            <SearchData />
            <span className="text-heading-large text-gray-90">잠시만요! 정확한 답변을 위해 확인이 필요해요.</span>
            <button
              onClick={() => onContinue([])}
              className="text-button-primary-blue flex cursor-pointer items-center gap-0.5 px-1.5 py-1"
            >
              <span className="text-body-small text-blue-55">건너뛰기</span>
              <FastForward />
            </button>
          </div>
          <span className="text-body-small text-gray-70 flex items-center gap-1">
            <span>관련이 높은 자료가</span>
            <span className="rounded-md2 bg-blue-5 px-1.5 py-0.5 text-blue-50">총 {prList.length}건</span>
            <span>발견되었습니다. 가장 연관성 높은 항목을 선택해 주시면, 상세 내용을 분석해 드릴게요!</span>
          </span>
        </div>
        {/* 내용 */}
        <div className="flex flex-col gap-4">
          {/* 버튼 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={toggleAll}
                className="icon-button-outline-gray flex h-7.5 cursor-pointer items-center gap-1 px-2 py-1"
              >
                <CheckCircle className="text-gray-70 relative bottom-px h-5 w-5 flex-shrink-0" />
                <span className="text-body-xsmall text-gray-80 flex-shrink-0">전체 선택</span>
              </button>
              <button
                // onClick={() => onRefetch?.()}
                className="icon-button-outline-gray flex h-7.5 cursor-pointer items-center gap-1 px-2 py-1"
              >
                <Rotate className="text-gray-70 relative bottom-px h-5 w-5 flex-shrink-0" />
                <span className="text-body-xsmall text-gray-80 flex-shrink-0">다시 찾기</span>
              </button>
            </div>
            <button
              disabled={!isActive}
              onClick={() => onContinue(selectedPrNumbers)}
              className={clsx(
                'flex h-9 w-24.75 gap-1 rounded-lg px-2.5 py-1.5 text-white',
                isActive
                  ? 'hover:bg-blue-55 active:bg-blue-60 disabled:bg-blue-10 cursor-pointer rounded-lg bg-blue-50'
                  : 'bg-blue-10',
              )}
            >
              <span className="text-heading-small relative top-px whitespace-nowrap">진행하기</span>
              <ArrowForward className="h-6 w-6 shrink-0" />
            </button>
          </div>
          {/* 선택 리스트 */}
          <div className="flex w-180.75 flex-col gap-4">
            {prList.map((pr, idx) => {
              const isSelected = selectedPrNumbers.includes(pr.prNumber);

              return (
                <div key={`${pr.owner}/${pr.repoName}#${pr.prNumber}`}>
                  <div className="flex h-28.75 w-full gap-6">
                    <div className="flex h-28.75 items-center">
                      <button
                        onClick={() => toggleSelect(pr.prNumber)}
                        className={clsx(
                          'flex h-8.5 w-8.5 cursor-pointer items-center justify-center rounded-lg border',
                          isSelected ? 'bg-blue-1 border-blue-45' : 'border-neutral-3 bg-neutral-1',
                        )}
                      >
                        <Check className={clsx('h-5.5 w-5.5', isSelected ? 'text-blue-50' : 'text-gray-30')} />
                      </button>
                    </div>
                    <div
                      onClick={() => toggleSelect(pr.prNumber)}
                      className={clsx(
                        'flex h-28.75 w-166.25 cursor-pointer flex-col gap-1.5 rounded-2xl border bg-white px-5 py-4',
                        isSelected ? 'border-blue-30' : 'border-neutral-2',
                      )}
                    >
                      {/* 제목 */}
                      <div className="flex w-156 items-center gap-1.5">
                        <GithubIcon className="h-5.5 w-5.5" />
                        <span className="text-body-medium text-gray-70 truncate">{pr.title}</span>
                      </div>
                      {/* 설명 */}
                      <div className="flex w-156 items-center gap-1.5">
                        <span className="text-heading-small text-gray-80 flex-shrink-0">설명:</span>
                        <span className="text-body-small text-gray-70 max-w-147.25 truncate">
                          {pr.summary || '설명 없음'}
                        </span>
                      </div>
                      {/* 부가정보 */}
                      <div className="text-body-xsmall flex w-156 items-center gap-1.5 text-gray-50">
                        <span className="max-w-95 truncate">{pr.repoName}</span>
                        <div className="bg-neutral-3 h-3.75 w-px" />
                        <span>{formatDate(pr.createdAt)}</span>
                        <div className="bg-neutral-3 h-3.75 w-px" />
                        <span>{pr.owner}</span>
                      </div>
                    </div>
                  </div>
                  {/* divider */}
                  {idx !== prList.length - 1 && <div className="bg-neutral-3 mt-4 h-px w-full" />}
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div ref={bottomRef} />
    </>
  );
};

export default GithubPRStepSkeleton;
