import type { RagSourceTypeModel, RagSourceUiModel } from '@/shared/types/ragSourceModel';
import type { SourceResponseApi } from '@/shared/types/sourceApi';

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

const getUiSourceType = (source: SourceResponseApi['source']): RagSourceTypeModel => source ?? 'unknown';

const dispatchIntegration = (
  source: SourceResponseApi,
  sourceType: RagSourceTypeModel,
): NormalizedIntegrationFields => {
  if (sourceType === 'jira') return normalizeJiraFields(source);
  if (sourceType === 'slack') return normalizeSlackFields(source);
  if (sourceType === 'github') return normalizeGithubFields(source);
  if (sourceType === 'confluence') return normalizeConfluenceFields(source);
  if (sourceType === 'channel_talk') return normalizeChannelTalkFields(source);
  return { repo: '', title: source.title ?? '', author: source.author ?? '' };
};

const normalize = (sources: SourceResponseApi[]): RagSourceUiModel[] =>
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

export const normalizeStreamSources = (sources: SourceResponseApi[]): RagSourceUiModel[] => normalize(sources);
export const normalizeHistorySources = (sources: SourceResponseApi[]): RagSourceUiModel[] => normalize(sources);
export const normalizeSources = (sources: SourceResponseApi[]): RagSourceUiModel[] => normalize(sources);
