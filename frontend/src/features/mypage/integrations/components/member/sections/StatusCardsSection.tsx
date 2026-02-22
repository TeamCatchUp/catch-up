import { useState } from 'react';

import IconHelp from '@/public/icons/icon/help.svg';
import IconInfo from '@/public/icons/icon/info.svg';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import type { IntegrationService } from '@/shared/types/integrationService';

import type { MemberIntegrationCardItem } from '../../../types/integrations';
import EmbeddingModal from '../modals/EmbeddingModal';

interface StatusCardsSectionProps {
  cards: MemberIntegrationCardItem[];
}

/** 이용자 연동 상단 계정 등록 카드 섹션 */
const StatusCardsSection = ({ cards }: StatusCardsSectionProps) => {
  const [embeddingModal, setEmbeddingModal] = useState<{
    open: boolean;
    service: IntegrationService;
    serviceName: string;
  }>({ open: false, service: 'jira', serviceName: '' });

  const openEmbeddingModal = (service: IntegrationService, serviceName: string) => {
    setEmbeddingModal({ open: true, service, serviceName });
  };

  return (
    <section className="flex w-250 flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-gray-80">계정 등록 상태</h2>
        <p className="text-body-small text-gray-50">팀의 매핑 등록 상태를 확인할 수 있어요.</p>
      </div>

      <div className="flex items-center gap-5">
        {cards.map((card) => {
          const { service, name, Icon, completedCount, totalCount, completionRate } = card;
          const iconClassName = service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0';

          return (
            <article
              key={service}
              className="border-neutral-3 flex h-51 w-58.75 flex-col gap-4 rounded-xl border bg-white p-4"
            >
              <div className="flex items-center gap-2.5">
                <Icon className={iconClassName} />
                <span className="text-heading-medium text-gray-80">{name}</span>
              </div>

              <div className="flex flex-col gap-3">
                <div className="border-neutral-2 bg-neutral-1 relative flex flex-col gap-1.5 overflow-clip rounded-lg border px-3 py-3">
                  <div className="flex items-center gap-1">
                    <span className="text-body-xsmall text-gray-70">연동 완료율</span>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex">
                          <IconInfo className="text-gray-30 size-4.5" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="bottom" align="start">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-1.5">
                            <IconHelp className="size-5 shrink-0 text-white" />
                            <span className="text-white">연동 완료율</span>
                          </div>
                          <p className="text-white/75">
                            {name}를 사용하는 사람 중에서 Catch Up에 자신의 계정을 등록한 사람의 비율이에요. 이 수치가
                            낮을 때 임베딩을 진행하면 특정 사람의 작업이 빠지거나 결과가 달라질 수 있어요.
                          </p>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-heading-medium text-gray-70">{completionRate}%</span>
                    <span className="rounded-md2 text-body-xsmall bg-blue-5 px-1.5 py-0.5 leading-none tracking-tight text-blue-50">
                      {`${completedCount}/${totalCount}`}
                    </span>
                  </div>
                  <div
                    className="bg-blue-40 absolute bottom-0 left-0 h-[5px] rounded-full"
                    style={{ width: `${completionRate}%` }}
                  />
                </div>

                <Button
                  variant="box-outline-blue"
                  size="md"
                  className="text-body-small h-9 w-full"
                  onClick={() => openEmbeddingModal(service, name)}
                >
                  임베딩하기
                </Button>
              </div>
            </article>
          );
        })}
      </div>

      <EmbeddingModal
        open={embeddingModal.open}
        onOpenChange={(open) => setEmbeddingModal((prev) => ({ ...prev, open }))}
        service={embeddingModal.service}
        serviceName={embeddingModal.serviceName}
      />
    </section>
  );
};

export default StatusCardsSection;
