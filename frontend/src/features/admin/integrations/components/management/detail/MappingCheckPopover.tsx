import IconCancel from '@/public/icons/icon/cancel.svg';
import IconInfoFilled from '@/public/icons/icon/info_filled.svg';
import { Button } from '@/shared/components/ui/button';

interface MappingCheckPopoverProps {
  onClose: () => void;
}

/**
 * 연결 전 이용자 매핑 확인을 권하는 비차단 안내.
 *
 * 본문은 온보딩 문서("처음 오셨나요? — 나의 이름표")를 바탕으로 교체했다
 * (사용자 지시 2026-08-05). 매핑의 실제 효용이 그 문서의 논리다:
 * 계정을 등록하지 않은 기간의 데이터는 Catch Up이 찾기 어렵고, 닉네임·이메일을
 * 등록해야 기록이 흩어지지 않고 '나의 업무 맥락'으로 정리된다.
 * Figma 원문("권한에 맞는 검색 결과")은 스펙 미결 #1로 남아 있었다.
 *
 * 같은 문구의 확인 모달은 구현하지 않는다(스펙 결정 #1).
 * 매핑 부재의 영향은 접근 제어가 아니라 인식 품질이라 흐름을 막을 근거가 없다.
 */
export default function MappingCheckPopover({ onClose }: MappingCheckPopoverProps) {
  // 폭은 내용에 맞추고 고정하지 않는다 — max-w 는 상한일 뿐이다
  return (
    <div className="border-accent-black-lighten bg-fill-normal-normal shadow-tooltip flex max-w-115 flex-col gap-1 rounded-xl border p-3">
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
        계정을 등록하지 않은 기간의 데이터는 Catch Up이 찾기 어려워요. 협업 툴에서 쓰는 닉네임·이메일을 등록해두면
        팀원의 기록이 흩어지지 않고 &lsquo;나의 업무 맥락&rsquo;으로 정리됩니다.
      </p>
    </div>
  );
}
