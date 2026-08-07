'use client';

import { type ComponentType, type SVGProps, useState } from 'react';

import IconCaret from '@/public/icons/icon/arrow_right.svg';
import IconDepthConnector from '@/public/icons/icon/arrow_right2.svg';
import { cn } from '@/shared/utils/cn';

export interface NavTreeNode {
  id: string;
  label: string;
  /** 행 앞 아이콘. 채널/폴더/문서 같은 의미는 이 컴포넌트가 모른다 — 소비처가 넣는다 */
  Icon?: ComponentType<SVGProps<SVGSVGElement>>;
  children?: readonly NavTreeNode[];
}

interface NavTreeProps {
  nodes: readonly NavTreeNode[];
  /** 현재 위치 하이라이트 (탐색형 전용) */
  activeId?: string;
  /** 처음부터 펼쳐둘 노드 (탐색형 전용 — 표시형은 항상 전체 펼침) */
  defaultExpandedIds?: readonly string[];
  /** 미전달 시 정적 표시 모드: 전체 펼침 고정, 토글·클릭 불가 (문서 위치 표시형) */
  onNodeClick?: (id: string) => void;
  className?: string;
}

/**
 * 탐색형 들여쓰기 단위.
 * Figma SNB 프로젝트 섹션(17578:127214 > 17884:15677)에서 depth 0/1/2 행의 x가 0/20/40이다.
 */
const INTERACTIVE_INDENT_PX = 20;

/**
 * 표시형 들여쓰기 단위.
 * Figma 문서 위치(17564:127054)에서 depth 0/1 행의 x가 0/16이다.
 */
const STATIC_INDENT_PX = 16;

/**
 * depth·아이콘·라벨·접기·active만 아는 프레젠테이션 트리.
 *
 * 두 곳이 같은 구조를 쓴다:
 * - SNB 프로젝트 섹션 — 탐색형. 행을 누르면 접히고 현재 위치가 하이라이트된다.
 * - 검토 큐 "문서 위치" — 표시형. `onNodeClick`을 넘기지 않으면 이 모드가 된다.
 *
 * 탐색형 행의 형상(h 36 / px 10 / gap 12 / radius 8 / 아이콘 슬롯 22)은 Figma에서
 * `SNB/menu` 인스턴스이며 {@link ../layout/panels/SnbMenuItem SnbMenuItem}과 같다.
 * 그래도 SnbMenuItem을 재사용하지 않은 이유는 두 가지다 — (1) 트리 행의 아이콘 색이
 * Icon/Normal/Neutral로 Primary Nav 쪽 Icon/Normal/Normal과 다르고, (2) 표시형은
 * 버튼이 아닌 마크업이라 어차피 별도 행 렌더러가 필요하다. SNB/menu 형상이 바뀌면
 * 두 파일을 같이 고쳐야 한다.
 */
export default function NavTree({ nodes, activeId, defaultExpandedIds, onNodeClick, className }: NavTreeProps) {
  const isStatic = onNodeClick === undefined;
  const [expandedIds, setExpandedIds] = useState<ReadonlySet<string>>(() => new Set(defaultExpandedIds));

  const toggle = (id: string) =>
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const renderRow = (node: NavTreeNode, depth: number, hasChildren: boolean, expanded: boolean) => {
    const label = (
      <span className="text-body-small text-text-normal-normal min-w-0 truncate text-left">{node.label}</span>
    );

    if (isStatic) {
      return (
        <span className="flex h-7 items-center gap-2" style={{ paddingInlineStart: depth * STATIC_INDENT_PX }}>
          {depth > 0 && (
            <IconDepthConnector
              data-slot="nav-tree-depth-connector"
              aria-hidden
              className="text-icon-normal-neutral size-6 shrink-0"
            />
          )}
          {node.Icon && <node.Icon aria-hidden className="text-icon-normal-normal size-6 shrink-0" />}
          {label}
        </span>
      );
    }

    return (
      <div style={{ paddingInlineStart: depth * INTERACTIVE_INDENT_PX }}>
        <div
          data-slot="nav-tree-row"
          className={cn(
            'group flex h-9 items-center gap-3 rounded-lg px-2.5 py-1.5 transition-colors',
            /*
             * SnbMenuItem과 같은 근거 — Figma는 상태를 알파 오버레이로 구분하지만 코드의
             * interaction 토큰은 아직 solid neutral 세대라 상대 순서(hover < pressed)만 지킨다.
             * 행이 더 이상 버튼이 아니라서 pressed는 내부 버튼의 :active를 has()로 받는다.
             */
            'hover:bg-fill-normal-interaction-hover has-[button:active]:bg-fill-normal-interaction-pressed',
          )}
        >
          {/*
           * 캐럿 대상 행은 Icon 유무와 무관하게 22px 슬롯을 예약한다.
           * 슬롯이 없으면 hover에 캐럿이 생기면서 라벨이 22px 밀린다.
           */}
          {(hasChildren || node.Icon) && (
            <span className="relative flex size-5.5 shrink-0 items-center justify-center">
              {node.Icon && (
                <node.Icon
                  aria-hidden
                  className={cn(
                    'text-icon-normal-neutral size-5.5',
                    hasChildren && 'group-focus-within:hidden group-hover:hidden',
                  )}
                />
              )}
              {hasChildren && (
                <button
                  type="button"
                  aria-label={`${node.label} ${expanded ? '접기' : '펼치기'}`}
                  aria-expanded={expanded}
                  onClick={() => toggle(node.id)}
                  className="text-icon-normal-neutral hover:bg-fill-normal-interaction-hover absolute hidden size-5.5 cursor-pointer items-center justify-center rounded-full group-focus-within:flex group-hover:flex"
                >
                  <IconCaret aria-hidden className={cn('size-4.5 transition-transform', expanded && 'rotate-90')} />
                </button>
              )}
            </span>
          )}

          <button
            type="button"
            aria-current={node.id === activeId ? 'page' : undefined}
            onClick={() => onNodeClick(node.id)}
            // 라벨 span이 flex 아이템이어야 truncate가 동작한다 — 인라인이면 overflow가 무시된다
            className="flex min-w-0 flex-1 cursor-pointer"
          >
            {label}
          </button>
        </div>
      </div>
    );
  };

  const renderNode = (node: NavTreeNode, depth: number) => {
    const hasChildren = Boolean(node.children?.length);
    // 표시형은 접을 수 없다 — 경로 조각을 보여주는 것이 전부라 접을 이유가 없다
    const expanded = isStatic || expandedIds.has(node.id);

    return (
      <li key={node.id} className={cn(isStatic && 'flex flex-col gap-2')}>
        {renderRow(node, depth, hasChildren, expanded)}
        {hasChildren && expanded ? renderList(node.children ?? [], depth + 1) : null}
      </li>
    );
  };

  const renderList = (items: readonly NavTreeNode[], depth: number) => (
    // 표시형 행 간격 8은 Figma 문서 위치 실측값이다. 탐색형은 행이 붙어 있다
    <ul className={cn(isStatic && 'flex flex-col gap-2')}>{items.map((node) => renderNode(node, depth))}</ul>
  );

  return <div className={className}>{renderList(nodes, 0)}</div>;
}
