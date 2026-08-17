import { Fragment, type ReactNode } from 'react';

import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import { cn } from '@/shared/utils/cn';

import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import { BREADCRUMB_ICON } from '../breadcrumbIcons';

interface WikiPageHeaderCommonProps {
  /** 우측 액션 슬롯. 내용물과 동작은 전부 소비처가 정하고, 헤더는 자리와 간격만 책임진다. */
  actions?: ReactNode;
}

interface WikiPageHeaderMainProps extends WikiPageHeaderCommonProps {
  /** 대시보드형 — 아이콘 + 제목 */
  variant: 'main';
  /** 제목 앞 아이콘. 화면마다 갈려서 주입받는다 */
  icon?: ReactNode;
  title: string;
}

interface WikiPageHeaderDetailProps extends WikiPageHeaderCommonProps {
  /** 세부 페이지형 — 채널·폴더·문서·검토큐가 쓴다. 채널은 마디가 1개뿐인 체인이다. */
  variant: 'detail';
  /** 마지막 마디가 현재 페이지다 — 강조되고 클릭되지 않는다. */
  breadcrumbs: readonly DocumentBreadcrumb[];
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
  /** 현재 페이지 옆 태그 슬롯. DocumentStatusBadge가 공급한다 */
  badge?: ReactNode;
}

export type WikiPageHeaderProps = WikiPageHeaderMainProps | WikiPageHeaderDetailProps;

/**
 * LLM Wiki 화면들의 공용 페이지 헤더. 셸은 공유하고 좌측 콘텐츠와 좌우 패딩만 variant로 갈린다.
 * main은 아이콘 + 제목, detail은 breadcrumb 체인(이전 마디는 버튼, 마지막은 현재 페이지)이다.
 */
export default function WikiPageHeader(props: WikiPageHeaderProps) {
  const { variant, actions } = props;

  return (
    <header
      className={cn(
        // 높이·gap은 두 variant가 공유한다 — 화면 간 헤더 리듬이 어긋나지 않게.
        'border-line-normal-neutral flex h-13 shrink-0 items-center justify-between gap-5 border-b py-2',
        variant === 'main' ? 'px-16' : 'px-6',
      )}
    >
      {/* 좌측 — 이 헤더에서 폭을 흡수하는 유일한 슬롯 */}
      {variant === 'main' ? (
        <div className="flex min-w-0 items-center gap-2">
          {props.icon && <span className="text-icon-normal-normal flex shrink-0 [&_svg]:size-6">{props.icon}</span>}
          <span className="text-heading-medium text-text-normal-normal truncate">{props.title}</span>
        </div>
      ) : (
        <div className="flex min-w-0 items-center gap-2">
          <nav aria-label="현재 위치" className="flex min-w-0 items-center">
            {props.breadcrumbs.map((crumb, index) => {
              const isCurrent = index === props.breadcrumbs.length - 1;
              const CrumbIcon = BREADCRUMB_ICON[crumb.kind];

              return (
                <Fragment key={`${crumb.kind}-${crumb.label}`}>
                  {index > 0 && <IconArrowRight2 aria-hidden className="text-icon-normal-neutral size-5 shrink-0" />}

                  {/* 공용 Button에 이 마디 규격의 variant가 없어 직접 그린다.
                      높이는 padding에서 파생되지 않는 고정값이라 h-9로 못박는다. */}
                  {isCurrent ? (
                    <span
                      aria-current="page"
                      className="text-heading-small text-text-normal-normal flex h-9 min-w-0 items-center gap-1.5 px-2"
                    >
                      {CrumbIcon && <CrumbIcon aria-hidden className="size-5 shrink-0" />}
                      <span className="truncate">{crumb.label}</span>
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => props.onBreadcrumbClick?.(crumb, index)}
                      className="text-heading-small text-text-normal-alternative hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-pressed flex h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-2 transition-colors"
                    >
                      {CrumbIcon && <CrumbIcon aria-hidden className="size-5 shrink-0" />}
                      <span className="truncate">{crumb.label}</span>
                    </button>
                  )}
                </Fragment>
              );
            })}
          </nav>

          {props.badge && <div className="shrink-0">{props.badge}</div>}
        </div>
      )}

      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}
