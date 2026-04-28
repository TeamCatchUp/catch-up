'use client';

import IconAddSquare from '@/public/icons/icon/add_square.svg';
import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconOpenInNew from '@/public/icons/icon/open_in_new.svg';

import type { ChannelTalkChannel, ChannelTalkConnectionState } from '../../../types/channelTalkModel';
import ChannelTalkChannelCard from './ChannelTalkChannelCard';

interface ChannelTalkManagementPanelProps {
  state: ChannelTalkConnectionState;
}

/**
 * 채널톡 메인 패널 — 연동 상태 관리 / 데이터 범위 / Credential 입력 3개 섹션.
 *
 * Figma node mapping:
 * - 메인 패널 컨테이너: `12045:47557` (684×3613)
 * - 연동 상태 관리 헤더: `12045:47558` (684×142)
 * - 연동된 데이터 범위: `12045:47576` (684×83)
 * - Credential 입력 섹션: `12045:47580` (684×1636)
 * - 채널 리스트 헤더: `12045:47583`
 */
export default function ChannelTalkManagementPanel({ state }: ChannelTalkManagementPanelProps) {
  const totalDocumentSpaces = state.channels.reduce((sum, ch) => sum + ch.documentSpaces.length, 0);

  return (
    <div className="flex flex-col gap-6">
      <ConnectionStatusSection state={state} />
      <DataRangeSection connected={state.connected} />
      <CredentialSection
        channels={state.channels}
        channelCount={state.channels.length}
        totalDocumentSpaces={totalDocumentSpaces}
      />
    </div>
  );
}

interface ConnectionStatusSectionProps {
  state: ChannelTalkConnectionState;
}

/** 연동 상태 관리 — 연동 상태 토글 + 보안 관련 설명 */
function ConnectionStatusSection({ state }: ConnectionStatusSectionProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-heading-small text-content-normal">연동 상태 관리</h3>

      <div className="border-edge-neutral bg-fill-strong overflow-hidden rounded-xl border">
        <div className="border-edge-neutral flex h-13 items-center justify-between border-b px-4 py-3">
          <span className="text-body-small text-content-neutral">연동 상태</span>
          {state.connected ? (
            <div className="flex items-center gap-1">
              <IconCloudCheckFilled className="text-icon-primary size-5 shrink-0" />
              <span className="text-body-xsmall text-content-primary">연동됨</span>
            </div>
          ) : (
            <span className="text-body-xsmall text-content-alternative">연동 안됨</span>
          )}
        </div>
        <div className="flex h-13 items-center justify-between px-4 py-3">
          <span className="text-body-small text-content-neutral">보안 관련 설명</span>
          <button
            type="button"
            className="text-body-xsmall text-content-neutral flex h-7 cursor-pointer items-center gap-1 rounded-full px-1.5 py-1"
          >
            원문 보기
            <IconOpenInNew className="text-icon-normal size-4.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

interface DataRangeSectionProps {
  connected: boolean;
}

/** 연동된 데이터 범위 섹션 — 단일 헤더 + 박스 (mock 단계는 텍스트만) */
function DataRangeSection({ connected }: DataRangeSectionProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-heading-small text-content-neutral">연동된 데이터 범위</h3>
      <div className="border-edge-neutral bg-fill-strong text-body-small text-content-neutral flex h-13 items-center rounded-xl border px-4">
        {connected ? '연동된 채널의 메시지를 임베딩하고 있어요.' : '연동되지 않았습니다.'}
      </div>
    </div>
  );
}

interface CredentialSectionProps {
  channels: ChannelTalkChannel[];
  channelCount: number;
  totalDocumentSpaces: number;
}

/** Credential Key 입력 및 동기화 주기 설정 — 채널 리스트 헤더 + 채널 카드들 */
function CredentialSection({ channels, channelCount, totalDocumentSpaces }: CredentialSectionProps) {
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-heading-small text-content-neutral">Credential Key 입력 및 동기화 주기 설정</h3>

      {/*
        채널 리스트 헤더 — 박스 전체가 "채널 추가하기" 클릭 영역.
        Figma 3상태:
        - Default(#f7f7f8): node `12060:84077`
        - Hover(#eaebec):   node `12060:84088`
        - Pressed(#e1e2e4): node `12060:84094`
      */}
      <button
        type="button"
        className="border-edge-assistive bg-fill-strong hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed flex w-full cursor-pointer flex-wrap items-center gap-1.5 rounded-xl border px-4 py-3 transition-colors"
      >
        <span className="text-body-small text-content-normal shrink-0">{channelCount}개 채널</span>
        <span className="bg-dim-black-25 size-1 shrink-0 rounded-full" aria-hidden />
        <span className="text-body-small text-content-normal min-w-0 flex-1 truncate text-left">
          {totalDocumentSpaces}개 도큐먼트 연결됨
        </span>
        <span className="text-body-small text-content-primary flex shrink-0 items-center gap-2">
          <IconAddSquare className="text-icon-primary size-6 shrink-0" />
          채널 추가하기
        </span>
      </button>

      {/* 채널 카드 리스트 — mock 5개가 5상태(idle/entered/tested/error/editing)를 각각 시연 */}
      <div className="flex flex-col gap-3">
        {channels.map((channel) => (
          <ChannelTalkChannelCard key={channel.id} channel={channel} />
        ))}
      </div>
    </div>
  );
}
