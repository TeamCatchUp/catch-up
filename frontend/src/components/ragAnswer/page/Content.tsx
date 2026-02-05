/** 스크롤 가능한 컨텐츠 영역 */

'use client';

import type { PropsWithChildren } from 'react';
import clsx from 'clsx';
import { useRagPageContext } from './Context';

interface ContentProps extends PropsWithChildren {
  className?: string;
}

const Content = ({ children, className }: ContentProps) => {
  const { refs } = useRagPageContext();

  return (
    <div className="border-neutral-3 relative flex flex-1 flex-col overflow-hidden border-r-0">
      <div
        ref={refs.scroll}
        className={clsx(
          'flex flex-1 flex-col items-center overflow-y-auto scroll-smooth px-24 pt-3 pb-9',
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
};

/** 슬라이드 애니메이션이 적용되는 내부 영역 */
export const ContentInner = ({ children, className }: ContentProps) => {
  const { pagination } = useRagPageContext();
  const { slideDirection } = pagination;

  return (
    <div
      className={clsx(
        'mx-auto w-193.25 flex-1 overflow-hidden transition-all duration-300',
        slideDirection === 'down'
          ? 'translate-y-full opacity-0'
          : slideDirection === 'up'
            ? '-translate-y-full opacity-0'
            : 'translate-y-0 opacity-100',
        className,
      )}
    >
      {children}
    </div>
  );
};

export default Content;
