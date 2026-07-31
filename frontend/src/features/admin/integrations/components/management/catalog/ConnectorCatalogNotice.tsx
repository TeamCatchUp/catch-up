import IconHelp from '@/public/icons/icon/help.svg';
import IconInfoFilled from '@/public/icons/icon/info_filled.svg';
import { Button } from '@/shared/components/ui/button';

interface ConnectorCatalogNoticeProps {
  onLearnMore: () => void;
}

/**
 * 카탈로그 하단 안내 배너.
 * Figma `16966:66318` — padding 8, gap 8, radius 8, bg #F7F7F8.
 */
export default function ConnectorCatalogNotice({ onLearnMore }: ConnectorCatalogNoticeProps) {
  return (
    <div className="bg-fill-normal-strong flex items-center justify-center gap-2 rounded-lg p-2">
      <IconInfoFilled className="text-icon-normal-alternative size-5.5 shrink-0" />
      <span className="text-body-small text-text-normal-alternative min-w-0 flex-1">
        연결은 관리자만 할 수 있어요. 데이터는 읽기 전용으로 안전하게 동기화돼요
      </span>
      <Button variant="text-secondary-mono" size="sm" onClick={onLearnMore} className="shrink-0">
        <IconHelp className="size-5" />
        연결에 대해 더 자세히 알아보기
      </Button>
    </div>
  );
}
