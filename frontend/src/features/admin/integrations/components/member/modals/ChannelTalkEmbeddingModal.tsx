'use client';

import IconCancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';

import { useChannelTalkSelection } from '../../../hooks/useChannelTalkSelection';
import ChannelGroup from './channelTalk/ChannelGroup';
import ChannelGroupListEmpty from './channelTalk/ChannelGroupListEmpty';
import ChannelList from './channelTalk/ChannelList';
import { type ChannelTalkChannel, MOCK_CHANNEL_TALK_CHANNELS } from './channelTalk/mockChannels';
import { DEFAULT_PERIOD } from './channelTalk/PeriodSelect';

interface ChannelTalkEmbeddingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * 채널톡 임베딩 모달 셸.
 *
 * ModalBody가 별도 컴포넌트로 분리된 이유: open=true일 때만 마운트되어 selection state가
 * 매 모달 진입마다 fresh하게 초기화된다. useEffect로 reset하는 패턴은 React 19의
 * `react-hooks/set-state-in-effect` 룰에 막혀, mount/unmount 기반 초기화로 우회.
 */
export default function ChannelTalkEmbeddingModal({ open, onOpenChange }: ChannelTalkEmbeddingModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="shadow-modal bg-fill-normal flex h-200 w-200 max-w-200 flex-col gap-0 rounded-3xl p-0"
      >
        {open && <ModalBody channels={MOCK_CHANNEL_TALK_CHANNELS} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

interface ModalBodyProps {
  channels: ChannelTalkChannel[];
  onClose: () => void;
}

function ModalBody({ channels, onClose }: ModalBodyProps) {
  const {
    selectedChannelIds,
    selectedSpaceIds,
    channelPeriods,
    spacePeriods,
    visibleChannels,
    channelCount,
    spaceCount,
    isSubmitDisabled,
    toggleChannel,
    toggleAllChannels,
    toggleSpace,
    toggleChannelSpaces,
    setChannelPeriod,
    setSpacePeriod,
  } = useChannelTalkSelection(channels);

  // TODO: 백엔드 임베딩 API 연동 시 mutation 호출 후 onClose. 현재는 모달만 닫음.
  const handleSubmit = onClose;

  return (
    <>
      <header className="flex items-start gap-3 px-6 pt-6 pb-4">
        <div className="flex flex-1 flex-col gap-1">
          <DialogTitle className="text-heading-large text-content-strong">
            임베딩 할 채널, 도큐먼트 스페이스 선택해주세요
          </DialogTitle>
          <p className="text-body-small text-content-assistive">
            AI 답변에 활용할 채널과 도큐먼트 스페이스를 선택하고 임베딩 기간을 지정하세요
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="닫기"
          className="hover:bg-fill-strong flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-lg"
        >
          <IconCancel className="text-content-alternative size-6" />
        </button>
      </header>

      <div className="border-edge-neutral flex flex-1 overflow-hidden border-t">
        <ChannelList
          channels={channels}
          selectedChannelIds={selectedChannelIds}
          onToggleChannel={toggleChannel}
          onToggleAll={toggleAllChannels}
        />

        <div className="custom-scrollbar flex flex-1 flex-col overflow-y-auto">
          {visibleChannels.length === 0 ? (
            <ChannelGroupListEmpty />
          ) : (
            visibleChannels.map((channel) => (
              <div key={channel.channel_id} className="animate-list-item-enter">
                <ChannelGroup
                  channel={channel}
                  selectedSpaceIds={selectedSpaceIds}
                  channelPeriod={channelPeriods[channel.channel_id] ?? DEFAULT_PERIOD}
                  spacePeriods={spacePeriods}
                  onToggleChannelSpaces={toggleChannelSpaces}
                  onToggleSpace={toggleSpace}
                  onChangeChannelPeriod={setChannelPeriod}
                  onChangeSpacePeriod={setSpacePeriod}
                />
              </div>
            ))
          )}
        </div>
      </div>

      <footer className="mx-6 mt-4 mb-5 flex h-9 items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5">
            <span className="text-body-small text-content-primary">{channelCount}</span>
            <span className="text-body-small text-content-normal">채널</span>
          </div>
          <span className="bg-edge-neutral block h-3 w-px" />
          <div className="flex items-center gap-2.5">
            <span className="text-body-small text-content-primary">{spaceCount}</span>
            <span className="text-body-small text-content-normal">도큐먼트 스페이스</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="capsule-outline-mono" size="md" onClick={onClose}>
            취소
          </Button>
          <Button variant="capsule-solid-primary" size="md" disabled={isSubmitDisabled} onClick={handleSubmit}>
            채널톡 임베딩하기
          </Button>
        </div>
      </footer>
    </>
  );
}
