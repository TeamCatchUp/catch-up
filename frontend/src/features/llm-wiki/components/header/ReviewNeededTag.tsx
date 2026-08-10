import IconDashCircle from '@/public/icons/icon/dash-circle.svg';
import { Badge } from '@/shared/components/ui/badge';

/**
 * 검토큐 문서 헤더(17930:57154)의 "검토 필요" 태그.
 *
 * DocumentStatusBadge("검토 완료")와 합치지 않는다 — Figma 계보가 다르다.
 * 이쪽은 `Tag` 세트(452:2178)의 type=purple(452:2175)이고, 저쪽은 Badge 계열이다.
 * 기하도 갈린다: radius 6 vs 8, padding 2/6 vs 4/8, 아이콘 18 vs 20.
 *
 * 확정된 태그는 이 1종뿐이라 라벨·색을 props로 열지 않는다(배지 발명 금지 계약).
 */
export default function ReviewNeededTag() {
  // 색은 shared Badge의 violet 변형이 Figma와 그대로 일치한다(#F0ECFE/#6541F2).
  // 기하만 이 태그 값으로 덮는다 — radius/md2 = 6px, padding 2/6, gap 4.
  return (
    <Badge variant="violet" className="text-body-xsmall rounded-md2 gap-1 px-1.5 py-0.5">
      {/* icon/dash-circle(1880:9313). 원본 export는 stroke="#464C53"이었고 currentColor로 정규화해
          Badge의 보라 글자색을 상속한다 — 확대 시안에서 아이콘과 라벨은 같은 색이다. */}
      <IconDashCircle aria-hidden className="size-4.5 shrink-0" />
      검토 필요
    </Badge>
  );
}
