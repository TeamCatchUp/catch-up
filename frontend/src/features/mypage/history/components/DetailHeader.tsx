'use client';

import Link from 'next/link';

import ArrowLeft from '@/public/icons/icon/arrow_left.svg';
import ArrowRight from '@/public/icons/icon/arrow_right.svg';
import { Button } from '@/shared/components/ui/button';

interface DetailHeaderProps {
  sessionId: string;
  prevQuery: string | null;
  nextQuery: string | null;
}

const DetailHeader = ({ sessionId, prevQuery, nextQuery }: DetailHeaderProps) => {
  const buildHref = (q: string) => `/mypage/history/${sessionId}?q=${encodeURIComponent(q)}`;

  return (
    <div className="flex items-center justify-between">
      {/* 전체 목록 보기 */}
      <Button variant="text-secondary-mono" size="md" asChild>
        <Link href="/mypage/history">
          <ArrowLeft className="size-5" />
          전체 목록 보기
        </Link>
      </Button>

      {/* 이전/다음 질문 네비게이션 */}
      <div className="flex items-center gap-1">
        {prevQuery !== null ? (
          <Button variant="text-secondary-mono" size="md" asChild>
            <Link href={buildHref(prevQuery)}>
              <ArrowLeft className="size-5" />
              이전 질문
            </Link>
          </Button>
        ) : (
          <Button variant="text-secondary-mono" size="md" disabled>
            <ArrowLeft className="size-5" />
            이전 질문
          </Button>
        )}

        {nextQuery !== null ? (
          <Button variant="text-secondary-mono" size="md" asChild>
            <Link href={buildHref(nextQuery)}>
              다음 질문
              <ArrowRight className="size-5" />
            </Link>
          </Button>
        ) : (
          <Button variant="text-secondary-mono" size="md" disabled>
            다음 질문
            <ArrowRight className="size-5" />
          </Button>
        )}
      </div>
    </div>
  );
};

export default DetailHeader;
