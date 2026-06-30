import StatusErrorPage from '@/shared/components/status/StatusErrorPage';
import { STATUS_IMAGES } from '@/shared/components/status/statusImages';

export default function NotFound() {
  return (
    <StatusErrorPage
      title="찾으시는 페이지가 없어요"
      description="주소가 잘못되었거나, 페이지가 이동했을 수 있어요"
      image={STATUS_IMAGES.notFound}
      secondaryAction={{ label: '이전 페이지', action: 'back' }}
      primaryAction={{ label: '홈으로 돌아가기', href: '/' }}
      className="min-h-dvh"
    />
  );
}
