import IconArrowBack from '@/public/icons/icon/arrow_back.svg';
import IconKebabHorizontal from '@/public/icons/icon/kebab_horizontal.svg';
import { Button } from '@/shared/components/ui/button';

interface OnboardingTopBarProps {
  onBack?: () => void;
  /** 더보기 메뉴 내용이 시안에 없어 콜백을 주지 않으면 버튼도 그리지 않는다 */
  onMore?: () => void;
}

// 온보딩 3단계가 공유하는 상단 바. 콘텐츠 패딩 밖의 형제라 좌우 여백이 본문과 다르다
// 스크롤해도 상단에 남는다 — 배경이 불투명해야 본문이 비쳐 보이지 않는다
export default function OnboardingTopBar({ onBack, onMore }: OnboardingTopBarProps) {
  return (
    <div className="bg-fill-normal-assistive z-base sticky top-0 flex h-13 shrink-0 items-center justify-between px-6">
      <Button variant="icon-only-gray" size="lg" className="p-1.5" onClick={onBack} aria-label="뒤로 가기">
        <IconArrowBack className="size-6" />
      </Button>
      {onMore && (
        <Button variant="icon-only-gray" size="lg" className="p-1.5" onClick={onMore} aria-label="더보기">
          <IconKebabHorizontal className="size-6" />
        </Button>
      )}
    </div>
  );
}
