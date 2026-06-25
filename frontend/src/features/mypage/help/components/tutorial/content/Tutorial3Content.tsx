import {
  HelpArticleSection,
  HelpArticleText,
  HelpDotDivider,
} from '@/features/mypage/help/components/article/HelpArticleBlocks';
import HelpArticleImage from '@/features/mypage/help/components/article/HelpArticleImage';
import HelpExampleBox from '@/features/mypage/help/components/article/HelpExampleBox';
import type { HelpArticleNavItem } from '@/features/mypage/help/types/helpArticle';

export const TUTORIAL_3_SECTIONS = [
  { id: 'citation-mark', title: '답변에 표시가 이미 되어 있어요' },
  { id: 'citation-reason', title: "답변 생성에 사용한 '이유'까지 보여줘요" },
  { id: 'open-original', title: '확인이 필요한 순간만 원문을 열면 돼요' },
  { id: 'ten-seconds', title: '출처 확인은 이렇게 10초면 충분해요' },
  { id: 'confident-check', title: '확인은 간편하게, 판단은 확실하게' },
] as const satisfies readonly HelpArticleNavItem[];

export default function Tutorial3Content() {
  return (
    <>
      <HelpArticleText>
        <p>
          좋은 답은 빠르기만 하면 끝이 아니에요.
          <br />
          실무에서 쓰려면 정확해야 하고, 팀이 그대로 공유해도 흔들리면 안 되죠.
        </p>
        <p>그래서 이 글에서는 &quot;출처를 확인하는 방식&quot;만 정리해볼게요.</p>
        <br />
        <p>
          출처를 전부 읽을 필요는 없어요.
          <br />왜 인용됐는지, 어떤 출처를 사용했는지만 보면 판단이 훨씬 빨라집니다.
        </p>
        <br />
        <p>Catch Up은 그 과정을 한 화면에서 끝내도록 만들었어요.</p>
      </HelpArticleText>

      <HelpDotDivider />

      <HelpArticleSection {...TUTORIAL_3_SECTIONS[0]}>
        <HelpArticleText>
          <p>
            출처를 확인하려고 원문부터 열 필요는 없어요.
            <br />
            Catch Up 답변에는 인용 표시가 붙어 있어서, &quot;어떤 문장이 어떤 근거를 썼는지&quot;가 먼저 보입니다.
          </p>
          <br />
          <p>
            궁금한 문장 옆 표시만 확인해보세요.
            <br />
            오른쪽 출처 리스트에서 해당 출처를 찾을 수 있어요.
          </p>
        </HelpArticleText>

        <HelpArticleImage
          lightSrc="/image/tutorial/light/tutorial-3-section-1.jpg"
          darkSrc="/image/tutorial/dark/tutorial-3-section-1.jpg"
          alt="답변에 표시가 이미 되어 있어요"
        />
      </HelpArticleSection>

      <HelpDotDivider />

      <HelpArticleSection {...TUTORIAL_3_SECTIONS[1]}>
        <HelpArticleImage
          lightSrc="/image/tutorial/light/tutorial-3-section-2.png"
          darkSrc="/image/tutorial/dark/tutorial-3-section-2.png"
          alt="답변 생성에 사용한 이유"
        />

        <HelpArticleText>
          <p>
            출처가 여러 개면 결국 이런 생각이 들어요.
            <br />
            이거 다 봐야 해? 어디부터 확인하지?
          </p>
          <br />
          <p>
            그래서 Catch Up은 출처를 링크로만 나열하지 않았어요.
            <br />각 출처마다 왜 이 출처가 답변 생성에 쓰였는지(인용 이유)를 같이 보여줍니다.
          </p>
          <br />
          <p>
            인용 이유를 보면 뭐가 좋아지냐면요.
            <br />
            이유를 아는 순간, 출처 확인이 훨씬 짧아져요.
          </p>
        </HelpArticleText>

        <HelpExampleBox>
          <ul className="list-disc space-y-3 pl-6">
            <li>
              그럴듯한 답을 빨리 걸러낼 수 있어요
              <br />
              인용 이유가 납득되면 믿고 진행하고, 애매하면 바로 원문을 확인하면 됩니다.
            </li>
            <li>
              확인 포인트가 정해져요
              <br />
              최신 변경이라면 &apos;최근 PR/배포&apos;만, 코드 근거라면 &apos;해당 diff&apos;만 보면 돼요.
            </li>
            <li>
              팀 합의가 빨라져요
              <br />
              근거가 무엇인지부터 다시 묻는 시간이 줄고, 같은 기준 위에서 얘기할 수 있어요.
            </li>
          </ul>
        </HelpExampleBox>

        <HelpArticleText>
          <p>결국 인용 이유는 출처를 덜 보고도 정확히 판단하게 만들어주는 장치예요.</p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpDotDivider />

      <HelpArticleSection {...TUTORIAL_3_SECTIONS[2]}>
        <HelpArticleText>
          <p>
            모든 출처를 다 열어볼 필요는 없어요.
            <br />
            다만 아래 같은 순간에는 원문 확인이 한 번 필요합니다.
          </p>
        </HelpArticleText>

        <HelpExampleBox badgeLabel="경우">
          <p>- 결정이 걸린 순간: 승인/정책/방향을 확정해야 할 때</p>
          <p>- 조건이 중요한 순간: 기간, 권한 범위, 수치가 포함될 때</p>
          <p>- 원인이 필요한 순간: 장애/버그처럼 재현과 근거가 필요할 때</p>
        </HelpExampleBox>

        <HelpArticleText>
          <p>
            이때도 &apos;어디로 가야 하는지&apos;가 명확해요.
            <br />
            Slack이면 해당 스레드로, Jira면 이슈 상세로, GitHub면 PR/커밋/코드로 바로 이어집니다.
          </p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_3_SECTIONS[3]}>
        <HelpArticleText>
          <p>처음엔 복잡해 보이지만, 실제로는 딱 이 순서면 돼요.</p>
        </HelpArticleText>

        <HelpExampleBox badgeLabel="순서">
          <p>1. 답변에서 표시 확인: 이 문장이 근거가 있는 문장인지 보기</p>
          <p>2. 인용 이유 확인: 왜 이 출처가 답변 생성에 쓰였는지 확인하기</p>
          <p>3. 필요할 때만 원문 이동: 결정에 필요한 부분만 확인하기</p>
        </HelpExampleBox>

        <HelpArticleText>
          <p>
            이 순서대로만 보면,
            <br />
            출처 확인이 부담스러운 검증이 아니라 빠르게 판단하는 방법이 돼요.
          </p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_3_SECTIONS[4]}>
        <HelpArticleText>
          <p>출처를 많이 보는 게 목표는 아니에요.</p>
          <br />
          <p>
            정보를 믿고 바로 사용해도 되는지,
            <br />
            지금 판단할 수 있는 만큼만 확인하면 충분합니다.
          </p>
          <br />
          <p>
            그럴듯한 답에 시간을 쓰지 않도록,
            <br />
            Catch Up과 함께해보세요.
          </p>
        </HelpArticleText>
      </HelpArticleSection>
    </>
  );
}
