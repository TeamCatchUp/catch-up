import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import { cn } from '@/shared/utils/cn';

import type { DocumentBreadcrumb } from '../../types/llmWikiModel';

const LOCATION_ICON = { channel: IconWikiChannel, folder: IconFolder, document: IconFile } as const;

/** 계단 들여쓰기 0/16/32 — 깊이가 그 밑으로 늘면 마지막 단을 그대로 쓴다 */
const INDENT_CLASS = ['pl-0', 'pl-4', 'pl-8'] as const;

interface DocumentLocationCardProps {
  /** 채널 > 폴더 > 문서 순서. 문서 마디가 현재 위치 점을 받는다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
}

/** 우측 패널의 "문서 위치" 카드 — 계단식 경로에 현재 위치(파란 점)를 찍는 정적 표시다. */
export default function DocumentLocationCard({ breadcrumbs }: DocumentLocationCardProps) {
  return (
    <section className="border-line-normal-neutral flex flex-col gap-4 border-b p-4">
      <h3 className="text-body-small text-text-normal-alternative">문서 위치</h3>
      <div className="flex flex-col gap-2">
        {breadcrumbs.map((crumb, index) => {
          const Icon = LOCATION_ICON[crumb.kind as keyof typeof LOCATION_ICON];
          return (
            <div
              key={`${crumb.kind}-${index}`}
              className={cn(
                'flex items-center gap-2 py-1',
                index > 0 && 'pr-1.5',
                INDENT_CLASS[Math.min(index, INDENT_CLASS.length - 1)],
              )}
            >
              {index > 0 && <IconArrowRight2 aria-hidden className="text-icon-normal-assistive size-6 shrink-0" />}
              {crumb.kind === 'document' && (
                <span aria-hidden className="flex size-6 shrink-0 items-center justify-center">
                  <span className="bg-fill-primary-normal-normal size-1.5 rounded-full" />
                </span>
              )}
              <span className="flex min-w-0 items-center gap-3">
                {Icon && <Icon aria-hidden className="text-icon-normal-normal size-5 shrink-0" />}
                <span className="text-body-small text-text-normal-normal truncate">{crumb.label}</span>
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
