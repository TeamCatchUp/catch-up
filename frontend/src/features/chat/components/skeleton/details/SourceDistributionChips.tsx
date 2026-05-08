'use client';

import type { ComponentType, SVGProps } from 'react';
import { motion } from 'motion/react';

import IconChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import IconConfluence from '@/public/icons/logo/Confluence.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSlack from '@/public/icons/logo/Slack.svg';
import { fadeInUp, MotionState, staggerListContainer } from '@/shared/motion';

interface SourceDistributionChipsProps {
  distribution: unknown;
}

type PlatformIcon = ComponentType<SVGProps<SVGSVGElement>>;

const PLATFORM_ICON: Record<string, PlatformIcon> = {
  confluence: IconConfluence,
  github: IconGithub,
  jira: IconJira,
  slack: IconSlack,
  channeltalk: IconChannelTalk,
  channel_talk: IconChannelTalk,
};

const PLATFORM_ORDER = ['confluence', 'github', 'jira', 'slack', 'channeltalk', 'channel_talk'];

const normalize = (raw: unknown): Array<{ key: string; count: number }> => {
  if (!raw || typeof raw !== 'object') return [];
  const dict = raw as Record<string, unknown>;
  const keys = Object.keys(dict).sort((a, b) => PLATFORM_ORDER.indexOf(a) - PLATFORM_ORDER.indexOf(b));
  return keys
    .map((k) => {
      const count = Number(dict[k] ?? 0);
      if (!Number.isFinite(count) || count <= 0) return null;
      if (!PLATFORM_ICON[k]) return null;
      return { key: k, count };
    })
    .filter(Boolean) as Array<{ key: string; count: number }>;
};

export default function SourceDistributionChips({ distribution }: SourceDistributionChipsProps) {
  const entries = normalize(distribution);
  if (!entries.length) return null;

  return (
    <motion.div
      className="bg-blue-5 border-edge-neutral flex w-full flex-wrap items-center gap-2.5 rounded-xl border border-solid px-4 py-3"
      initial={MotionState.Hidden}
      animate={MotionState.Visible}
      variants={staggerListContainer}
    >
      {entries.map((entry, idx) => {
        const Icon = PLATFORM_ICON[entry.key];
        return (
          <motion.span key={entry.key} variants={fadeInUp} className="flex items-center">
            <span className="text-body-small flex items-center gap-1.5 whitespace-nowrap">
              <Icon className="h-6 w-6 shrink-0" aria-hidden />
              <span className="text-content-primary">{entry.count}</span>
            </span>
            {idx < entries.length - 1 && (
              <span aria-hidden className="border-edge-neutral ml-2.5 h-3.5 border-l border-solid" />
            )}
          </motion.span>
        );
      })}
    </motion.div>
  );
}
