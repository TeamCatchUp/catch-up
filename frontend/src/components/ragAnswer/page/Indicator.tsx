/** Q&A 페이지 인디케이터 - 페이지 수가 2개 이상일 때만 표시 */

'use client';

import clsx from 'clsx';
import { useRagPageContext } from './Context';
import PageIndicator from '@/components/common/PageIndicator';

interface IndicatorProps {
  className?: string;
  variant?: 'dot' | 'bar';
}

const Indicator = ({ className, variant = 'bar' }: IndicatorProps) => {
  const { pagination, chat } = useRagPageContext();
  const { qaPairs, currentPage, goToPage } = pagination;

  if (qaPairs.length <= 1) return null;

  return (
    <PageIndicator
      total={qaPairs.length}
      current={currentPage}
      disabled={chat.isLoading}
      onSelect={goToPage}
      variant={variant}
      className={clsx('mt-10', className)}
    />
  );
};

export default Indicator;
