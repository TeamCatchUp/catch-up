import IconInfo from '@/public/icons/icon/info.svg';
import { Button } from '@/shared/components/ui/button';

import type { MemberIntegrationCardItem } from '../../../types/integrations';

interface StatusCardsSectionProps {
  cards: MemberIntegrationCardItem[];
}

/** 이용자 연동 상단 계정 등록 카드 섹션 */
const StatusCardsSection = ({ cards }: StatusCardsSectionProps) => {
  return (
    <section className="flex w-250 flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-gray-80">계정 등록 상태</h2>
        <p className="text-body-small text-gray-50">팀의 계정 등록 상태를 확인할 수 있어요.</p>
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
                <div className="border-neutral-2 bg-neutral-1 flex flex-col gap-1.5 rounded-lg border px-3 py-3">
                  <div className="flex items-center gap-1">
                    <span className="text-body-xsmall text-gray-70">연동 완료율</span>
                    <IconInfo className="text-gray-30 size-4.5" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-heading-medium text-gray-70">{completionRate}%</span>
                    <span className="rounded-md2 text-body-xsmall bg-violet-5 px-1.5 py-0.5 leading-none tracking-tight text-violet-50">
                      {`${completedCount}/${totalCount}`}
                    </span>
                  </div>
                </div>

                <Button variant="box-outline-gray" size="md" className="text-body-small h-9 w-full">
                  임베딩하기
                </Button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
};

export default StatusCardsSection;
