'use client';

import { type ComponentType, type SVGProps, useState } from 'react';

import IconAdd from '@/public/icons/icon/add_small_400.svg';
import IconArrowRightFilled from '@/public/icons/icon/arrow_right_filled.svg';
// 표시형 depth 연결자는 꺾쇠, 탐색형 접기 캐럿은 속이 찬 삼각형이다 — 자산이 다르다
import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import IconMore from '@/public/icons/icon/kebab_horizontal_400.svg';
import { cn } from '@/shared/utils/cn';

export interface NavTreeNode {
  id: string;
  label: string;
  /** 행 앞 아이콘. 채널/폴더/문서 같은 의미는 이 컴포넌트가 모른다 — 소비처가 넣는다 */
  Icon?: ComponentType<SVGProps<SVGSVGElement>>;
  children?: readonly NavTreeNode[];
  /** 하위 추가(+) 어포던스를 가질 수 있는 행인가. 무엇을 추가하는지는 소비처가 안다 */
  canAddChild?: boolean;
}

interface NavTreeProps {
  nodes: readonly NavTreeNode[];
  /** 현재 위치 하이라이트 (탐색형 전용) */
  activeId?: string;
  /** 처음부터 펼쳐둘 노드 (탐색형 전용 — 표시형은 항상 전체 펼침) */
  defaultExpandedIds?: readonly string[];
  /** 미전달 시 정적 표시 모드: 전체 펼침 고정, 토글·클릭 불가 (문서 위치 표시형) */
  onNodeClick?: (id: string) => void;
  /** 전달 시 모든 행에 더보기(⋯). 두 번째 인자는 눌린 버튼이라 소비처가 메뉴를 붙일 수 있다 */
  onNodeMore?: (id: string, trigger: HTMLElement) => void;
  /** 전달 시 canAddChild 행에만 하위 추가(+). 인자 규칙은 위와 같다 */
  onNodeAdd?: (id: string, trigger: HTMLElement) => void;
  /** 메뉴가 열려 있는 행. 그 동안 액션이 hover 없이도 보이고 누른 버튼이 강조된다 */
  openActionMenu?: { nodeId: string; kind: 'more' | 'add' };
  className?: string;
}

/** 표시형 들여쓰기 단위 */
const STATIC_INDENT_PX = 16;

/** 이 depth부터 라벨 앞에 점 슬롯이 하나 더 붙는다 (시안 type=sub menu_depth2) */
const DOT_DEPTH = 2;

/** 행 hover·포커스에서만 나타나는 행 액션 버튼. 동작은 소비처 핸들러가 안다. */
function RowActionButton({
  label,
  Icon,
  onClick,
  active = false,
}: {
  label: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  onClick: (trigger: HTMLElement) => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-expanded={active || undefined}
      onClick={(event) => onClick(event.currentTarget)}
      /*
       * DS Icon button(392:1887)의 상태 fill이다 — hover 10%, 메뉴 열림 12%.
       * 토큰 이름과 한 칸씩 어긋나 보이지만 22px 원에서 6%는 거의 보이지 않는다.
       */
      className={cn(
        'flex size-5.5 shrink-0 cursor-pointer items-center justify-center rounded-full',
        active ? 'bg-fill-normal-interaction-pressed-hover' : 'hover:bg-fill-normal-interaction-pressed',
      )}
    >
      <Icon aria-hidden className="size-4.5" />
    </button>
  );
}

/**
 * depth·아이콘·라벨·접기·선택만 아는 프레젠테이션 트리.
 * `onNodeClick`을 넘기지 않으면 정적 표시형(전체 펼침·클릭 불가)이 된다.
 */
export default function NavTree({
  nodes,
  activeId,
  defaultExpandedIds,
  onNodeClick,
  onNodeMore,
  onNodeAdd,
  openActionMenu,
  className,
}: NavTreeProps) {
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
    // 표시형은 선택 개념이 없다 — 경로 조각을 보여주는 것이 전부다
    const isActive = !isStatic && node.id === activeId;
    const menuOpen = openActionMenu?.nodeId === node.id;

    const label = (
      <span
        className={cn(
          'text-body-small min-w-0 truncate text-left',
          isActive ? 'text-text-primary-normal' : 'text-text-normal-normal',
        )}
      >
        {node.label}
      </span>
    );

    if (isStatic) {
      return (
        <span className="flex h-7 items-center gap-2" style={{ paddingInlineStart: depth * STATIC_INDENT_PX }}>
          {depth > 0 && (
            <IconArrowRight2
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

    /*
     * 들여쓰기가 행을 밀지 않는다 — 배경은 depth와 무관하게 같은 폭이다(시안 18580:80747).
     * depth2는 점 슬롯이 하나 더 붙어 그만큼 더 들어가고 간격도 좁다.
     */
    const hasDot = depth >= DOT_DEPTH;

    return (
      <div
        data-slot="nav-tree-row"
        className={cn(
          'group flex h-9 items-center rounded-lg py-1.5 pr-2.5 transition-colors',
          depth === 0 ? 'pl-2.5' : 'pl-5',
          hasDot ? 'gap-2' : 'gap-3',
          'hover:bg-fill-normal-interaction-hover',
          // 메뉴가 열려 있는 동안은 마우스가 떠나도 hover 상태를 유지한다.
          menuOpen && 'bg-fill-normal-interaction-hover',
          /*
           * 선택 상태는 중립 hover 대신 primary hover_assistive가 덮는다. 시안에
           * Selected_pressed가 없어 선택 행에는 중립 pressed를 걸지 않는다.
           */
          isActive
            ? 'bg-fill-primary-normal-neutral hover:bg-fill-primary-normal-interaction-hover-assistive'
            : 'has-[button:active]:bg-fill-normal-interaction-pressed',
        )}
      >
        {hasDot && (
          <span className="flex size-5.5 shrink-0 items-center justify-center">
            {/* 선택 행에서는 점도 파랑이다 — 라벨(#005eeb)보다 옅은 blue-40이다 */}
            <span
              aria-hidden
              className={cn(
                'size-1.5 rounded-full border-[1.5px]',
                isActive ? 'border-icon-primary-assistive' : 'border-icon-normal-assistive',
              )}
            />
          </span>
        )}

        {/* 캐럿 대상 행은 Icon 유무와 무관하게 슬롯을 예약한다 — 없으면 hover에 라벨이 밀린다 */}
        {(hasChildren || node.Icon) && (
          <span className="relative flex size-5.5 shrink-0 items-center justify-center">
            {node.Icon && (
              <node.Icon
                aria-hidden
                className={cn(
                  'size-5.5',
                  isActive ? 'text-icon-primary-normal' : 'text-icon-normal-neutral',
                  hasChildren && 'group-hover:hidden group-has-[:focus-visible]:hidden',
                )}
              />
            )}
            {hasChildren && (
              <button
                type="button"
                aria-label={`${node.label} ${expanded ? '접기' : '펼치기'}`}
                aria-expanded={expanded}
                onClick={() => toggle(node.id)}
                className={cn(
                  'hover:bg-fill-normal-interaction-pressed absolute hidden size-5.5 cursor-pointer items-center justify-center rounded-full group-hover:flex group-has-[:focus-visible]:flex',
                  isActive ? 'text-icon-primary-normal' : 'text-icon-normal-neutral',
                )}
              >
                <IconArrowRightFilled
                  aria-hidden
                  className={cn('size-4.5 transition-transform', expanded && 'rotate-90')}
                />
              </button>
            )}
          </span>
        )}

        <button
          type="button"
          aria-current={isActive ? 'page' : undefined}
          onClick={() => onNodeClick(node.id)}
          // 라벨 span이 flex 아이템이어야 truncate가 동작한다 — 인라인이면 overflow가 무시된다
          className="flex min-w-0 flex-1 cursor-pointer"
        >
          {label}
        </button>

        {/*
         * 액션은 오버레이가 아니라 in-flow다. focus-within이 아니라 focus-visible을 보는 이유는
         * 클릭 후에도 포커스가 남아 어포던스가 붙어 있기 때문이다 — 키보드 접근은 그대로 된다.
         */}
        {(onNodeMore || (onNodeAdd && node.canAddChild)) && (
          <div
            className={cn(
              'shrink-0 items-center gap-0.5 group-hover:flex group-has-[:focus-visible]:flex',
              // 선택 행의 액션은 파랑이다 (시안 Selected_hover는 Icon only(Blue))
              isActive ? 'text-icon-primary-normal' : 'text-icon-normal-neutral',
              menuOpen ? 'flex' : 'hidden',
            )}
          >
            {onNodeMore && (
              <RowActionButton
                label={`${node.label} 추가 작업`}
                Icon={IconMore}
                active={menuOpen && openActionMenu?.kind === 'more'}
                onClick={(trigger) => onNodeMore(node.id, trigger)}
              />
            )}
            {onNodeAdd && node.canAddChild && (
              <RowActionButton
                label={`${node.label} 하위 페이지 추가`}
                Icon={IconAdd}
                active={menuOpen && openActionMenu?.kind === 'add'}
                onClick={(trigger) => onNodeAdd(node.id, trigger)}
              />
            )}
          </div>
        )}
      </div>
    );
  };

  const renderNode = (node: NavTreeNode, depth: number) => {
    const hasChildren = Boolean(node.children?.length);
    // 표시형은 접을 수 없다 — 경로 조각을 보여주는 것이 전부라 접을 이유가 없다
    const expanded = isStatic || expandedIds.has(node.id);

    return (
      <li key={node.id} className={cn('flex flex-col', isStatic ? 'gap-2' : 'gap-0.5')}>
        {renderRow(node, depth, hasChildren, expanded)}
        {hasChildren && expanded ? renderList(node.children ?? [], depth + 1) : null}
      </li>
    );
  };

  const renderList = (items: readonly NavTreeNode[], depth: number) => (
    // 표시형만 행 간격을 벌린다 — 탐색형은 행이 붙어 있다
    <ul className={cn('flex flex-col', isStatic ? 'gap-2' : 'gap-0.5')}>
      {items.map((node) => renderNode(node, depth))}
    </ul>
  );

  return <div className={className}>{renderList(nodes, 0)}</div>;
}
