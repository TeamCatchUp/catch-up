const DotDivider = () => (
  <div className="flex items-center justify-center gap-1.5 py-4">
    <span className="bg-text-normal-assistive size-1 rounded-full" />
    <span className="bg-text-normal-assistive size-1 rounded-full" />
    <span className="bg-text-normal-assistive size-1 rounded-full" />
  </div>
);

/** 협업 툴 계정 관리 */
export default function Support2Content() {
  return (
    <div className="flex w-full flex-col gap-16">
      {/* 도입부 */}
      <section className="flex flex-col gap-5">
        <h2 className="text-heading-xlarge text-text-normal-strong">
          나의 모든 이름을 하나로, Catch Up에게 알려주세요
        </h2>
        <div className="text-label-medium text-text-normal-normal">
          <p>
            우리는 업무 도구마다 조금씩 다른 이름을 씁니다.
            <br />
            Jira에서는 김철수, Slack에서는 Charles, GitHub에서는 charles_k…
            <br />
            사람은 눈치껏 알지만, <strong>시스템에게는 완전히 다른 사람으로 보일 수 있어요.</strong>
          </p>
        </div>
      </section>

      <DotDivider />

      {/* 처음 오셨나요? */}
      <section className="flex flex-col gap-5">
        <h2 className="text-heading-xlarge text-text-normal-strong">처음 오셨나요? 가장 먼저 할 일이에요</h2>
        <div className="text-label-medium text-text-normal-normal">
          <p>새로운 도구를 본격적으로 쓰기 전에, 여기서 &apos;나의 이름표&apos;를 먼저 달아주세요.</p>
          <br />
          <p>
            신규 입사자라면 회사에서 발급받은 계정들을 <strong>Catch Up에 가장 먼저 등록</strong>해두는 게 좋습니다.
            <br />
            등록하지 않은 상태로 다른 협업 툴을 이용한다면, 해당 기간 동안의 데이터는 Catch Up이 찾기 어려울 수 있어요.
          </p>
          <br />
          <p>
            Catch Up에 협업 툴에서 사용하는 닉네임, 이메일 등을 꼼꼼히 입력해주세요.
            <br />
            그래야 앞으로 쌓일 여러분의 기록들이 흩어지지 않고, 처음부터 &apos;나의 업무 맥락&apos;으로 차곡차곡
            정리되거든요.
          </p>
        </div>
      </section>

      {/* 계정이 바뀌었거나 */}
      <section className="flex flex-col gap-5">
        <h2 className="text-heading-xlarge text-text-normal-strong">계정이 바뀌었거나, 새로 추가되었나요?</h2>
        <div className="text-label-medium text-text-normal-normal">
          <p>쓰던 아이디가 바뀌었거나, 새로운 툴 계정을 받으셨나요?</p>
          <br />
          <p>
            <strong>꼭 &apos;협업 툴 연동 관리&apos; 페이지에서 수정하고 추가해주세요!</strong>
          </p>
          <br />
          <p>
            바뀐 이름표를 다시 달아주시면, 끊길 뻔한 맥락은 다시 매끄럽게 이어드려요.
            <br />
            (최대한 빠르게 수정해주세요. 수정되지 않은 기간 동안의 데이터는 Catch Up이 찾기 어려울 수 있어요.)
          </p>
        </div>
      </section>

      {/* 정확한 연결 */}
      <section className="flex flex-col gap-5">
        <h2 className="text-heading-xlarge text-text-normal-strong">
          정확한 답은 &apos;정확한 연결(Mapping)&apos;에서 나와요
        </h2>
        <div className="text-label-medium text-text-normal-normal">
          <p>
            이 과정은 단순한 등록 절차가 아니에요.
            <br />
            도구마다 흩어진 &apos;나&apos;를 하나로 묶어, AI가 &apos;이 모든 게 한 사람의 일&apos;임을 이해하게 만드는
            과정입니다.
            <br />이 연결이 정확할수록 데이터의 맥락을 읽는 <strong>임베딩(Embedding)</strong> 품질이 좋아집니다.
          </p>
        </div>

        <div className="bg-fill-normal-strong border-line-normal-assistive flex flex-col gap-3 rounded-xl border px-5 py-4">
          <p className="text-label-medium text-text-normal-normal">&quot;내가 지난주에 수정한 코드 보여줘&quot;</p>
          <p className="text-label-medium text-text-normal-normal">&quot;나한테 멘션된 이슈 찾아줘&quot;</p>
        </div>

        <div className="text-label-medium text-text-normal-normal">
          <p>
            Catch Up이 이런 질문에 헤매지 않고, 진짜 &apos;나&apos;를 위한 답을 내놓을 수 있도록 여러분의 모든 이름을
            알려주세요.
          </p>
        </div>
      </section>
    </div>
  );
}
