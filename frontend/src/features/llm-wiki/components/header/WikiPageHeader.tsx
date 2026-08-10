import { Fragment, type ReactNode } from 'react';

import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import { cn } from '@/shared/utils/cn';

import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import { BREADCRUMB_ICON } from '../breadcrumbIcons';

interface WikiPageHeaderCommonProps {
  /**
   * 우측 액션 슬롯. ⋯ 메뉴 항목·문서 넘기기·미리보기 동작은 전부 소비처가 정한다 —
   * 메뉴 내용 시안이 없으므로 헤더는 자리와 간격(gap 8)만 책임진다.
   */
  actions?: ReactNode;
}

interface WikiPageHeaderMainProps extends WikiPageHeaderCommonProps {
  /** 대시보드(17600:149328) — Header/state=Main */
  variant: 'main';
  /** 제목 앞 아이콘. 화면마다 갈릴 수 있어 주입받는다(대시보드=icon/dashboard) */
  icon?: ReactNode;
  title: string;
}

interface WikiPageHeaderDetailProps extends WikiPageHeaderCommonProps {
  /**
   * 폴더(17762:104786)·문서(17922:56420)·검토큐 문서(17930:57154) — Header/state=세부페이지_2단이상.
   * 채널 화면도 여기에 속한다(사용자 확정 8/10) — 마디가 1개뿐인 체인이다.
   */
  variant: 'detail';
  /**
   * 마지막 마디가 현재 페이지다 — 강조되고 클릭되지 않는다.
   * 마디가 1개면 그 하나가 현재 페이지이고 구분자는 그려지지 않는다(채널 화면).
   */
  breadcrumbs: readonly DocumentBreadcrumb[];
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
  /** 현재 페이지 옆 태그 슬롯. 확정 시안은 검토큐의 "검토 필요" 1종 — DocumentStatusBadge가 공급한다 */
  badge?: ReactNode;
}

export type WikiPageHeaderProps = WikiPageHeaderMainProps | WikiPageHeaderDetailProps;

/**
 * LLM Wiki 5개 화면의 공용 페이지 헤더.
 *
 * Figma가 `Header` 컴포넌트 세트(585:7525)의 두 state로 모델링한 구조를 그대로 옮겼다.
 * 셸(높이·테두리·좌우 배치·우측 슬롯)은 공유하고 좌측 콘텐츠와 좌우 패딩만 갈린다.
 *
 * - main: 아이콘 24 + 17px 제목. breadcrumb가 아니다(마디가 버튼이 아니고 타이포도 다르다)
 * - detail: 15px breadcrumb 체인. 이전 마디는 버튼, 마지막 마디는 현재 페이지
 *
 * 리포 선례와 같은 셸이다 — AgentStudioHeader가 main, RagContentHeader가 detail에 해당하고
 * 둘 다 `h-13 justify-between border-b py-2`에 패딩만 px-16 / px-6으로 갈린다.
 */
export default function WikiPageHeader(props: WikiPageHeaderProps) {
  const { variant, actions } = props;

  return (
    <header
      className={cn(
        // 높이 52 = py 8×2 + 내용물 36(Icon button·Text Button). 두 state가 같은 값이다.
        // gap 20은 detail의 breadcrumbs↔액션 간격이고, main은 Figma에 gap 정의가 없어(hug 콘텐츠에
        // justify-between뿐) 같은 값을 최소 간격으로 함께 쓴다.
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

                  {/* Text Button(582:3810) Secondary Mono / size=large_{이전,현재}페이지.
                      코드 Button의 text-secondary-mono는 어느 size도 이 규격이 아니라(lg는 17px·
                      rounded-full, md는 Medium) 직접 그린다 — RagContentHeader와 같은 판단이다.
                      높이 36은 padding(4)+라인박스(22.5)로는 안 나오는 Figma 고정값이라 h-9로 못박는다. */}
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
