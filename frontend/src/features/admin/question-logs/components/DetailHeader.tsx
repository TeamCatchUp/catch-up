'use client';

import Link from 'next/link';

import ArrowLeft from '@/public/icons/icon/arrow_left.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { Button } from '@/shared/components/ui/button';
import { Separator } from '@/shared/components/ui/separator';

interface DetailHeaderProps {
  userId: string;
  userName: string;
  userDepartment: string;
  /** 진입 경로 (감사 로그에서 진입 시 'audit-logs') */
  from?: string;
}

/** 질문 로그 상세 — 헤더 (타이틀 + 유저 정보 + 목록 복귀) */
export default function DetailHeader({ userName, userDepartment, from }: DetailHeaderProps) {
  const backHref = from === 'audit-logs' ? '/admin/audit-logs?tab=question' : '/admin/question-logs';

  return (
    <div className="flex flex-col gap-6">
      {/* 타이틀 + 유저 정보 */}
      <div className="flex items-center gap-2.5">
        <h1 className="text-heading-xlarge text-text-normal-strong shrink-0">이용자 질문 기록</h1>
        <Separator orientation="vertical" className="h-6" />
        <div className="flex min-w-0 items-center gap-3">
          <DefaultProfile className="text-text-normal-assistive size-7 shrink-0 rounded-full" />
          <span className="text-body-small text-text-normal-neutral truncate">
            {userName} ({userDepartment})
          </span>
        </div>
      </div>

      <Separator />

      {/* 전체 목록 보기 */}
      <div className="flex items-center">
        <Button variant="text-secondary-mono" size="md" asChild>
          <Link href={backHref}>
            <ArrowLeft className="size-5" />
            전체 목록 보기
          </Link>
        </Button>
      </div>
    </div>
  );
}
