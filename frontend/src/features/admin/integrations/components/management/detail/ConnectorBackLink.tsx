import IconArrowLeft from '@/public/icons/icon/arrow_left.svg';
import { Button } from '@/shared/components/ui/button';

interface ConnectorBackLinkProps {
  onBack: () => void;
}

/**
 * 상세에서 카탈로그로 돌아가는 링크.
 * Figma `16922:134098` — Text Button / Secondary Mono / size=large_이전페이지.
 * 코드 Text Button에는 그 크기가 없어 md에 타이포와 gap만 덮어 맞췄다.
 */
export default function ConnectorBackLink({ onBack }: ConnectorBackLinkProps) {
  return (
    <Button variant="text-secondary-mono" size="md" onClick={onBack} className="text-heading-small gap-1.5 self-start">
      <IconArrowLeft className="size-5" />
      커넥터 전체 보기
    </Button>
  );
}
