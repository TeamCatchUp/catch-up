export const TUTORIALS = [
  {
    id: 1,
    category: '검색 안내 튜토리얼',
    title: '검색 한 번으로 찾는 업무 정보',
    heroImage: '/image/tutorial/light/tutorial-1-hero.jpg',
  },
  {
    id: 2,
    category: '검색 안내 튜토리얼',
    title: '원하는 답을 한 번에 얻는 비결',
    heroImage: '/image/tutorial/light/tutorial-2-hero.jpg',
  },
  {
    id: 3,
    category: '계정 및 지원 안내',
    title: '정확도를 올리는 출처 확인 방법',
    heroImage: '/image/tutorial/light/tutorial-3-hero.jpg',
  },
  {
    id: 4,
    category: '가이드 ∙ 튜토리얼 보기',
    title: 'Catch Up MCP 설치하기',
  },
] as const;

export const TUTORIAL_1_FEATURE_CARDS = [
  {
    title: '한 번에 찾아요: 흩어진 도구를 같이 검색',
    description:
      'Jira 이슈, GitHub PR/코드, Slack 대화처럼 흩어진 기록을 따로따로 찾지 않아도 돼요.\n한 번의 검색으로 관련된 것들을 한데 모아 보여줍니다.',
    image: '/image/tutorial/light/tutorial-1-card-1.png',
  },
  {
    title: '답을 먼저 보여줘요: 핵심 요약',
    description:
      '검색 결과를 그대로 던지지 않아요.\n질문에 맞는 핵심만 먼저 정리해서\n"지금 필요한 답"부터 볼 수 있게 해요.',
    image: '/image/tutorial/light/tutorial-1-card-2.png',
  },
  {
    title: '왜 이걸 골랐는지 알려줘요: 인용 이유',
    description:
      "같은 주제라도 자료가 여러 개면 헷갈릴 수 있어요.\n\n그래서 '왜 이 출처가 선택됐는지'를 짧게 설명해요.\n최신이라서인지, 결론이 명확해서인지, 실제 코드/결정이 담겨 있어서인지 같은 이유를요.",
    image: '/image/tutorial/light/tutorial-1-card-3.png',
  },
  {
    title: '근거가 같이 따라와요: 핵심 발췌 + 출처 카드',
    description:
      '왜 그렇게 답했는지 궁금하잖아요.\n\nCatch Up은 답변에 쓰인 근거를 출처 카드로 같이 보여줘요.\n어느 문서/대화의 어떤 부분을 참고했는지 핵심 발췌까지 함께 확인할 수 있습니다.',
    image: '/image/tutorial/light/tutorial-1-card-4.jpg',
  },
  {
    title: '원문으로 바로 넘어가요: 딥링크로 맥락 확인',
    description:
      '요약만으로 결정하기 어려운 순간이 있죠.\n\n그럴 땐 원문을 한 번에 열어 전체 맥락을 확인할 수 있어요.\nSlack은 해당 스레드로, Jira는 이슈 상세로, GitHub는 PR/코드로 바로 이동합니다.',
    image: '/image/tutorial/light/tutorial-1-card-5.jpg',
  },
] as const;
