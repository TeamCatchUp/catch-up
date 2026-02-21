'use client';

import Link from 'next/link';

import ArrowLeft from '@/public/icons/icon/arrow_left.svg';
import ArrowRight from '@/public/icons/icon/arrow_right.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { Button } from '@/shared/components/ui/button';
import { Separator } from '@/shared/components/ui/separator';

interface DetailHeaderProps {
  sessionId: string;
  userId: string;
  userName: string;
  userDepartment: string;
  prevQuery: string | null;
  nextQuery: string | null;
}

/** 질문 로그 상세 — 헤더 (타이틀 + 유저 정보 + 네비게이션) */
const DetailHeader = ({ sessionId, userId, userName, userDepartment, prevQuery, nextQuery }: DetailHeaderProps) => {
  const buildHref = (q: string) =>
    `/admin/question-logs/${sessionId}?q=${encodeURIComponent(q)}&userId=${userId}`;

  return (
    <div className="flex flex-col gap-6">
      {/* 타이틀 + 유저 정보 */}
      <div className="flex items-center gap-2.5">
        <h1 className="text-heading-xlarge text-gray-90 shrink-0">이용자 질문 기록</h1>
        <Separator orientation="vertical" className="h-6" />
        <div className="flex min-w-0 items-center gap-3">
          <DefaultProfile className="border-neutral-2 text-gray-30 size-7 shrink-0 rounded-full border" />
          <span className="text-body-small text-gray-70 truncate tracking-tight">
            {userName} ({userDepartment})
          </span>
        </div>
      </div>

      <Separator />

      {/* 네비게이션 */}
      <div className="flex items-center justify-between">
        <Button variant="text-secondary-mono" size="md" asChild>
          <Link href="/admin/question-logs">
            <ArrowLeft className="size-5" />
            전체 목록 보기
          </Link>
        </Button>

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
    </div>
  );
};

export default DetailHeader;
