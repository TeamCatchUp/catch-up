import RouterIcon from '/public/icons/icon/router_rewrite.svg';
import RetrieveIcon from '/public/icons/icon/plan_retrieve.svg';
import RerankIcon from '/public/icons/icon/rerank.svg';
import GradeIcon from '/public/icons/icon/grade.svg';
import GenerateIcon from '/public/icons/icon/generate.svg';

export const RAG_UI_STEPS: Record<
  Exclude<RagStepKey, 'manage_pr_context'>,
  {
    label: string;
    Icon: React.ComponentType<{ className?: string }>;
  }
> = {
  router: {
    label: '질문의 맥락을 파악하고 있어요.',
    Icon: RouterIcon,
  },
  retrieve: {
    label: 'Jira와 GitHub을 샅샅이 훑어보는 중...',
    Icon: RetrieveIcon,
  },
  rerank: {
    label: '수백 개 문서 중 핵심만 골라내고 있습니다.',
    Icon: RerankIcon,
  },
  grade: {
    label: '선택한 문서들이 답변 생성에 적합한지 검토중이에요.',
    Icon: GradeIcon,
  },
  generate: {
    label: '답변을 작성하고 있어요. 조금만 기다려주세요:)',
    Icon: GenerateIcon,
  },
} as const;
