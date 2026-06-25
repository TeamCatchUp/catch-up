import {
  HelpArticleSection,
  HelpArticleText,
  HelpDotDivider,
} from '@/features/mypage/help/components/article/HelpArticleBlocks';
import type { HelpArticleNavItem } from '@/features/mypage/help/types/helpArticle';

export const SUPPORT_3_SECTIONS = [
  { id: 'public-only', title: '1. 왜 비공개 문서는 검색되지 않나요?' },
  { id: 'private-projects', title: '2. 그럼 제 개인적인 업무나 비공개 프로젝트는요?' },
  { id: 'permission-request', title: '3. 권한이 필요한 정보도 검색하고 싶어요.' },
] as const satisfies readonly HelpArticleNavItem[];

export default function Support3Content() {
  return (
    <>
      <HelpArticleText>
        <p>캐치업은 우리 팀의 소중한 정보들이 안전하게 모이고 연결되는 곳이에요.</p>
        <br />
        <p>
          안심하고 캐치업을 사용할 수 있도록,
          <br />
          어떤 정보들을 찾아볼 수 있는지 친절하게 안내해 드릴게요.
        </p>
      </HelpArticleText>

      <HelpDotDivider />

      <HelpArticleSection {...SUPPORT_3_SECTIONS[0]}>
        <HelpArticleText>
          <p>
            <strong>지금은 &apos;모두가 보는 정보&apos;만 담았습니다.</strong>
          </p>
          <br />
          <p>
            Catch Up은 현재 <strong>&apos;전사 공개(Public)&apos;</strong> 설정된 데이터만 수집하는 것을 원칙으로
            합니다.
            <br />
            슬랙의 공개 채널이나 누구나 볼 수 있는 문서들처럼요.
          </p>
          <br />
          <p>
            &quot;여기서 찾은 건 우리 팀 누구와 나눠도 괜찮은 정보야&quot;라는 믿음을 드리기 위해,
            <br />
            가장 열려있고 안전한 이야기들로 먼저 시작했답니다.
          </p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...SUPPORT_3_SECTIONS[1]}>
        <HelpArticleText>
          <p>
            <strong>안전하게 가려져 있습니다.</strong>
          </p>
          <br />
          <p>현재 버전에서는 개인적인 DM, 비공개 채널, 특정 멤버만 볼 수 있는 문서는 기술적으로 수집하지 않아요.</p>
          <br />
          <p>
            혹시라도 민감한 정보가 의도치 않게 노출되는 일을 원천적으로 차단하기 위함입니다.
            <br />
            검색되지 않는 것이 오류가 아니라, 여러분의 보안을 지키고 있는 상태이니 안심하셔도 괜찮습니다.
          </p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...SUPPORT_3_SECTIONS[2]}>
        <HelpArticleText>
          <p>
            <strong>더 깊은 정보도 꼼꼼하게 준비하고 있습니다.</strong>
          </p>
          <br />
          <p>
            &apos;나의 비공개 문서&apos;나 &apos;접근 권한이 있는 프로젝트&apos;의 내용까지 검색하고자 하는 여러분의
            의견을 깊이 공감하며 수용하고 있어요.
          </p>
          <br />
          <p>
            현재 Catch Up은 개별 사용자의 데이터 접근 권한(ACL)을 엄격하게 통제하여, &apos;오직 허락된 정보&apos;만
            안전하게 연결하는 고도화된 보안 환경을 구축 중입니다.
          </p>
          <br />
          <p>보안은 결코 타협할 수 없는 최우선 가치이기에, 안정성이 검증될 때까지 조금만 기다려주세요.</p>
          <br />
          <p>
            공개된 지식을 넘어, 고객님만의 고유한 업무 맥락까지 가장 완벽하고 안전하게 지원해 드릴 수 있도록 최선을
            다하겠습니다.
          </p>
        </HelpArticleText>
      </HelpArticleSection>
    </>
  );
}
