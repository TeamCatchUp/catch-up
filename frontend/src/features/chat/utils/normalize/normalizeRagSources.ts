import type { ChatSource, SourceResponse } from '@/features/chat/types';

import { normalizeChannelTalkFields } from './sources/channelTalk';
import {
  buildStableSourceId,
  formatCreatedAt,
  getSourceContent,
  getSourceLink,
  type NormalizedIntegrationFields,
} from './sources/common';
import { normalizeConfluenceFields } from './sources/confluence';
import { normalizeGithubFields } from './sources/github';
import { normalizeJiraFields } from './sources/jira';
import { normalizeSlackFields } from './sources/slack';

const getUiSourceType = (source: SourceResponse['source']): ChatSource['source_type'] => source ?? 'unknown';

const dispatchIntegration = (
  source: SourceResponse,
  sourceType: ChatSource['source_type'],
): NormalizedIntegrationFields => {
  if (sourceType === 'jira') return normalizeJiraFields(source);
  if (sourceType === 'slack') return normalizeSlackFields(source);
  if (sourceType === 'github') return normalizeGithubFields(source);
  if (sourceType === 'confluence') return normalizeConfluenceFields(source);
  if (sourceType === 'channel_talk') return normalizeChannelTalkFields(source);
  return { repo: '', title: source.title ?? '', author: source.author ?? '' };
};

const normalize = (sources: SourceResponse[]): ChatSource[] =>
  (sources ?? []).map((source, index) => {
    const sourceType = getUiSourceType(source.source);
    const integration = dispatchIntegration(source, sourceType);

    return {
      id: buildStableSourceId(source, index),
      source_type: sourceType,
      entity_type: source.entity_type,
      is_cited: source.is_cited ?? false,
      content: getSourceContent(source),
      date: formatCreatedAt(source.created_at),
      html_url: getSourceLink(source),
      source_index: typeof source.index === 'number' ? source.index : index + 1,
      ...integration,
    };
  });

export const normalizeStreamSources = (sources: SourceResponse[]): ChatSource[] => normalize(sources);
export const normalizeHistorySources = (sources: SourceResponse[]): ChatSource[] => normalize(sources);
export const normalizeSources = (sources: SourceResponse[]): ChatSource[] => normalize(sources);
