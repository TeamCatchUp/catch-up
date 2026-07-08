'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import {
  customerFull,
  customerPartial,
  metadataVariants,
} from '@/features/hybrid-search/components/original/__fixtures__/originalContent.fixtures';
import Collapsible from '@/features/hybrid-search/components/original/channel-talk/metadata/Collapsible';
import ConsultationInfo from '@/features/hybrid-search/components/original/channel-talk/metadata/ConsultationInfo';
import CustomerInfo from '@/features/hybrid-search/components/original/channel-talk/metadata/CustomerInfo';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { Case, PanelWidth, StorySurface } from './OriginalPanelStoryFrame';

const meta = {
  title: 'Compositions/Hybrid Search/Original Panel/ChannelTalkMetadata',
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'consultation-info',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['consultation-info', 'customer-info', 'collapsible'],
      dataNotes: ['Uses ChannelTalk metadata variants for consultation and customer information.'],
      reuseNotes: ['Renders production metadata components without the full panel shell.'],
    }),
  },
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const InfoVariants: Story = {
  render: () => (
    <StorySurface>
      {metadataVariants.map((variant) => (
        <Case key={variant.metadata.user_chat_id} label={variant.label}>
          <PanelWidth>
            <ConsultationInfo metadata={variant.metadata} />
          </PanelWidth>
        </Case>
      ))}
      <Case label="고객 정보 전체 필드">
        <PanelWidth>
          <CustomerInfo customer={customerFull} />
        </PanelWidth>
      </Case>
      <Case label="고객 정보 일부 필드">
        <PanelWidth>
          <CustomerInfo customer={customerPartial} />
        </PanelWidth>
      </Case>
      <Case label="고객 정보 없음">
        <PanelWidth>
          <CustomerInfo customer={undefined} />
        </PanelWidth>
      </Case>
      <Case label="접기 펼치기">
        <PanelWidth>
          <Collapsible
            open
            onOpenChange={() => undefined}
            header={<span className="text-body-small text-text-normal-normal py-2 font-medium">펼쳐진 헤더</span>}
          >
            <p className="text-body-small text-text-normal-alternative pb-2">접히는 본문 영역입니다.</p>
          </Collapsible>
        </PanelWidth>
      </Case>
    </StorySurface>
  ),
};
