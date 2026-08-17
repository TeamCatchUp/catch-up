import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import NavTree, { type NavTreeNode } from '@/shared/components/navigation/NavTree';

import type { DocumentBreadcrumb } from '../../types/llmWikiModel';

const LOCATION_ICON = { channel: IconWikiChannel, folder: IconFolder, document: IconFile } as const;

/** breadcrumb 경로를 NavTree 중첩 노드로 바꾼다. 마지막 마디가 최심 leaf다 */
function toLocationNodes(crumbs: readonly DocumentBreadcrumb[]): NavTreeNode[] {
  return crumbs.reduceRight<NavTreeNode[]>((children, crumb, index) => {
    const Icon = LOCATION_ICON[crumb.kind as keyof typeof LOCATION_ICON];
    return [{ id: `location-${index}`, label: crumb.label, Icon, children }];
  }, []);
}

interface DocumentLocationCardProps {
  breadcrumbs: readonly DocumentBreadcrumb[];
}

/** 우측 패널의 "문서 위치" 카드 — NavTree 정적 표시형의 확정 소비처다. */
export default function DocumentLocationCard({ breadcrumbs }: DocumentLocationCardProps) {
  return (
    <section className="border-line-normal-neutral flex flex-col gap-4 border-b p-4">
      <h3 className="text-body-small text-text-normal-alternative">문서 위치</h3>
      <NavTree nodes={toLocationNodes(breadcrumbs)} />
    </section>
  );
}
