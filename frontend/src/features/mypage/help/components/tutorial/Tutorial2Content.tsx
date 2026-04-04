import Image from 'next/image';

const DotDivider = () => (
  <div className="flex items-center justify-center gap-1.5 py-4">
    <span className="bg-content-assistive size-1 rounded-full" />
    <span className="bg-content-assistive size-1 rounded-full" />
    <span className="bg-content-assistive size-1 rounded-full" />
  </div>
);

const ExampleBox = ({ children }: { children: React.ReactNode }) => (
  <div className="border-edge-assistive bg-fill-strong text-label-medium flex flex-col gap-3 rounded-xl border px-5 py-4">
    {children}
  </div>
);

export default function Tutorial2Content() {
  return (
    <div className="flex w-full flex-col gap-16">
      {/* 도입부 */}
      <div className="text-label-medium text-content-normal">
        <p>
          좋은 답은 혼자 만들어지지 않아요.
          <br />
          질문이 또렷할수록, 더 정확한 답을 드릴 수 있어요.
        </p>
        <br />
        <p>그래서 오늘은 질문 한 번에 원하는 답을 얻는 비결을 소개해드릴게요.</p>
      </div>

      <DotDivider />

      {/* 섹션 1: 정확도를 올리는 질문 습관 */}
      <section className="flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <h2 className="text-heading-xlarge text-content-strong">정확도를 올리는 질문 습관</h2>
          <div className="text-label-medium text-content-normal">
            <p>길게 설명하지 않아도 괜찮아요. 필요한 정보만 있으면 충분해요.</p>
            <br />
            <p>아래 세 가지만 적어주면, 답이 훨씬 또렷해져요.</p>
          </div>
        </div>

        <div className="px-16">
          <div className="relative aspect-[1416/600] w-full">
            <Image
              src="/image/tutorial/light/tutorial-2-section-1.jpg"
              alt="정확도를 올리는 질문 습관"
              fill
              className="object-cover dark:hidden"
            />
            <Image
              src="/image/tutorial/dark/tutorial-2-section-1.jpg"
              alt="정확도를 올리는 질문 습관"
              fill
              className="hidden object-cover dark:block"
            />
          </div>
        </div>

        <div className="flex flex-col gap-8">
          {/* 1. 기능명 같은 '단서'를 하나 주세요 */}
          <div className="flex flex-col gap-2">
            <h3 className="text-heading-large text-content-normal">1. 기능명 같은 &apos;단서&apos;를 하나 주세요</h3>
            <div className="text-label-medium text-content-normal">
              <p>무엇에 대한 질문인지가 먼저 잡히면, 찾는 범위가 흔들리지 않아요.</p>
              <br />
              <p>
                기능 이름, 이슈/PR 번호, 문서 제목처럼 기억나는 단서 하나면 충분해요. 링크까지 찾아오지 않아도
                괜찮습니다.
              </p>
            </div>
          </div>

          {/* 2. 목적을 한 줄로 알려주세요 */}
          <div className="flex flex-col gap-2">
            <h3 className="text-heading-large text-content-normal">2. 목적을 한 줄로 알려주세요</h3>
            <div className="text-label-medium text-content-normal">
              <p>
                원하는 답의 방향을 먼저 정해주면 좋아요.
                <br />
                원인을 좁힐지, 현황을 정리할지, 결론을 찾을지.
              </p>
              <br />
              <p>내가 어떤 답을 기대하는지가 정리되면, 답도 그 방향으로 더 정확해져요.</p>
            </div>
            <ExampleBox>
              <p className="text-content-normal">[예시]</p>
              <p className="text-content-alternative">
                - 원인 좁히기: [증상-문제]가 있는데 원인을 찾으려면 코드/인프라/설정 중 어디부터 봐야 할까요?
              </p>
              <p className="text-content-alternative">
                - 현황 정리: [이슈/프로젝트]의 지금 진행 상태랑 다음 액션을 정리해 주세요.
              </p>
              <p className="text-content-alternative">
                - 히스토리 찾기: [주제]에 대해 마지막으로 합의된 결론이 뭐였나요? 근거(티켓/스레드/문서)도 같이요.
              </p>
            </ExampleBox>
          </div>

          {/* 3. 기간을 말해주면 더 좋아요 */}
          <div className="flex flex-col gap-2">
            <h3 className="text-heading-large text-content-normal">3. 기간을 말해주면 더 좋아요</h3>
            <div className="text-label-medium text-content-normal">
              <p>언제부터의 기록을 봐야 하는지 알면, 최신/관련 정보를 더 잘 좁힐 수 있어요.</p>
            </div>
            <ExampleBox>
              <p className="text-content-normal">[예시]</p>
              <p className="text-content-alternative">- 오늘 오전부터 / 어제 배포 이후</p>
              <p className="text-content-alternative">- 최근 1주 / 최근 1달</p>
              <p className="text-content-alternative">- 2월 초부터 지금까지</p>
            </ExampleBox>
          </div>
        </div>
      </section>

      <DotDivider />

      {/* 섹션 2: 골라 쓰는 상황별 질문 템플릿 */}
      <section className="flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <h2 className="text-heading-xlarge text-content-strong">골라 쓰는 상황별 질문 템플릿</h2>
          <div className="text-label-medium text-content-normal">
            <p>질문을 잘 쓰는 게 은근 어렵잖아요. 특히 바쁠 때는 더 그렇고요.</p>
            <br />
            <p>그래서 Catch Up은 &quot;상황별 맞춤 프롬프트&quot;를 카드로 준비해뒀어요.</p>
            <p>
              홈 질문창 하단에서 지금 상황에 맞는 카드를 고르면, 질문창에{' '}
              <strong>추천 문장이 자동으로 채워집니다.</strong>
            </p>
            <br />
            <p>사용자는 빈칸만 내 상황에 맞게 바꾸면 돼요.</p>
          </div>
        </div>

        <div className="px-16">
          <div className="relative aspect-[1416/600] w-full">
            <Image
              src="/image/tutorial/light/tutorial-2-section-2.jpg"
              alt="상황별 질문 템플릿"
              fill
              className="object-cover dark:hidden"
            />
            <Image
              src="/image/tutorial/dark/tutorial-2-section-2.jpg"
              alt="상황별 질문 템플릿"
              fill
              className="hidden object-cover dark:block"
            />
          </div>
        </div>

        <ExampleBox>
          <p className="text-body-medium text-content-alternative">[예시]</p>
          <div className="text-label-medium text-content-alternative">
            <p>- 유사한 사례 찾기</p>
            <p>
              예전에 해결된 비슷한 케이스를 찾아서 지금 문제에 바로 연결해요. 원인·해결·결론·담당자·확인 링크까지 한
              번에 정리해드려요.
            </p>
          </div>
          <div className="text-label-medium text-content-alternative">
            <p>- 이슈 현황을 한 번에</p>
            <p>지라만 보지 않고 PR/커밋, 슬랙 논의까지 같이 보고 실제로 어디까지 진행됐는지 정리해요.</p>
          </div>
          <div className="text-label-medium text-content-alternative">
            <p>- 빠르게 히스토리 파악하기</p>
            <p>
              신규 입사자도 혼자 파악할 수 있게 배경부터 핵심 타임라인까지 모아드려요. 결정 포인트·관련자·참고 링크까지
              한 번에 볼 수 있어요.
            </p>
          </div>
          <div className="text-label-medium text-content-alternative">
            <p>- 배포 직후 문제 원인 좁히기</p>
            <p>
              최근 변경점(코드/티켓/슬랙 배포 논의)에서 원인 후보를 찾아드려요. Top 3 후보 + 근거 + 담당자 + 확인 링크로
              정리해요.
            </p>
          </div>
        </ExampleBox>

        <div className="text-label-medium text-content-normal">
          <p>
            이 카드들의 공통점은 하나예요.
            <br />
            &quot;정확하게 물어볼 수 있는 형태&quot;를 먼저 잡아주는 것.
          </p>
          <br />
          <p>
            카드를 눌러서 프롬프트를 채우고, 빈칸만 내 상황에 맞게 바꾸면 질문이 완성돼요.
            <br />그 다음부터는 저희가 근거를 찾아 붙이고, 확인할 링크까지 같이 정리해드릴게요.
          </p>
        </div>
      </section>

      <DotDivider />

      {/* 섹션 3: 완벽하게 쓰실 필요 없어요. */}
      <section className="flex flex-col gap-4">
        <h2 className="text-heading-xlarge text-content-strong">완벽하게 쓰실 필요 없어요.</h2>
        <div className="text-label-medium text-content-normal">
          <p>기억나는 단서 하나, 원하는 답 한 줄, 기간만 적어주시면 됩니다.</p>
          <p>나머지는 Catch Up이 정리할게요.</p>
          <br />
          <p>
            질문 한 번으로 원하는 답을 찾는 비결,
            <br />
            지금 바로 써먹어보아요:)
          </p>
        </div>
      </section>
    </div>
  );
}
