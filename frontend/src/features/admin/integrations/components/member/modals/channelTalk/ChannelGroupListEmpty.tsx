'use client';

import { memo } from 'react';

import IconTag from '@/public/icons/icon/tag.svg';

function ChannelGroupListEmpty() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2.5 px-5">
      <div className="border-line-normal-strong inline-flex size-9 shrink-0 items-center justify-center rounded-lg border border-dashed p-1.5">
        <IconTag className="text-text-normal-alternative size-6" />
      </div>
      <p className="text-heading-small text-text-normal-normal">채널을 선택하세요</p>
      <p className="text-body-small text-text-normal-assistive text-center">
        왼쪽에서 채널을 선택하면
        <br />
        임베딩할 도큐먼트 스페이스 목록이 표시됩니다
      </p>
    </div>
  );
}

export default memo(ChannelGroupListEmpty);
