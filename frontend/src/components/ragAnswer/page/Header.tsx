/**
 * 페이지 상단 헤더
 * children 전달 시 커스텀 헤더로 대체 가능
 */

'use client';

import type { PropsWithChildren } from 'react';
import { useRagPageContext } from './Context';
import RagContentHeader from '@/components/ragAnswer/components/answerComponent/RagContentHeader';

interface HeaderProps extends PropsWithChildren {}

const Header = ({ children }: HeaderProps) => {
  const { chat, pagination } = useRagPageContext();

  if (children) return <>{children}</>;

  return (
    <RagContentHeader
      title={chat.chatData?.title ?? ''}
      onSelectQuestion={pagination.goToQuestion}
    />
  );
};

export default Header;
