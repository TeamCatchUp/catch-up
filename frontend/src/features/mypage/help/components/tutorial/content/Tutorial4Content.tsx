import {
  HelpArticleSection,
  HelpArticleSubsection,
  HelpArticleText,
} from '@/features/mypage/help/components/article/HelpArticleBlocks';
import HelpCalloutBox from '@/features/mypage/help/components/article/HelpCalloutBox';
import HelpExampleBox from '@/features/mypage/help/components/article/HelpExampleBox';
import McpScriptCommands from '@/features/mypage/help/components/article/McpScriptCommands';
import type { HelpArticleNavItem } from '@/features/mypage/help/types/helpArticle';

export const TUTORIAL_4_SECTIONS = [
  { id: 'what-is-mcp', title: 'Catch Up MCP가 뭔가요?' },
  { id: 'before-install', title: '설치 전 확인해주세요' },
  { id: 'before-use', title: '사용 전 꼭 확인해주세요' },
  { id: 'claude-desktop', title: 'Claude Desktop에 설치하기' },
  { id: 'claude-code', title: 'Claude Code에 설치하기' },
  { id: 'manual-install', title: '수동 설치하기' },
  { id: 'troubleshooting', title: '문제가 생겼나요?' },
] as const satisfies readonly HelpArticleNavItem[];

export default function Tutorial4Content() {
  return (
    <>
      <HelpArticleSection {...TUTORIAL_4_SECTIONS[0]}>
        <HelpArticleText>
          <p>
            Catch Up MCP는 평소 사용하던 AI Agent가 회사의 업무 기록을 직접 검색할 수 있게 연결하는 통로입니다.
            <br />
            하나의 MCP 연결만으로 여러 협업 툴의 기록을 함께 탐색하고, 팀의 결정과 논의 맥락을 기반으로 답변합니다.
          </p>
        </HelpArticleText>

        <HelpExampleBox>
          <p>Claude에서 &quot;지난주 결제 장애 관련 Jira와 Slack 논의 찾아줘&quot;처럼 요청할 수 있어요.</p>
          <p>Claude는 Catch Up MCP를 통해 관련 기록을 찾고, 근거가 있는 답변을 구성합니다.</p>
        </HelpExampleBox>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[1]}>
        <HelpArticleText>
          <p>
            설치 전에 Catch Up에 로그인되어 있는지, 그리고 Claude Desktop 또는 Claude Code가 준비되어 있는지 확인해
            주세요.
            <br />
            회사 네트워크나 VPN이 필요한 환경이라면 먼저 접속한 뒤 진행하는 것이 좋습니다.
          </p>
        </HelpArticleText>

        <HelpCalloutBox>
          <p>1. Catch Up에 로그인되어 있는지 확인합니다.</p>
          <p>2. 사용할 Claude 앱 또는 CLI가 설치되어 있는지 확인합니다.</p>
          <p>3. 아래 명령어 중 사용할 환경에 맞는 항목을 복사해 실행합니다.</p>
        </HelpCalloutBox>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[2]}>
        <HelpArticleText>
          <p>
            설치 명령어는 현재 배포 환경의 주소를 기준으로 서버에서 내려주는 값을 그대로 표시합니다.
            <br />
            배포 주소가 바뀌어도 프론트엔드 코드를 수정하지 않고 최신 설치 명령을 확인할 수 있어요.
          </p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[3]}>
        <HelpArticleSubsection title="Mac에서 설치하기">
          <McpScriptCommands scriptKeys={['mac']} />
        </HelpArticleSubsection>

        <HelpArticleSubsection title="Windows에서 설치하기">
          <McpScriptCommands scriptKeys={['windows']} />
        </HelpArticleSubsection>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[4]}>
        <McpScriptCommands scriptKeys={['claude_code']} />
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[5]}>
        <HelpArticleText>
          <p>
            자동 설치 대신 설정 파일에 직접 추가해야 하는 경우 아래 설정 값을 사용합니다.
            <br />
            표시되는 값은 API 응답의 `claude_desktop_config`를 보기 좋게 변환한 내용입니다.
          </p>
        </HelpArticleText>

        <McpScriptCommands scriptKeys={['claude_desktop_config']} />
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[6]}>
        <HelpArticleText>
          <p>
            설치가 끝나면 Claude를 다시 실행하고 Catch Up MCP 서버가 연결되어 있는지 확인해 주세요.
            <br />
            연결이 보이지 않으면 명령어를 다시 실행하거나, 설정 파일에 추가된 값을 확인하면 됩니다.
          </p>
        </HelpArticleText>
      </HelpArticleSection>
    </>
  );
}
