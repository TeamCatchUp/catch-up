import IconCancel from '@/public/icons/icon/cancel.svg';
import IconInfoFilled from '@/public/icons/icon/info_filled.svg';
import { Button } from '@/shared/components/ui/button';

interface MappingCheckPopoverProps {
  onClose: () => void;
}

/**
 * 연결 전 이용자 매핑 확인을 권하는 비차단 안내.
 * Figma `17251:77202` — Tooltip size=large, padding 12, gap 4, radius 12.
 *
 * 같은 문구의 확인 모달(`17251:77261`)은 구현하지 않는다(스펙 결정 #1).
 * 매핑 부재의 영향은 접근 제어가 아니라 이름 인식 품질이라 흐름을 막을 근거가 없다.
 */
export default function MappingCheckPopover({ onClose }: MappingCheckPopoverProps) {
  return (
    <div className="border-accent-black-lighten bg-fill-normal-normal shadow-tooltip flex w-115 flex-col gap-1 rounded-xl border p-3">
      <div className="flex items-center gap-2">
        <IconInfoFilled className="text-icon-normal-normal size-5.5 shrink-0" />
        <span className="text-body-small text-text-normal-strong min-w-0 flex-1">
          연동 전, 이용자 매핑 상태를 확인해 주세요
        </span>
        <Button variant="icon-only-gray" size="sm" onClick={onClose} aria-label="닫기" className="shrink-0">
          <IconCancel className="size-5" />
        </Button>
      </div>
      <p className="text-label-small text-text-normal-neutral">
        팀원이 본인 권한에 맞는 검색 결과를 받으려면 계정 매핑이 필요해요. 연결 전에 매핑 상태를 한번 확인해 주세요.
      </p>
    </div>
  );
}
