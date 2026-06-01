'use client';

import type { ReactNode } from 'react';

import type { EntrySlug } from './entries';
import { channelTalkMetadataRenderers } from './renderers/channelTalkMetadataRenderers';
import { channelTalkRenderers } from './renderers/channelTalkRenderers';
import { panelStateRenderers } from './renderers/panelStateRenderers';
import { slackRenderers } from './renderers/slackRenderers';

const ENTRY_RENDERERS = {
  ...channelTalkRenderers,
  ...channelTalkMetadataRenderers,
  ...slackRenderers,
  ...panelStateRenderers,
} satisfies Partial<Record<EntrySlug, () => ReactNode>>;

interface EntryRendererProps {
  slug: EntrySlug;
}

export default function EntryRenderer({ slug }: EntryRendererProps) {
  const renderer = ENTRY_RENDERERS[slug];
  return renderer ? renderer() : null;
}
