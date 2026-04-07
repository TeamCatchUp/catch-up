import AlarmFilled from '@/public/icons/icon/alarm_filled.svg';
import ArrowForward from '@/public/icons/icon/arrow_circle_right.svg';
import CommentFilled from '@/public/icons/icon/comment_filled.svg';
import { Button } from '@/shared/components/ui/button';

export default function ContactChannelSection() {
  return (
    <section className="flex w-full flex-col gap-3">
      <div className="flex items-end justify-between">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-heading-large text-content-normal">Catch Up 문의 채널</h2>
          <div className="flex items-center gap-1">
            <p className="text-body-small text-content-alternative">운영팀과 Slack으로 바로 연결됩니다.</p>
            <Button variant="text-primary-blue" size="md" className="text-content-primary gap-1" asChild>
              <a
                href="https://app.slack.com/accept-slack-connect-invitation/example"
                target="_blank"
                rel="noopener noreferrer"
              >
                Slack 으로 문의하기
                <ArrowForward className="h-5 w-5 shrink-0" />
              </a>
            </Button>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <AlarmFilled className="text-content-assistive h-5 w-5" />
            <span className="text-body-small text-content-alternative">운영 시간</span>
          </div>
          <span className="text-body-small text-content-normal">매일 10:00-18:00</span>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <CommentFilled className="text-content-assistive h-5 w-5" />
            <span className="text-body-small text-content-alternative">응답 시간</span>
          </div>
          <span className="text-body-small text-content-normal">매일 10:00-18:00</span>
        </div>
      </div>
    </section>
  );
}
