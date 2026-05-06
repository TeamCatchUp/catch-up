'use client';

import { motion } from 'motion/react';

import { fadeInUp, MotionState, staggerListContainer } from '@/shared/motion';

interface SourceDistributionChipsProps {
  distribution: unknown;
}

const PLATFORM_LABEL: Record<string, string> = {
  jira: 'Jira',
  github: 'GitHub',
  slack: 'Slack',
  confluence: 'Confluence',
  channeltalk: 'ChannelTalk',
};

const PLATFORM_ORDER = ['confluence', 'github', 'jira', 'slack', 'channeltalk'];

const normalize = (raw: unknown): Array<{ key: string; label: string; count: number }> => {
  if (!raw || typeof raw !== 'object') return [];
  const dict = raw as Record<string, unknown>;
  const keys = Object.keys(dict).sort(
    (a, b) => PLATFORM_ORDER.indexOf(a) - PLATFORM_ORDER.indexOf(b),
  );
  return keys
    .map((k) => {
      const count = Number(dict[k] ?? 0);
      if (!Number.isFinite(count) || count <= 0) return null;
      return { key: k, label: PLATFORM_LABEL[k] ?? k, count };
    })
    .filter(Boolean) as Array<{ key: string; label: string; count: number }>;
};

export default function SourceDistributionChips({ distribution }: SourceDistributionChipsProps) {
  const entries = normalize(distribution);
  if (!entries.length) return null;

  return (
    <motion.div
      className="bg-fill-primary-normal-neutral border-edge-neutral flex w-full flex-wrap items-center gap-2.5 rounded-xl border border-solid px-4 py-3"
      initial={MotionState.Hidden}
      animate={MotionState.Visible}
      variants={staggerListContainer}
    >
      {entries.map((entry, idx) => (
        <motion.span key={entry.key} variants={fadeInUp} className="flex items-center">
          <span className="text-body-small flex items-center gap-1 whitespace-nowrap">
            <span className="text-content-neutral">{entry.label}</span>
            <span className="text-content-primary">{entry.count}</span>
          </span>
          {idx < entries.length - 1 && (
            <span aria-hidden className="border-edge-neutral ml-2.5 h-3.5 border-l border-solid" />
          )}
        </motion.span>
      ))}
    </motion.div>
  );
}
