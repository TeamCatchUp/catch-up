import { HelpArticleSection, HelpArticleText } from '@/features/mypage/help/components/article/HelpArticleBlocks';
import type { HelpArticleNavItem } from '@/features/mypage/help/types/helpArticle';

import TutorialFeatureCards from '../TutorialFeatureCards';

export const TUTORIAL_1_SECTIONS = [
  { id: 'work-time', title: '정보를 찾는 시간이 줄면, 일하는 시간이 늘어납니다.' },
  { id: 'sources', title: '출처를 같이 보여주는 이유' },
  { id: 'team-scale', title: '팀이 커질수록 효과가 커지는 이유' },
  { id: 'wrap-up', title: '마무리' },
] as const satisfies readonly HelpArticleNavItem[];

export default function Tutorial1Content() {
  return (
    <>
      <HelpArticleText>
        <p>
          필요한 정보는 사실 회사 안에 다 있어요.
          <br />
          없어서 막히는 게 아니라, 여기저기 흩어져 있어서 찾다가 시간이 새는 거죠.
        </p>
        <br />
        <p>
          기록은 Jira에, 코드는 GitHub에, 대화는 Slack에 남아 있는데
          <br />
          흩어져 있으니까 결국 &quot;이거 누가 알아?&quot; 하고 사람을 부르게 돼요.
        </p>
        <br />
        <p>질문하는 쪽도, 답하는 쪽도 일을 멈추게 되죠.</p>
        <br />
        <p>결국 서로가 서로를 방해하는 구조가 되고, 이건 팀 전체의 시간 낭비 예요.</p>
        <br />
        <p>
          그래서 Catch Up은 이런 끊김을 줄이려고 시작됐어요.
          <br />
          검색 한 번으로 흩어진 기록을 모아, 필요한 답을 근거와 함께 정리해드립니다.
        </p>
      </HelpArticleText>
      <HelpArticleSection {...TUTORIAL_1_SECTIONS[0]}>
        <HelpArticleText>
          <p>그냥 몇 분 아끼는 얘기가 아니에요.</p>
          <p>찾는 과정이 짧아질수록, 집중은 오래 가고 실행은 빨라져요.</p>
          <br />
          <p>
            그래서 저희는 생각했어요.
            <br />
            찾는 걸 빨리 해주는 것만으론 부족하고, 바로 납득하고 확인까지 갈 수 있어야 한다고요.
          </p>
          <br />
          <p>아래 기능들이 그 흐름을 만들어줍니다.</p>
        </HelpArticleText>

        <TutorialFeatureCards />
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_1_SECTIONS[1]}>
        <HelpArticleText>
          <p>
            그럴듯한 답이 제일 위험해요
            <br />
            맞는 말 같은데, 근거가 안 보이면 팀에서는 결국 다시 확인하게 되잖아요.
          </p>
          <br />
          <p>그래서 Catch Up은 출처랑 핵심 발췌, 왜 선택됐는지까지 같이 보여줘요.</p>
          <br />
          <p>
            답이 빠른 것도 중요하지만,
            <br />
            팀에서 공유되고 합의될 수 있어야 더 중요하니까요.
          </p>
          <br />
          <p>
            출처가 많다고 좋은 건 아니잖아요.
            <br />
            여러 자료가 있어도, 지금 확인해야 할 게 무엇인지 먼저 좁혀지는 게 더 중요하죠.
          </p>
          <br />
          <p>
            출처마다 &quot;왜 인용됐는지&quot;를 같이 보여주니까
            <br />
            어떤 걸 먼저 보면 될지 감이 잡히고, 확인도 훨씬 빨라집니다.
          </p>
          <br />
          <p>덕분에 팀은 같은 맥락 위에서 더 쉽게 합의하고, 다음 일을 바로 이어갈 수 있어요.</p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_1_SECTIONS[2]}>
        <HelpArticleText>
          <p>
            팀이 작을 때는 기억으로도 꽤 잘 굴러가요.
            <br />
            누가 뭘 했는지, 왜 그렇게 결정했는지 대충은 다 알고 있으니까요.
          </p>
          <br />
          <p>
            그런데 사람이 늘고 프로젝트가 쌓이면 얘기가 달라집니다.
            <br />
            기억은 자연스럽게 흩어지고, 새로 온 사람은 처음부터 다시 물어봐야 하죠.
          </p>
          <br />
          <p>
            우리가 하려는 건 사람을 대신하는 게 아니에요.
            <br />
            사람이 남긴 기록이 다음에도 바로 쓰일 수 있도록, &apos;다시 찾을 수 있는 지식&apos;으로 정리해두는 일입니다.
          </p>
          <br />
          <p>사람은 바뀌어도, 팀이 쌓아온 맥락은 남아야 하니까요.</p>
        </HelpArticleText>
      </HelpArticleSection>
      <HelpArticleSection {...TUTORIAL_1_SECTIONS[3]}>
        <HelpArticleText>
          <p>
            업무 정보는 원래 계속 쌓이고 있었어요.
            <br />
            다만 여기저기 흩어져 있고, 모양도 제각각이라 꺼내 쓰기가 어려웠을 뿐이죠.
          </p>
          <br />
          <p>
            Catch Up은 흩어진 기록을 한 번의 검색으로 연결해서,
            <br />
            팀이 다시 일의 흐름을 이어갈 수 있게 돕습니다.
          </p>
          <br />
          <p>
            찾느라 쓰던 시간,
            <br />
            이제 일하는 데 쓰세요.
          </p>
        </HelpArticleText>
      </HelpArticleSection>
    </>
  );
}
