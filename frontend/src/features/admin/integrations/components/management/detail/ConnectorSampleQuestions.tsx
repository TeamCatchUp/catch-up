import IconCheck from '@/public/icons/icon/check.svg';

import { CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import type { IntegrationService } from '../../../types/integrationModel';

interface ConnectorSampleQuestionsProps {
  service: IntegrationService;
}

/**
 * "이렇게 물어볼 수 있어요." 예시 질문 목록.
 */
export default function ConnectorSampleQuestions({ service }: ConnectorSampleQuestionsProps) {
  const { sampleQuestions } = CONNECTOR_CONTENT[service];

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-heading-small text-text-normal-normal">이렇게 물어볼 수 있어요.</h3>
      <ul className="flex flex-col gap-2">
        {sampleQuestions.map((question) => (
          <li key={question} className="flex items-center gap-2">
            <IconCheck className="text-icon-normal-alternative size-6 shrink-0" />
            <span className="text-body-small text-text-normal-alternative">{question}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
