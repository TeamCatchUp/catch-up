import AlarmFilled from '@/public/icons/icon/alarm_filled.svg';
import ArrowForward from '@/public/icons/icon/arrow_forward.svg';
import CommentFilled from '@/public/icons/icon/comment_filled.svg';

const ContactChannelSection = () => {
  return (
    <section className="flex w-250 shrink-0 flex-col gap-3">
      <div className="flex items-end justify-between">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-heading-large text-gray-80">Catch Up 문의 채널</h2>
          <p className="text-body-small text-gray-60">운영팀과 Slack으로 바로 연결됩니다.</p>
        </div>

        <span className="text-body-small flex items-center gap-1 px-1.5 py-1 text-blue-50">
          Slack 으로 문의하기
          <ArrowForward className="h-5 w-5" />
        </span>
      </div>

      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <AlarmFilled className="h-5 w-5 text-gray-20" />
            <span className="text-body-small text-gray-60">운영 시간</span>
          </div>
          <span className="text-body-small text-gray-80">매일 10:00-18:00</span>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <CommentFilled className="h-5 w-5 text-gray-20" />
            <span className="text-body-small text-gray-60">응답 시간</span>
          </div>
          <span className="text-body-small text-gray-80">매일 10:00-18:00</span>
        </div>
      </div>
    </section>
  );
};

export default ContactChannelSection;
