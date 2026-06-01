import type { ReactNode } from 'react';

import {
  customerFull,
  customerPartial,
  metadataVariants,
} from '@/features/hybrid-search/components/original/__fixtures__/originalContent.fixtures';
import Collapsible from '@/features/hybrid-search/components/original/channel-talk/metadata/Collapsible';
import ConsultationInfo from '@/features/hybrid-search/components/original/channel-talk/metadata/ConsultationInfo';
import CustomerInfo from '@/features/hybrid-search/components/original/channel-talk/metadata/CustomerInfo';

import Case from '../components/Case';
import PanelWidth from '../components/PanelWidth';
import type { OriginalPanelCaseId } from '../originalPanelEntries';

export const channelTalkMetadataRenderers = {
  'consultation-info': () => (
    <>
      {metadataVariants.map((variant) => (
        <Case key={variant.metadata.user_chat_id} label={variant.label}>
          <PanelWidth>
            <ConsultationInfo metadata={variant.metadata} />
          </PanelWidth>
        </Case>
      ))}
    </>
  ),
  'customer-info': () => (
    <>
      <Case label="전체 필드">
        <PanelWidth>
          <CustomerInfo customer={customerFull} />
        </PanelWidth>
      </Case>
      <Case label="일부 필드 ('없음' placeholder)">
        <PanelWidth>
          <CustomerInfo customer={customerPartial} />
        </PanelWidth>
      </Case>
      <Case label="customer 자체가 undefined">
        <PanelWidth>
          <CustomerInfo customer={undefined} />
        </PanelWidth>
      </Case>
    </>
  ),
  collapsible: () => (
    <Case label="기본 (CustomerInfo·FormContent 케이스 참고)">
      <PanelWidth>
        <Collapsible
          open
          onOpenChange={() => {}}
          header={<span className="text-body-small text-content-normal py-2 font-medium">펼쳐진 헤더</span>}
        >
          <p className="text-body-small text-content-alternative pb-2">접히는 본문 영역입니다.</p>
        </Collapsible>
      </PanelWidth>
    </Case>
  ),
} satisfies Partial<Record<OriginalPanelCaseId, () => ReactNode>>;
