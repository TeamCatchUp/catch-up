import { Fragment } from 'react';

import { cn } from '@/shared/utils/cn';

export interface SnbDropdownMenuItem {
  /** 소비처가 어떤 항목이 눌렸는지 구분하는 키 */
  id: string;
  label: string;
  /** 좌측 아이콘. 생략하면 아이콘 자리를 만들지 않는다 */
  Icon?: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  onSelect?: () => void;
}

export interface SnbDropdownMenuProps {
  /** 메뉴 상단 분류 문구(채널·폴더·보기 등). 생략하면 줄 자체를 만들지 않는다 */
  categoryLabel?: string;
  /** 항목 묶음. 묶음 사이에만 구분선이 들어간다 */
  groups: readonly (readonly SnbDropdownMenuItem[])[];
  /** 하단 부가 정보 줄. 있으면 구분선 뒤에 붙는다 */
  metaLines?: readonly string[];
  className?: string;
}

const Divider = () => <div data-testid="snb-dropdown-menu-divider" className="bg-line-normal-normal mx-2 my-2 h-px" />;

/**
 * SNB 트리 행의 컨텍스트 메뉴 셸. 팝오버 배치·열림 상태는 소비처가 들고,
 * 이 컴포넌트는 받은 항목을 그리기만 한다.
 */
export default function SnbDropdownMenu({ categoryLabel, groups, metaLines, className }: SnbDropdownMenuProps) {
  // 권한으로 항목이 모두 빠진 묶음은 구분선만 남기지 않는다
  const visibleGroups = groups.filter((group) => group.length > 0);

  return (
    <div
      data-testid="snb-dropdown-menu"
      className={cn(
        'bg-background-elevated-normal border-line-normal-normal shadow-dropdown-menu flex w-[250px] flex-col rounded-xl border px-1.5 py-2',
        className,
      )}
    >
      {categoryLabel && (
        <span className="text-body-xsmall text-text-normal-alternative flex h-5 items-center px-2">{categoryLabel}</span>
      )}
      {/* 블록 사이는 모두 8, 그룹 안 항목만 4로 붙는다 */}
      <div className={cn('flex flex-col', categoryLabel && 'mt-2')}>
        {visibleGroups.map((group, groupIndex) => (
          <Fragment key={group.map((item) => item.id).join('|')}>
            {groupIndex > 0 && <Divider />}
            <div className="flex flex-col gap-1">
              {group.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={item.onSelect}
                  className="hover:bg-fill-normal-interaction-hover flex h-[31px] w-full cursor-pointer items-center gap-2.5 rounded-lg px-2 transition-colors"
                >
                  {item.Icon && <item.Icon aria-hidden className="text-icon-normal-normal size-5 shrink-0" />}
                  <span className="text-body-small text-text-normal-normal min-w-0 truncate text-left">
                    {item.label}
                  </span>
                </button>
              ))}
            </div>
          </Fragment>
        ))}
      </div>
      {metaLines && metaLines.length > 0 && (
        <>
          <Divider />
          <div data-testid="snb-dropdown-menu-meta" className="text-body-xsmall text-text-normal-assistive px-2">
            {metaLines.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
