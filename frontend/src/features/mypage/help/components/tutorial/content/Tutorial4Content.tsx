import {
  HelpArticleEmphasis,
  HelpArticleQuote,
  HelpArticleSection,
  HelpArticleStep,
  HelpArticleText,
} from '@/features/mypage/help/components/article/HelpArticleBlocks';
import HelpCommandBlock from '@/features/mypage/help/components/article/HelpCommandBlock';
import McpScriptCommands from '@/features/mypage/help/components/article/McpScriptCommands';
import type { HelpArticleNavItem } from '@/features/mypage/help/types/helpArticle';
import ArrowOutwardIcon from '@/public/icons/icon/arrow_outward.svg';
import ClaudeIcon from '@/public/icons/logo/claude.svg';

export const TUTORIAL_4_SECTIONS = [
  { id: 'what-is-mcp', title: 'Catch Up MCP가 뭔가요?' },
  { id: 'before-install', title: '설치 전 확인해주세요' },
  { id: 'before-use', title: '사용 전 꼭 확인해주세요' },
  { id: 'claude-desktop', title: 'Claude Desktop에 설치하기' },
  { id: 'claude-code', title: 'Claude Code에 설치하기' },
  { id: 'troubleshooting', title: '문제가 생겼나요?' },
  { id: 'manual-install', title: '수동 설치 방법(추가)' },
] as const satisfies readonly HelpArticleNavItem[];

const NODE_WINDOWS_INSTALL_COMMAND = 'winget install -e --id OpenJS.NodeJS';
const NODE_MAC_INSTALL_COMMAND = 'brew install node@24';
const NODE_VERSION_COMMAND = 'node --version  # 예) v24.17.0';

function ClaudeDownloadCard() {
  return (
    <a
      href="https://claude.com/download"
      target="_blank"
      rel="noreferrer"
      className="border-line-normal-neutral bg-fill-normal-normal flex w-full max-w-[520px] items-center gap-4 rounded-xl border p-3"
    >
      <ClaudeIcon aria-hidden className="size-10 shrink-0" />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-center gap-2.5">
          <span className="text-reading-body-md-small text-text-normal-normal">Claude</span>
          <span className="bg-fill-normal-interaction-hover rounded-md2 flex size-[22px] items-center justify-center">
            <ArrowOutwardIcon className="text-icon-normal-normal size-[18px]" />
          </span>
        </span>
        <span className="text-label-xsmall text-text-normal-alternative truncate">https://claude.com/download</span>
      </span>
    </a>
  );
}

export default function Tutorial4Content() {
  return (
    <>
      <HelpArticleSection {...TUTORIAL_4_SECTIONS[0]}>
        <HelpArticleText className="flex flex-col gap-4 whitespace-pre-wrap">
          <p>Catch Up MCP는 평소에 쓰던 AI Agent가 회사 안의 업무 맥락을 직접 찾아볼 수 있게 해주는 연결 도구입니다.</p>
          <p>
            Slack, Jira, Confluence, GitHub, ChannelTalk에 흩어져 있는 자료를 AI Agent가 한 번에 검색할 수 있어요. 우리
            팀이 어떤 결정을 했는지, 어떤 이슈가 있었는지, 어떤 논의가 오갔는지까지 맥락을 이해하고 답변합니다.
          </p>
          <p>
            여러 서비스를 각각 연결할 필요는 없습니다.
            <br />
            <HelpArticleEmphasis>Catch Up MCP</HelpArticleEmphasis> 하나만 설치하면, 여러 업무 도구의 정보를 한 번에
            탐색할 수 있습니다.
          </p>
          <p>
            Catch Up은 사전에 인덱싱된 데이터를 기반으로 검색하기 때문에, 정확한 키워드를 몰라도 괜찮습니다.
            <br />
            “그때 논의했던 내용”, “이 기능이 왜 이렇게 바뀌었는지”, “비슷한 이슈가 있었는지”처럼 자연스럽게 물어봐도
            관련 맥락을 빠르게 찾아줍니다.
          </p>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[1]}>
        <HelpArticleText className="flex flex-col gap-4">
          <p className="text-reading-heading-sb-medium">설치하기 전에 아래 항목을 먼저 확인해주세요.</p>
          <ul className="list-disc pl-6">
            <li>사내 VPN에 연결되어 있어야 합니다.</li>
            <li>Catch Up에 회원가입된 사용자만 이용할 수 있습니다.</li>
            <li>회사 SSO 계정으로 로그인할 수 있어야 합니다.</li>
            <li>
              Catch Up MCP는 <HelpArticleEmphasis>Claude Desktop</HelpArticleEmphasis> 또는{' '}
              <HelpArticleEmphasis>Claude Code</HelpArticleEmphasis>에서 사용할 수 있습니다.
            </li>
          </ul>
        </HelpArticleText>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[2]}>
        <HelpArticleText className="flex flex-col gap-4">
          <p>
            Catch Up MCP는 <HelpArticleEmphasis>Claude Desktop</HelpArticleEmphasis>과{' '}
            <HelpArticleEmphasis>Claude Code</HelpArticleEmphasis>에서 사용할 수 있습니다.
          </p>
          <p>
            <HelpArticleEmphasis>웹 브라우저 화면에서는 사용할 수 없습니다.</HelpArticleEmphasis>
            <br />
            보안 정책으로 인해 VPN 환경에서만 동작하기 때문에 웹에서는 사용할 수 없습니다.
            <br />
            브라우저에서 Claude를 사용 중이라면, 먼저 Claude Desktop을 설치한 뒤 아래 안내에 따라 Catch Up MCP를
            연결해주세요.
          </p>
        </HelpArticleText>
        <ClaudeDownloadCard />
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[3]}>
        <div className="flex flex-col gap-8">
          <HelpArticleStep order={1} title="Claude Desktop에 설치하기">
            <HelpArticleText>
              <p>Claude Desktop이 아직 없다면 먼저 설치해주세요.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep order={2} title="설치 명령어 복사하기">
            <HelpArticleText>
              <p>Catch Up 서비스에 접속한 뒤 아래 경로로 이동합니다.</p>
              <p>
                <HelpArticleEmphasis>우측 상단 프로필 → MCP 설치</HelpArticleEmphasis>
              </p>
              <p>사용 중인 운영체제에 맞는 명령어를 복사해주세요.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep title="Mac">
            <HelpArticleText>
              <p>터미널을 열고, 복사한 명령어를 붙여넣은 뒤 Enter를 누릅니다.</p>
            </HelpArticleText>
            <McpScriptCommands scriptKeys={['mac']} showHeader={false} />
          </HelpArticleStep>

          <HelpArticleStep title="Windows">
            <HelpArticleText>
              <p>PowerShell을 열고, 복사한 명령어를 붙여넣은 뒤 Enter를 누릅니다.</p>
            </HelpArticleText>
            <McpScriptCommands scriptKeys={['windows']} showHeader={false} />
          </HelpArticleStep>

          <HelpArticleStep order={3} title="Claude Desktop 재시작하기">
            <HelpArticleText>
              <p>설치가 끝나면 Claude Desktop을 완전히 종료한 뒤 다시 실행해주세요.</p>
              <p>단순히 창만 닫는 것이 아니라, 시스템 트레이에서 앱을 완전히 종료해야 합니다.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep order={4} title="SSO 로그인하기">
            <HelpArticleText>
              <p>
                Claude Desktop을 다시 실행하면 SSO 로그인 화면이 열립니다.
                <br />
                회사 계정으로 로그인해주세요.
              </p>
              <p>로그인이 완료되면 Catch Up MCP 연결이 활성화됩니다.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep order={5} title="연결 확인하기">
            <HelpArticleText>
              <p>Claude Desktop 채팅창에 아래처럼 입력해보세요.</p>
            </HelpArticleText>
            <HelpArticleQuote>
              <p>Catch Up 연결됐어?</p>
            </HelpArticleQuote>
            <HelpArticleText>
              <p>또는 Claude Desktop 설정에서 커넥터 목록에 Catch Up이 표시되는지 확인할 수 있습니다.</p>
            </HelpArticleText>
          </HelpArticleStep>
        </div>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[4]}>
        <div className="flex flex-col gap-8">
          <HelpArticleStep order={1} title="Claude Code에 설치하기">
            <HelpArticleText>
              <p>Claude Code가 아직 없다면 먼저 설치해주세요.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep order={2} title="설치 명령어 복사하기">
            <HelpArticleText>
              <p>Catch Up 서비스에 접속한 뒤 아래 경로로 이동합니다.</p>
              <p>
                <HelpArticleEmphasis>우측 상단 프로필 → MCP 설치</HelpArticleEmphasis>
              </p>
              <p>Claude Code 명령어를 복사해주세요.</p>
            </HelpArticleText>
            <McpScriptCommands scriptKeys={['claude_code']} showHeader={false} />
          </HelpArticleStep>

          <HelpArticleStep order={3} title="연결 확인하기">
            <HelpArticleText>
              <p>Claude Code에서 /mcp를 입력하고 catch-up이 표시되는지 확인해주세요.</p>
            </HelpArticleText>
          </HelpArticleStep>
        </div>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[5]}>
        <div className="flex flex-col gap-8">
          <HelpArticleStep title="Windows에서 PowerShell 실행이 막혀요">
            <HelpArticleText>
              <p>
                PowerShell을 사용하고 있는지 먼저 확인해주세요.
                <br />
                명령 프롬프트(cmd)가 아니라 PowerShell에서 실행해야 합니다.
              </p>
              <p>
                보안 정책 때문에 실행이 제한될 수 있습니다.
                <br />
                제공된 설치 명령어에는 일회성 실행 권한 설정이 포함되어 있지만, 회사 보안 정책에 따라 추가 제한이 있을
                수 있습니다.
              </p>
              <p>이 경우 사내 관리자에게 PowerShell 오류 메시지를 전달해주세요.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep title="Claude Code에서 catch-up이 보이지 않아요">
            <HelpArticleText>
              <p>설치 명령어가 정상적으로 등록되지 않았을 수 있습니다.</p>
              <p>아래 명령어를 다시 실행해주세요.</p>
            </HelpArticleText>
            <McpScriptCommands scriptKeys={['claude_code']} showHeader={false} />
            <HelpArticleText>
              <p>그다음 Claude Code에서 /mcp를 입력하고 catch-up이 표시되는지 확인해주세요.</p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep title="Claude.ai에서 Catch Up이 로드되지 않아요.">
            <HelpArticleText>
              <p>
                Catch Up MCP는 현재 Claude Desktop과 Claude Code에서만 사용할 수 있습니다.
                <br />
                <a href="http://claude.ai/" target="_blank" rel="noreferrer" className="underline">
                  http://claude.ai
                </a>{' '}
                웹 브라우저에서는 MCP 서버의 도구가 로드되지 않습니다.
              </p>
              <p>
                브라우저에서 Claude를 사용 중이라면 Claude Desktop을 설치한 뒤, 이 문서의 Claude Desktop에 설치하기
                안내를 따라주세요.
              </p>
            </HelpArticleText>
          </HelpArticleStep>

          <HelpArticleStep title="인증 URL에 접속했는데 인증이 실패해요">
            <HelpArticleText className="flex flex-col gap-4">
              <p>아래 항목을 확인해주세요.</p>
              <ul className="list-disc pl-6">
                <li>회사 SSO 계정으로 로그인했는지 확인해주세요.</li>
                <li>Catch Up에 회원가입된 사용자 계정인지 확인해주세요.</li>
                <li>사내 VPN에 연결되어 있는지 확인해주세요.</li>
                <li>인증 URL이 만료되었다면 Claude에서 다시 Authenticate를 눌러 새 URL로 접속해주세요.</li>
              </ul>
            </HelpArticleText>
          </HelpArticleStep>

          <div className="flex flex-col gap-3">
            <h3 className="text-heading-xlarge text-text-normal-normal">계속 해결되지 않는다면</h3>
            <HelpArticleText className="flex flex-col gap-4">
              <p>문제가 계속되면 아래 정보를 함께 전달해주세요.</p>
              <ul className="list-disc pl-6">
                <li>사용 중인 환경: Mac / Windows / Claude Desktop / Claude Code</li>
                <li>실행한 설치 명령어</li>
                <li>오류가 발생한 단계</li>
                <li>화면에 표시된 오류 메시지</li>
                <li>VPN 연결 여부</li>
                <li>Catch Up 서비스 접속 가능 여부</li>
              </ul>
              <p>이 정보를 함께 보내주시면 원인을 더 빠르게 확인할 수 있습니다.</p>
            </HelpArticleText>
          </div>
        </div>
      </HelpArticleSection>

      <HelpArticleSection {...TUTORIAL_4_SECTIONS[6]} titleClassName="text-display-large text-text-normal-normal">
        <div className="flex flex-col gap-4">
          <h3 className="text-heading-xlarge text-text-normal-normal">Claude Desktop</h3>
          <HelpArticleText>
            <ol className="list-decimal pl-6">
              <li>Node.js를 설치합니다.</li>
            </ol>
          </HelpArticleText>

          <HelpArticleStep title="Window">
            <HelpCommandBlock value={NODE_WINDOWS_INSTALL_COMMAND} ariaLabel="Windows Node.js 설치 명령어 복사" />
          </HelpArticleStep>

          <HelpArticleStep title="Mac">
            <HelpCommandBlock value={NODE_MAC_INSTALL_COMMAND} ariaLabel="Mac Node.js 설치 명령어 복사" />
          </HelpArticleStep>

          <HelpArticleStep title="설치 상태 확인">
            <HelpCommandBlock value={NODE_VERSION_COMMAND} ariaLabel="Node.js 설치 상태 확인 명령어 복사" />
          </HelpArticleStep>

          <HelpArticleText>
            <ol className="list-decimal pl-6" start={2}>
              <li>Claude Desktop을 실행합니다.</li>
              <li>설정 &gt; 개발자 탭을 선택합니다.</li>
              <li>‘구성 편집’ 버튼을 선택합니다.</li>
              <li>파일 탐색기가 열리면 claude_desktop_config.json 파일을 안전한 장소에 백업합니다.</li>
              <li>해당 파일을 열어 아래와 같이 편집합니다.</li>
            </ol>
          </HelpArticleText>

          <McpScriptCommands scriptKeys={['claude_desktop_config']} showHeader={false} />

          <HelpArticleText>
            <ol className="list-decimal pl-6" start={6}>
              <li>Claude Desktop을 완전히 종료하고 재시작합니다.</li>
              <li>잠시 뒤 SSO 인증 화면이 팝업되며 로그인을 진행합니다.</li>
              <li>커넥터 목록 또는 Claude를 통해 Catch Up MCP 사용 가능 여부를 확인합니다.</li>
            </ol>
          </HelpArticleText>
        </div>
      </HelpArticleSection>
    </>
  );
}
