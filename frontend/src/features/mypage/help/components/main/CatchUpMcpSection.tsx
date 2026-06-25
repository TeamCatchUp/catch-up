import Image from 'next/image';
import Link from 'next/link';

import ArrowOutward from '@/public/icons/icon/arrow_outward.svg';
import { Button } from '@/shared/components/ui/button';

export default function CatchUpMcpSection() {
  return (
    <section className="flex w-full flex-wrap items-center gap-x-12 gap-y-6">
      <div className="flex min-w-75 flex-1 flex-col items-start gap-4">
        <h2 className="text-heading-xlarge text-text-normal-strong">새로운 기능: Catch Up MCP</h2>
        <div className="text-body-small text-text-normal-alternative leading-[1.75]">
          <p>
            평소 사용하던 AI Agent가 회사의 업무 기록을 직접 검색할 수 있습니다. 하나의 MCP 연결만으로 여러 협업 툴을
            함께 탐색하고 팀의 결정과 논의 맥락을 기반으로 답변합니다.
          </p>
          <br />
          <ul className="list-disc pl-5">
            <li>질문 하나로 회사에 흩어진 정보를 찾아보세요.</li>
            <li>Catch Up MCP가 여러 업무 도구를 함께 탐색합니다.</li>
          </ul>
        </div>
        <Button asChild variant="capsule-solid-primary" size="md" className="text-body-medium h-10 gap-2.5 px-4 py-1.5">
          <Link href="/mypage/help/tutorial/4">
            더 알아보기
            <ArrowOutward className="size-6" />
          </Link>
        </Button>
      </div>

      <div className="relative aspect-597/312 w-full overflow-hidden rounded-2xl lg:min-h-[261px] lg:max-w-[600px] lg:min-w-[500px]">
        <Image
          src="/image/help/light/catch-up-mcp.png"
          alt="Catch Up MCP 연결 가이드"
          fill
          className="object-cover dark:hidden"
        />
        <Image
          src="/image/help/dark/catch-up-mcp.png"
          alt="Catch Up MCP 연결 가이드"
          fill
          className="hidden object-cover dark:block"
        />
      </div>
    </section>
  );
}
