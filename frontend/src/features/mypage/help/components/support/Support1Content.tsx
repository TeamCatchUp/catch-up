const DotDivider = () => (
  <div className="flex items-center justify-center gap-1.5 py-4">
    <span className="bg-content-assistive size-1 rounded-full" />
    <span className="bg-content-assistive size-1 rounded-full" />
    <span className="bg-content-assistive size-1 rounded-full" />
  </div>
);

/** 자주 묻는 질문 (FAQ) */
export default function Support1Content() {
  return (
    <div className="flex w-full flex-col gap-16">
      <DotDivider />

      {/* 1. 보안과 프라이버시 */}
      <section className="flex flex-col gap-6">
        <h2 className="text-heading-xlarge text-content-strong">1. 보안과 프라이버시 (Security &amp; Privacy)</h2>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">
            Q. 혹시 제가 볼 권한이 없는 대외비 문서도 검색되나요?
          </h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A. 아니요, 비공개 정보는 가져오지 않습니다.</strong>
            </p>
            <br />
            <p>
              Catch Up은 <strong>&apos;전사 공개&apos;</strong> 설정된 정보만 수집합니다.
            </p>
            <br />
            <p>
              누구나 볼 수 있는 Slack 퍼블릭 채널, 전체 공개된 Jira 이슈, 공용 문서만 검색 대상입니다.
              <br />
              복잡하게 권한을 따질 필요 없이, &quot;여기서 검색된다면, 우리 팀 누구나 봐도 되는 정보&quot;라고
              생각하시면 됩니다.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">Q. 개인적인 DM이나 비공개 채널은요?</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A. 절대 수집하지 않습니다.</strong>
            </p>
            <br />
            <p>
              &apos;전사 공개&apos;가 아닌 개인적인 영역(DM, 비공개 채널, 잠금 설정된 문서)은 아예 연동 대상에서
              제외됩니다.
            </p>
            <br />
            <p>
              Catch Up은 팀 전체가 공유해야 할 지식만 다룹니다.
              <br />
              개인의 사적인 영역은 건드리지 않으니 안심하세요.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">Q. 우리 회사 데이터로 AI를 학습시키나요?</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A. 아니요, 여러분의 데이터는 AI 학습에 쓰이지 않습니다.</strong>
            </p>
            <br />
            <p>
              Catch Up은 검색과 답변 생성을 위해 데이터를 &apos;참조&apos;할 뿐, 이를 외부 모델의 학습 데이터로 넘기지
              않습니다.
              <br />
              모든 데이터 처리는 보안 가이드라인 안에서 안전하게 이루어집니다.
            </p>
          </div>
        </div>
      </section>

      {/* 2. 질문 잘하는 법 */}
      <section className="flex flex-col gap-6">
        <h2 className="text-heading-xlarge text-content-strong">2. 질문 잘하는 법 (Smart Prompting)</h2>

        <div className="text-label-medium text-content-normal">
          <p>원하는 답을 한 번에 얻기 위한 핵심 요령입니다.</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">Q. 질문을 어떻게 해야 정확한 답이 나오나요?</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A.</strong> 길게 쓰지 않아도 됩니다. <strong>[단서 + 목적 + 기간]</strong> 이 3가지만 기억하세요.
            </p>
          </div>
        </div>

        <div className="bg-fill-strong border-edge-assistive flex flex-col gap-3 rounded-xl border px-5 py-4">
          <p className="text-label-medium text-content-normal">[예시]</p>
          <p className="text-label-medium text-content-normal">- 나쁜 예: &quot;로그인 안 돼.&quot; (너무 막연함)</p>
          <div className="text-label-medium text-content-normal">
            <p>
              - 좋은 예: &quot;어제 배포 이후(기간) 소셜 로그인(단서)에서 발생하는 500 에러의 담당자가
              누구야?(목적)&quot;
            </p>
            <br />
            <p>이렇게 구체적인 맥락을 주면, AI가 수많은 문서 중 정확히 필요한 것만 정리할 수 있습니다.</p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">Q. 매번 질문을 갖춰서 쓰기가 너무 번거로워요.</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A. 그래서 &apos;상황별 맞춤 프롬프트&apos;를 준비했습니다.</strong>
            </p>
            <br />
            <p>홈 화면 하단에 있는 카드들을 눌러보세요.</p>
            <br />
            <p>
              &quot;유사 사례 찾기&quot;, &quot;배포 후 원인 좁히기&quot;, &quot;히스토리 파악&quot; 등 자주 쓰는 질문
              템플릿이 자동으로 입력됩니다.
              <br />
              빈칸만 내 상황에 맞게 톡톡 바꿔주시면 질문 완성입니다.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">
            Q. 질문에 오타가 있거나, 정확한 용어가 생각 안 나면요?
          </h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A. 완벽한 단어가 아니어도 괜찮습니다.</strong>
            </p>
            <br />
            <p>Catch Up은 단순 키워드 매칭을 넘어 문장의 의미를 이해합니다.</p>
            <br />
            <p>
              &apos;결제창 오류&apos;나 &apos;결제 에러&apos;처럼 생각나는 대로 물어보세요.
              <br />
              AI가 사내 문서와 대화의 맥락을 분석해 가장 연관성 높은 기록을 찾아 연결합니다.
            </p>
          </div>
        </div>
      </section>

      {/* 3. 검증과 확인 */}
      <section className="flex flex-col gap-6">
        <h2 className="text-heading-xlarge text-content-strong">3. 검증과 확인 (Verification &amp; Citations)</h2>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">
            Q. 답변에 달린 출처가 너무 많은데, 이걸 다 읽어야 하나요?
          </h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A. 아니요, 인용된 이유부터 살펴보시면 됩니다.</strong>
            </p>
            <br />
            <p>
              다 읽으면 시간이 아깝잖아요.
              <br />
              Catch Up은 출처 리스트에 &apos;인용 이유(Reasoning)&apos;를 같이 달아둡니다.
            </p>
            <br />
            <p>
              &quot;최신 변경 사항이 포함됨&quot;, &quot;오류 원인 코드가 있음&quot;, &quot;최종 합의된 스레드&quot;
              같은 이유를 먼저 훑어보세요.
              <br />그 이유가 납득된다면 굳이 원문을 열어보지 않고 넘어가셔도 됩니다.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">
            Q. 그럼 &apos;원문 바로가기&apos;는 언제 누르면 되나요?
          </h3>
          <div className="text-label-medium text-content-normal">
            <p>
              A. &apos;결정적인 10초&apos;가 필요할 때만 누르세요. 대부분은 요약만으로 충분하지만,
              <br />
              아래 세 가지 경우에는 꼭 원문을 확인하는 게 좋습니다.
            </p>
          </div>
        </div>

        <div className="bg-fill-strong border-edge-assistive flex flex-col gap-3 rounded-xl border px-5 py-4">
          <p className="text-label-medium text-content-normal">[예시]</p>
          <p className="text-label-medium text-content-normal">
            1. <strong>숫자와 조건</strong>: 예산, 기간, 권한 설정 등 정확한 수치가 필요할 때.
          </p>
          <p className="text-label-medium text-content-normal">
            2. <strong>최종 결정</strong>: 팀의 정책이나 방향을 확정 짓고 승인해야 할 때.
          </p>
          <p className="text-label-medium text-content-normal">
            3. <strong>코드와 원인</strong>: 버그 재현 경로를 확인하거나, 실제 코드를 볼 때.
          </p>
        </div>
      </section>

      {/* 4. 데이터 연결 및 동기화 */}
      <section className="flex flex-col gap-6">
        <h2 className="text-heading-xlarge text-content-strong">
          4. 데이터 연결 및 동기화 (Files &amp; Synchronization)
        </h2>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">Q. PDF나 엑셀 파일 내용도 검색되나요?</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A. 파일 속을 뜯어보는 게 아니라, 파일이 공유된 &apos;맥락&apos;을 찾아드립니다.</strong>
            </p>
            <br />
            <p>아직 파일 내용을 직접 인덱싱하지는 않아요.</p>
            <p>
              대신 그 파일이 <strong>어떤 대화 흐름에서, 어떤 이슈와 함께 공유되었는지</strong>를 찾습니다.
            </p>
            <br />
            <p>
              예를 들어, Slack에서 &quot;이번 달 정산 내역서(xlsx) 공유합니다&quot;라고 올렸다면,
              <br />
              Catch Up은 그 메시지를 찾아 <strong>파일 원본으로 가는 링크</strong>를 제공해요.
            </p>
            <br />
            <p>
              굳이 무거운 뷰어를 띄우지 않고, 클릭 한 번으로 원본 툴에서 파일을 바로 열 수 있어 훨씬 빠르고 가볍습니다.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">Q. 캡처 이미지나 도표도 검색되나요?</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A. 이미지가 포함된 &apos;대화&apos;를 찾아드려요.</strong>
            </p>
            <br />
            <p>이미지 자체를 분석하는 게 아니라, 그 이미지를 올릴 때 나눴던 대화나 이슈 내용을 바탕으로 찾습니다.</p>
            <br />
            <p>
              &quot;로그인 화면 캡처&quot;라고 검색하면, 해당 스레드를 찾아 <strong>이미지 원본 링크</strong>를 드리는
              식이죠.
              <br />
              이미지를 설명하는 주변 텍스트가 단서가 됩니다.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-medium text-content-normal">Q. 방금 올린 자료가 검색에 안 떠요. 고장인가요?</h3>
          <div className="text-label-medium text-content-normal">
            <p>
              <strong>A.</strong> 잠깐 시간이 필요해요.
            </p>
            <br />
            <p>
              여러분이 올린 소중한 자료를 안전하게 가져와서, 검색하기 좋게 정리하는 데는
              <br />약 간의 시간(보통 수 분 이내)이 걸립니다.
            </p>
            <br />
            <p>
              특히 대용량 파일이나 긴 스레드는 조금 더 걸릴 수 있어요.
              <br />
              조금만 기다려 주시면, 깔끔하게 정리해서 보여드릴게요.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
