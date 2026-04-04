const DotDivider = () => (
  <div className="flex items-center justify-center gap-1.5 py-4">
    <span className="bg-content-assistive size-1 rounded-full" />
    <span className="bg-content-assistive size-1 rounded-full" />
    <span className="bg-content-assistive size-1 rounded-full" />
  </div>
);

/** 오류 및 장애 */
export default function Support4Content() {
  return (
    <div className="flex w-full flex-col gap-16">
      {/* 도입부 */}
      <div className="text-label-medium text-content-normal">
        <p>
          Catch Up은 여러분의 치열한 업무 흐름을 끊지 않으려 노력하지만,
          <br />
          흩어진 지식들을 더 완벽하게 연결하기 위해 확인이 필요한 순간들이 있습니다.
        </p>
        <br />
        <p>당황하지 마세요. 대부분은 금방 해결되는 자연스러운 과정이니까요.</p>
      </div>

      <DotDivider />

      {/* 1. 검색 결과가 텅 비었나요? */}
      <section className="flex flex-col gap-5">
        <h2 className="text-heading-xlarge text-content-strong">1. 검색 결과가 텅 비었나요?</h2>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-strong">혹시 방금 작성하신 글인가요?</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              Catch Up이 Slack이나 Jira 등 원본 도구의 새로운 기록을 읽고, 전체 맥락 속에서 고르게 정리하는 데는{' '}
              <strong>잠깐의 시간이 필요합니다.</strong>
            </p>
            <br />
            <p>조금의 여유를 두고 다시 검색해 보시면, 아마 필요한 지식이 정리되어 있을거에요.</p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-strong">
            혹시 &apos;비공개&apos;로 설정된 글인가요?
          </h3>
          <div className="text-label-medium text-content-normal">
            <p>
              아무것도 나오지 않는다면, 오류가 아니라
              <br />
              Catch Up의 철저한 보안 원칙이 완벽하게 작동하고 있다는 뜻입니다.
            </p>
            <br />
            <p>
              Catch Up은 오직 전사 공개로 설정된 정보만 수집합니다.
              <br />
              개인적인 DM이나 비공개 채널의 데이터는 애초에 접근하지 않으니 안심하셔도 좋습니다.
            </p>
          </div>
        </div>
      </section>

      {/* 2. 답변이 원하던 방향과 조금 빗나갔나요? */}
      <section className="flex flex-col gap-6">
        <div className="flex flex-col gap-5">
          <h2 className="text-heading-xlarge text-content-normal">2. 답변이 원하던 방향과 조금 빗나갔나요?</h2>

          <div className="flex flex-col gap-1.5">
            <h3 className="text-heading-medium text-content-strong">질문의 폭을 조금만 더 좁혀주세요.</h3>
            <div className="text-label-medium text-content-normal">
              <p>
                수많은 업무 기록의 바다에서 나에게 딱 맞는 하나의 실마리를 건져 올리려면 &apos;작은 단서&apos;가
                필요합니다.
                <br />
                너무 포괄적인 질문보다는, AI가 집중해야 할 곳을 살짝 가리켜주세요.
              </p>
            </div>
          </div>
        </div>

        <div className="bg-fill-strong border-edge-assistive flex flex-col gap-3 rounded-xl border px-5 py-4">
          <p className="text-label-medium text-content-normal">
            <strong>[단서(기능명) + 목적(원인/현황) + 기간]</strong>을 더해보세요.
          </p>
          <div className="text-label-medium text-content-normal">
            <p>&quot;로그인 안 돼&quot; (X)</p>
            <p>
              &quot;어제(기간) 발생한 소셜 로그인(단서) 실패 원인(목적)이 뭐야?&quot; (O)
            </p>
          </div>
        </div>

        <div className="text-label-medium text-content-normal">
          <p>
            단어 몇 개만 더해주셔도, Catch Up은 숨겨진 맥락까지 파악하여 훨씬 더 선명하고 정확한 답을
            찾아냅니다.
          </p>
        </div>
      </section>

      {/* 3. 화면이 멈추거나 에러 메시지가 떴나요? */}
      <section className="flex flex-col gap-6">
        <div className="flex flex-col gap-5">
          <h2 className="text-heading-xlarge text-content-normal">3. 화면이 멈추거나 에러 메시지가 떴나요?</h2>

          <div className="flex flex-col gap-1.5">
            <h3 className="text-heading-medium text-content-strong">새로고침을 한 번 해주세요.</h3>
            <div className="text-label-medium text-content-normal">
              <p>
                사내 네트워크 환경이나 VPN 상태에 따라 연결이 일시적으로 불안정해질 수 있습니다.
                <br />
                대부분의 일시적인 엇갈림은 새로고침(F5) 한 번이면 해결됩거에요.
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <h3 className="text-heading-medium text-content-strong">
              연동 상태나 사내 보안 환경에 작은 변화가 생겼는지 확인해 주세요.
            </h3>
            <div className="text-label-medium text-content-normal">
              <p>
                [설정 &gt; 협업 툴 연동] 메뉴에서 혹시 &apos;연동 해제&apos;나 &apos;재인증 필요&apos; 상태가
                아닌지 살펴봐 주세요.
                <br />
                다음과 같은 상황에서 흔히 나타납니다.
              </p>
            </div>
          </div>
        </div>

        <div className="bg-fill-strong border-edge-assistive flex flex-col gap-3 rounded-xl border px-5 py-4">
          <ul className="text-label-medium text-content-normal list-disc space-y-3 pl-6">
            <li>사내 보안 시스템(Okta 등 통합 인증)의 권한 정보가 갱신되거나 세션이 만료된 경우</li>
            <li>
              관리자에 의해 원본 도구(Slack, Jira 등)에 설치된 Catch Up 앱이 일시적으로 삭제되거나 권한이 변경된
              경우
            </li>
          </ul>
        </div>

        <div className="text-label-medium text-content-normal">
          <p>
            이러한 경우에는 사내 관리자에게 확인을 요청해 주시면, 끊어졌던 맥락을 곧바로 다시 이어드립니다.
          </p>
        </div>
      </section>

      {/* 4. 그래도 해결되지 않는다면 */}
      <section className="flex flex-col gap-5">
        <h2 className="text-heading-xlarge text-content-normal">4. 그래도 해결되지 않는다면 (Support)</h2>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-strong">
            가장 가까운 곳에서, 가장 빠른 방법으로 돕겠습니다.
          </h3>
          <div className="text-label-medium text-content-normal">
            <p>
              문제가 생겼을 때 이메일을 쓰고 답장을 기다리는 건 우리의 업무 속도와 맞지 않죠.
              <br />
              우리는 여러분이 매일 일하시는 Slack 바로 그 안에 있습니다.
            </p>
          </div>
        </div>

        <p className="text-label-medium text-content-normal">
          <strong>▶ [Catch Up 공식 지원 채널 바로가기]</strong>
        </p>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-strong">격식은 생략하셔도 좋습니다.</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              에러 화면 캡처 한 장, 혹은 안타까운 로그 한 줄만 툭 남겨주셔도 충분합니다.
              <br />
              여러분의 업무 맥락을 깨지 않고 그 안에서 바로 해답을 찾아드리겠습니다.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-strong">여러분의 질문이 동료의 해답이 됩니다.</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              공유 채널에 남겨주신 질문은, 같은 문제를 겪을지 모르는 다른 동료들에게 훌륭한 이정표가 됩니다.
              <br />
              고민하지 말고 언제든 편하게 말을 걸어주세요.
            </p>
            <br />
            <p>끊어진 연결을 다시 단단하게 이어드리겠습니다.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
