'use client';

import React, { useState } from 'react';

import AddSmallIcon from '@/public/icons/icon/add_small.svg';
import ArrowDownIcon from '@/public/icons/icon/arrow_down.svg';
import ArrowLeftIcon from '@/public/icons/icon/arrow_left.svg';
import ArrowRightIcon from '@/public/icons/icon/arrow_right.svg';
import CheckIcon from '@/public/icons/icon/check.svg';
import CloseIcon from '@/public/icons/icon/close.svg';
import CopyIcon from '@/public/icons/icon/copy.svg';
import DeleteIcon from '@/public/icons/icon/delete.svg';
import DownloadIcon from '@/public/icons/icon/download.svg';
import EditIcon from '@/public/icons/icon/edit_pencil.svg';
import FilterIcon from '@/public/icons/icon/filter.svg';
import HomeIcon from '@/public/icons/icon/home.svg';
import TagIcon from '@/public/icons/icon/icon_type.svg';
import InventoryIcon from '@/public/icons/icon/inventory.svg';
import KebabIcon from '@/public/icons/icon/kebab.svg';
import LinkIcon from '@/public/icons/icon/link.svg';
import SearchIcon from '@/public/icons/icon/search.svg';
import SettingsIcon from '@/public/icons/icon/settings.svg';
import ShareIcon from '@/public/icons/icon/share.svg';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/shared/components/ui/command';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/shared/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Input } from '@/shared/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { Separator } from '@/shared/components/ui/separator';
import { Switch } from '@/shared/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/ToolTip';

/* ─────────────────────────────────────────────
 * Figma icon size constant
 * All Figma button icons use a 24×24 frame (size-6).
 * Only xs icon buttons (22px) need size-5 (20px).
 * ───────────────────────────────────────────── */
const IC = 'size-6'; // 24px — Figma standard icon frame
const IC_XS = 'size-5'; // 20px — fits xs icon button (22px, 1px padding)

/* ─────────────────────────────────────────────
 * Section wrapper
 * ───────────────────────────────────────────── */
function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-heading-large text-gray-90">{title}</h2>
        {description && <p className="mt-1 text-body-small text-gray-50">{description}</p>}
      </div>
      {children}
    </section>
  );
}

function SubSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-heading-medium text-gray-70">{title}</h3>
      {children}
    </div>
  );
}

function StateRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-4">
      <span className="w-20 shrink-0 text-body-xsmall text-gray-50">{label}</span>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  );
}

function SizeLabel({ children }: { children: React.ReactNode }) {
  return <span className="text-label-xsmall text-gray-40">{children}</span>;
}

/* ─────────────────────────────────────────────
 * Nav links for quick jump
 * ───────────────────────────────────────────── */
const NAV_ITEMS = [
  'Icon Buttons',
  'Box Buttons',
  'Capsule Buttons',
  'FAB',
  'Text Buttons',
  'Input / Textfield',
  'Checkbox',
  'Switch',
  'Badge / Chips',
  'Separator',
  'Tooltip',
  'ScrollArea',
  'Tabs',
  'Select',
  'DropdownMenu',
  'Popover',
  'Command',
  'Dialog',
];

function toId(name: string) {
  return name.toLowerCase().replace(/[\s\/]+/g, '-');
}

/* ─────────────────────────────────────────────
 * PAGE
 * ───────────────────────────────────────────── */
export default function UIPreviewPage() {
  const [switchChecked, setSwitchChecked] = useState(false);
  const [checkboxChecked, setCheckboxChecked] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <TooltipProvider>
    <div className="flex min-h-screen bg-white">
      {/* ── Sticky sidebar nav ── */}
      <nav className="sticky top-0 h-screen w-56 shrink-0 overflow-y-auto border-r border-neutral-3 bg-white p-4">
        <h1 className="mb-4 text-heading-large text-gray-90">UI Preview</h1>
        <ul className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <li key={item}>
              <a
                href={`#${toId(item)}`}
                className="block rounded-lg px-2 py-1.5 text-body-xsmall text-gray-70 transition-colors hover:bg-neutral-2"
              >
                {item}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* ── Main content ── */}
      <main className="flex-1 space-y-16 p-10">
        <div>
          <h1 className="text-[28px] font-bold text-gray-90">CatchUp Design System</h1>
          <p className="mt-1 text-body-medium text-gray-50">
            shadcn/ui 기반 공통 컴포넌트 프리뷰 — Figma 디자인과 1:1 대응
          </p>
        </div>

        {/* ═══════════════════════════════════════════
         *  1. ICON BUTTONS
         *  Figma: all icon frames = 24×24, colors inherit from button variant
         *  - Solid(Blue): icon white
         *  - Outline(Gray): icon gray-70 (#33363d)
         *  - Icon Only(Gray): icon gray-50 (#6d7882)
         *  - Icon Only(Blue): icon blue-50 (#06f)
         * ═══════════════════════════════════════════ */}
        <div id={toId('Icon Buttons')}>
          <Section
            title="Icon Buttons"
            description="Icon Button은 icon으로 구성되며, 메인페이지, 헤더, 필터 등에 사용됩니다."
          >
            {/* Solid(Blue) — icon: white (inherited) */}
            <SubSection title="Solid (Blue)">
              <div className="flex items-end gap-6 mb-2">
                <SizeLabel>Large</SizeLabel>
                <SizeLabel>Medium</SizeLabel>
                <SizeLabel>Small</SizeLabel>
                <SizeLabel>Xsmall</SizeLabel>
              </div>
              <StateRow label="Default">
                <Button variant="icon-solid-blue" size="lg"><InventoryIcon className={IC} /></Button>
                <Button variant="icon-solid-blue" size="md"><InventoryIcon className={IC} /></Button>
                <Button variant="icon-solid-blue" size="sm"><InventoryIcon className={IC} /></Button>
                <Button variant="icon-solid-blue" size="xs"><InventoryIcon className={IC_XS} /></Button>
              </StateRow>
              <StateRow label="Disabled">
                <Button variant="icon-solid-blue" size="lg" disabled><InventoryIcon className={IC} /></Button>
                <Button variant="icon-solid-blue" size="md" disabled><InventoryIcon className={IC} /></Button>
                <Button variant="icon-solid-blue" size="sm" disabled><InventoryIcon className={IC} /></Button>
                <Button variant="icon-solid-blue" size="xs" disabled><InventoryIcon className={IC_XS} /></Button>
              </StateRow>
            </SubSection>

            {/* Outline(Gray) — icon: gray-70 (inherited) */}
            <SubSection title="Outline (Gray)">
              <div className="flex items-end gap-6 mb-2">
                <SizeLabel>Large</SizeLabel>
                <SizeLabel>Medium</SizeLabel>
                <SizeLabel>Small</SizeLabel>
              </div>
              <StateRow label="Default">
                <Button variant="icon-outline-gray" size="lg"><InventoryIcon className={IC} /></Button>
                <Button variant="icon-outline-gray" size="md"><InventoryIcon className={IC} /></Button>
                <Button variant="icon-outline-gray" size="sm"><InventoryIcon className={IC} /></Button>
              </StateRow>
              <StateRow label="Disabled">
                <Button variant="icon-outline-gray" size="lg" disabled><InventoryIcon className={IC} /></Button>
                <Button variant="icon-outline-gray" size="md" disabled><InventoryIcon className={IC} /></Button>
                <Button variant="icon-outline-gray" size="sm" disabled><InventoryIcon className={IC} /></Button>
              </StateRow>
            </SubSection>

            {/* Icon Only(Gray) — icon: gray-50 (inherited) */}
            <SubSection title="Icon Only (Gray)">
              <div className="flex items-end gap-6 mb-2">
                <SizeLabel>Large</SizeLabel>
                <SizeLabel>Medium</SizeLabel>
                <SizeLabel>Small</SizeLabel>
                <SizeLabel>Xsmall</SizeLabel>
              </div>
              <StateRow label="Default">
                <Button variant="icon-only-gray" size="lg"><InventoryIcon className={IC} /></Button>
                <Button variant="icon-only-gray" size="md"><InventoryIcon className={IC} /></Button>
                <Button variant="icon-only-gray" size="sm"><InventoryIcon className={IC} /></Button>
                <Button variant="icon-only-gray" size="xs"><InventoryIcon className={IC_XS} /></Button>
              </StateRow>
              <StateRow label="Disabled">
                <Button variant="icon-only-gray" size="lg" disabled><InventoryIcon className={IC} /></Button>
                <Button variant="icon-only-gray" size="md" disabled><InventoryIcon className={IC} /></Button>
                <Button variant="icon-only-gray" size="sm" disabled><InventoryIcon className={IC} /></Button>
                <Button variant="icon-only-gray" size="xs" disabled><InventoryIcon className={IC_XS} /></Button>
              </StateRow>
            </SubSection>

            {/* Icon Only(Blue) — icon: blue-50 (inherited) */}
            <SubSection title="Icon Only (Blue)">
              <div className="flex items-end gap-6 mb-2">
                <SizeLabel>Xsmall</SizeLabel>
              </div>
              <StateRow label="Default">
                <Button variant="icon-only-blue" size="xs"><InventoryIcon className={IC_XS} /></Button>
              </StateRow>
              <StateRow label="Disabled">
                <Button variant="icon-only-blue" size="xs" disabled><InventoryIcon className={IC_XS} /></Button>
              </StateRow>
            </SubSection>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  2. BOX BUTTONS
         *  Figma: icon/arrow_left + icon/arrow_right = 24×24 frame
         *  - Solid(Primary): text white, icon white
         *  - Outline(Gray): text gray-70, icon gray-70
         *  - lg: text-body-medium (17px), md: text-heading-small (15px)
         *  - sm/xs: text-body-xsmall (13px)
         * ═══════════════════════════════════════════ */}
        <div id={toId('Box Buttons')}>
          <Section
            title="Box Buttons"
            description="UI 사용되는 버튼입니다. 사용자의 action에 대한 확인 또는 동작이나 페이지를 시행합니다. Label text와 right&left icon으로 구성됩니다."
          >
            {/* Solid(Primary) — text: white, icon: white */}
            <SubSection title="Solid (Primary)">
              <div className="flex items-end gap-8 mb-2">
                <SizeLabel>Large</SizeLabel>
                <SizeLabel>Medium</SizeLabel>
                <SizeLabel>Small</SizeLabel>
                <SizeLabel>Xsmall</SizeLabel>
              </div>
              <StateRow label="Default">
                <Button variant="box-solid-primary" size="lg"><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-solid-primary" size="md"><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-solid-primary" size="sm"><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-solid-primary" size="xs"><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
              </StateRow>
              <StateRow label="Disabled">
                <Button variant="box-solid-primary" size="lg" disabled><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-solid-primary" size="md" disabled><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-solid-primary" size="sm" disabled><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-solid-primary" size="xs" disabled><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
              </StateRow>
            </SubSection>

            {/* Outline(Gray) — text: gray-70, icon: gray-70 */}
            <SubSection title="Outline (Gray)">
              <div className="flex items-end gap-8 mb-2">
                <SizeLabel>Large</SizeLabel>
                <SizeLabel>Medium</SizeLabel>
                <SizeLabel>Small</SizeLabel>
                <SizeLabel>Xsmall</SizeLabel>
              </div>
              <StateRow label="Default">
                <Button variant="box-outline-gray" size="lg"><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-outline-gray" size="md"><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-outline-gray" size="sm"><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-outline-gray" size="xs"><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
              </StateRow>
              <StateRow label="Disabled">
                <Button variant="box-outline-gray" size="lg" disabled><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-outline-gray" size="md" disabled><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-outline-gray" size="sm" disabled><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
                <Button variant="box-outline-gray" size="xs" disabled><ArrowLeftIcon className={IC} />Text<ArrowRightIcon className={IC} /></Button>
              </StateRow>
            </SubSection>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  3. CAPSULE BUTTONS
         *  Figma: icon/add_small = 24×24 frame
         *  - Solid(Primary): text white, icon white
         *  - Outline(Mono): text gray-70, icon gray-70
         *  - Outline(Blue): text blue-50, icon blue-50
         * ═══════════════════════════════════════════ */}
        <div id={toId('Capsule Buttons')}>
          <Section
            title="Capsule Buttons"
            description="Selection Bar에 사용되거나 업무 및 파일 링크로 이동하는 버튼으로 활용됩니다."
          >
            <SubSection title="Solid (Primary)">
              <StateRow label="Large">
                <Button variant="capsule-solid-primary" size="lg"><AddSmallIcon className={IC} />Text</Button>
              </StateRow>
              <StateRow label="Small">
                <Button variant="capsule-solid-primary" size="sm"><AddSmallIcon className={IC} />Text</Button>
              </StateRow>
              <StateRow label="Disabled">
                <Button variant="capsule-solid-primary" size="sm" disabled><AddSmallIcon className={IC} />Text</Button>
              </StateRow>
            </SubSection>

            <SubSection title="Outline (Mono)">
              <StateRow label="Large">
                <Button variant="capsule-outline-mono" size="lg"><AddSmallIcon className={IC} />Text</Button>
              </StateRow>
              <StateRow label="Small">
                <Button variant="capsule-outline-mono" size="sm"><AddSmallIcon className={IC} />Text</Button>
              </StateRow>
              <StateRow label="Disabled">
                <Button variant="capsule-outline-mono" size="sm" disabled><AddSmallIcon className={IC} />Text</Button>
              </StateRow>
            </SubSection>

            <SubSection title="Outline (Blue)">
              <StateRow label="Small">
                <Button variant="capsule-outline-blue" size="sm"><AddSmallIcon className={IC} />Text</Button>
              </StateRow>
              <StateRow label="Disabled">
                <Button variant="capsule-outline-blue" size="sm" disabled><AddSmallIcon className={IC} />Text</Button>
              </StateRow>
            </SubSection>

            <SubSection title="Solid (Purple / Lightblue)">
              <StateRow label="Default">
                <Button variant="capsule-solid-purple" size="sm"><AddSmallIcon className={IC} />Text</Button>
                <Button variant="capsule-solid-light-blue" size="sm"><AddSmallIcon className={IC} />Text</Button>
              </StateRow>
            </SubSection>

            <SubSection title="Epic / Task 칩 예시">
              <div className="flex items-center gap-3">
                <Button variant="capsule-solid-purple" size="sm">일본 시장 진출 리서치 범위 및 방향 정의</Button>
                <Button variant="capsule-outline-blue" size="sm">일본 진출 가설 검증 결과 정리</Button>
              </div>
            </SubSection>

            <SubSection title="파일링크 칩 예시">
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="capsule-outline-mono" size="sm"><LinkIcon className={IC} />일본 시장 경쟁사 분석 자료</Button>
                <Button variant="capsule-outline-mono" size="sm"><LinkIcon className={IC} />일본 시장 진출 가설 및 검증 결과</Button>
              </div>
            </SubSection>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  4. FAB
         *  Figma: icon 24×24, p-6 (6px)
         *  - Primary: bg #292a2d (neutral-80), icon add_small white
         *  - Secondary: bg white, border #e1e2e4, icon arrow_down gray
         *  - shadow: 0 0 4px rgba(0,0,0,0.08)
         * ═══════════════════════════════════════════ */}
        <div id={toId('FAB')}>
          <Section
            title="FAB (Floating Action Button)"
            description="Elevation으로 layer의 맨 위에 fixed 상태로 사용되는 버튼입니다. 높은 주목도를 가지며, 동작을 실행하는 Primary 타입 또는 맨위로 스크롤 동작을 시행하는 Secondary 타입을 가집니다."
          >
            <div className="flex items-center gap-6">
              <div className="text-center">
                <Button variant="fab-primary" size="md"><AddSmallIcon className={IC} /></Button>
                <p className="mt-2 text-label-xsmall text-gray-50">Primary</p>
              </div>
              <div className="text-center">
                <Button variant="fab-secondary" size="md"><ArrowDownIcon className={IC} /></Button>
                <p className="mt-2 text-label-xsmall text-gray-50">Secondary</p>
              </div>
            </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  5. TEXT BUTTONS
         *  Figma: icon/arrow_left + arrow_right = 24×24 frame (ALL sizes)
         *  - Primary Blue: text #005eeb, icon same blue
         *  - Secondary Mono: text gray-70, icon gray-70
         *  - lg: gap-6, text heading/medium (17px)
         *  - md: gap-2, text body/small (15px)
         *  - sm: gap-4, text body/xsmall (13px)
         * ═══════════════════════════════════════════ */}
        <div id={toId('Text Buttons')}>
          <Section
            title="Text Buttons"
            description="UI 사용되는 버튼입니다. 사용자의 action에 대한 확인 또는 다음 단계의 동작을 시행합니다. Label text와 right&left icon으로 구성됩니다."
          >
            <SubSection title="Primary Blue">
              <div className="flex items-end gap-6 mb-2">
                <SizeLabel>Large</SizeLabel>
                <SizeLabel>Medium</SizeLabel>
                <SizeLabel>Small</SizeLabel>
              </div>
              <StateRow label="Default">
                <Button variant="text-primary-blue" size="lg"><ArrowLeftIcon className={IC} />더보기<ArrowRightIcon className={IC} /></Button>
                <Button variant="text-primary-blue" size="md"><ArrowLeftIcon className={IC} />더보기<ArrowRightIcon className={IC} /></Button>
                <Button variant="text-primary-blue" size="sm"><ArrowLeftIcon className={IC} />더보기<ArrowRightIcon className={IC} /></Button>
              </StateRow>
            </SubSection>

            <SubSection title="Secondary Mono">
              <div className="flex items-end gap-6 mb-2">
                <SizeLabel>Large</SizeLabel>
                <SizeLabel>Medium</SizeLabel>
                <SizeLabel>Small</SizeLabel>
              </div>
              <StateRow label="Default">
                <Button variant="text-secondary-mono" size="lg"><ArrowLeftIcon className={IC} />더보기<ArrowRightIcon className={IC} /></Button>
                <Button variant="text-secondary-mono" size="md"><ArrowLeftIcon className={IC} />더보기<ArrowRightIcon className={IC} /></Button>
                <Button variant="text-secondary-mono" size="sm"><ArrowLeftIcon className={IC} />더보기<ArrowRightIcon className={IC} /></Button>
              </StateRow>
            </SubSection>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  6. INPUT / TEXTFIELD
         *  Figma node 1:6980
         *  - Large: h-[46px] p-3, border neutral-3, focus:border-blue-30
         *  - Small: h-9 px-2.5 py-1.5, border neutral-5, focus:border-blue-30
         *  - Error: border-red-50
         *  - Helper text: label/xsmall, gray-30 or red-50
         *  - Label: red-50 for required (*), gray-50 for normal
         * ═══════════════════════════════════════════ */}
        <div id={toId('Input / Textfield')}>
          <Section
            title="Input / Textfield"
            description="Large: 로그인, 회원가입 시 사용됩니다. Small: rag 키워드 필터링 등에 사용됩니다."
          >
            <SubSection title="Large (로그인/회원가입)">
              <div className="max-w-md space-y-4">
                <div>
                  <p className="mb-1 text-label-xsmall text-gray-50">Default</p>
                  <Input inputSize="lg" placeholder="아이디" />
                  <p className="mt-1 text-label-xsmall text-gray-30">영문과 숫자를 포함해 4~15자 이내로 입력하세요.</p>
                </div>
                <div>
                  <p className="mb-1 text-label-xsmall text-gray-50">Focused</p>
                  <Input inputSize="lg" placeholder="아이디" className="border-blue-30" />
                </div>
                <div>
                  <p className="mb-1 text-label-xsmall text-red-50">* 아이디</p>
                  <Input inputSize="lg" placeholder="내용을 입력해주세요." defaultValue="내용을 입력해주세요.내용을 입..." error />
                  <p className="mt-1 text-label-xsmall text-red-50">영문, 숫자 4~15자로 입력해주세요.</p>
                </div>
                <div>
                  <p className="mb-1 text-label-xsmall text-gray-50">Disabled</p>
                  <Input inputSize="lg" placeholder="아이디" disabled />
                </div>
              </div>
            </SubSection>

            <SubSection title="Small (필터/검색)">
              <div className="max-w-xs space-y-4">
                <div>
                  <p className="mb-1 text-label-xsmall text-gray-50">Default</p>
                  <Input inputSize="sm" placeholder="키워드 추가" />
                </div>
                <div>
                  <p className="mb-1 text-label-xsmall text-gray-50">Focused</p>
                  <Input inputSize="sm" placeholder="키워드 추가" className="border-blue-30" />
                </div>
                <div>
                  <p className="mb-1 text-label-xsmall text-gray-50">Disabled</p>
                  <Input inputSize="sm" placeholder="키워드 추가" disabled />
                </div>
              </div>
            </SubSection>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  7. CHECKBOX
         *  Figma node 1:6982 — icon 24×24 with 4px padding
         *  - Unselected: border neutral-3
         *  - Selected: bg blue-50, check icon white
         * ═══════════════════════════════════════════ */}
        <div id={toId('Checkbox')}>
          <Section
            title="Checkbox"
            description="다수의 항목을 선택하거나 해제할 수 있는 컴포넌트입니다."
          >
            <div className="space-y-4">
              <StateRow label="Unselected">
                <Checkbox />
              </StateRow>
              <StateRow label="Selected">
                <Checkbox checked={checkboxChecked} onCheckedChange={(v) => setCheckboxChecked(!!v)} defaultChecked />
              </StateRow>
              <StateRow label="Disabled">
                <Checkbox disabled />
                <Checkbox disabled checked />
              </StateRow>
              <div className="mt-4 flex items-center gap-2">
                <Checkbox id="terms" defaultChecked />
                <label htmlFor="terms" className="text-body-small text-gray-80 cursor-pointer">이용약관에 동의합니다</label>
              </div>
            </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  8. SWITCH
         *  Figma node 1:4477 — track 36×20, thumb 16px
         *  - Off: bg gray-20 (#cdd1d5)
         *  - On: bg blue-50 (#06f)
         *  - Thumb: white
         * ═══════════════════════════════════════════ */}
        <div id={toId('Switch')}>
          <Section
            title="Switch (Toggle)"
            description="알림받기 메뉴 등에서 on/off 토글에 사용됩니다. track 36×20, thumb 16px."
          >
            <div className="space-y-4">
              <StateRow label="Off">
                <Switch />
              </StateRow>
              <StateRow label="On">
                <Switch checked={switchChecked} onCheckedChange={setSwitchChecked} defaultChecked />
              </StateRow>
              <StateRow label="Disabled">
                <Switch disabled />
                <Switch disabled checked />
              </StateRow>
              <div className="mt-4 flex items-center gap-3">
                <span className="text-body-small text-gray-80">알림받기</span>
                <Switch defaultChecked />
              </div>
            </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  9. BADGE / CHIPS
         *  Figma node 2:4050
         *  - Category Chips: rounded, bg-color + text-color pairs
         *  - Filter Chips: capsule button variants, icon 24×24
         *  - Input Chips: h-25, border neutral, text + close icon
         *  - 부서명 Chip: icon/tag 24×24, text body/small gray-70
         * ═══════════════════════════════════════════ */}
        <div id={toId('Badge / Chips')}>
          <Section
            title="Badge / Chips"
            description="선택된 항목을 시각적으로 표기합니다. 사용자가 여러 개의 선택지를 쉽게 추가하거나 제거할 수 있도록 합니다."
          >
            <SubSection title="Category Chips (Badge variants)">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="default" size="md">Default (Blue)</Badge>
                <Badge variant="secondary" size="md">Secondary (Gray)</Badge>
                <Badge variant="success" size="md">Success (Green)</Badge>
                <Badge variant="violet" size="md">Violet</Badge>
                <Badge variant="orange" size="md">Orange</Badge>
                <Badge variant="pink" size="md">Pink</Badge>
                <Badge variant="red" size="md">Red</Badge>
              </div>
            </SubSection>

            <SubSection title="Size 비교">
              <div className="flex items-center gap-3">
                <Badge variant="default" size="md">Medium (h-7)</Badge>
                <Badge variant="default" size="sm">Small (h-6)</Badge>
              </div>
            </SubSection>

            <SubSection title="Filter Chips (Button capsule 활용)">
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="capsule-outline-mono" size="sm"><ArrowLeftIcon className={IC} />칩스<ArrowRightIcon className={IC} /></Button>
                <Button variant="capsule-outline-blue" size="sm"><ArrowLeftIcon className={IC} />칩스<ArrowRightIcon className={IC} /></Button>
              </div>
            </SubSection>

            <SubSection title="Input Chips (텍스트 + 닫기)">
              <div className="flex flex-wrap items-center gap-3">
                <span className="inline-flex h-[25px] items-center gap-1 rounded-full border border-neutral-4 bg-white px-2.5 text-body-xsmall text-gray-70">
                  text input <CloseIcon className="size-3.5 cursor-pointer text-gray-40" />
                </span>
                <span className="inline-flex h-[25px] items-center gap-1 rounded-full border border-neutral-4 bg-white px-2.5 text-body-xsmall text-gray-70">
                  유저명 text <CloseIcon className="size-3.5 cursor-pointer text-gray-40" />
                </span>
              </div>
            </SubSection>

            <SubSection title="부서명 검색 Chip">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-9 items-center gap-1 rounded-lg border border-neutral-3 bg-white px-2 text-body-small text-gray-70">
                  <TagIcon className={IC} />부서명
                </span>
                <span className="inline-flex h-9 items-center gap-1 rounded-lg border border-blue-30 bg-blue-1 px-2 text-body-small text-blue-50">
                  <TagIcon className={IC} />부서명: UXUI디...
                </span>
              </div>
            </SubSection>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  10. SEPARATOR
         * ═══════════════════════════════════════════ */}
        <div id={toId('Separator')}>
          <Section title="Separator" description="모든 곳의 divider에 사용됩니다. bg-neutral-3.">
            <div className="space-y-4 max-w-md">
              <p className="text-body-small text-gray-80">Horizontal (default)</p>
              <Separator />
              <div className="flex h-10 items-center gap-4">
                <span className="text-body-small text-gray-80">Left</span>
                <Separator orientation="vertical" />
                <span className="text-body-small text-gray-80">Right</span>
              </div>
            </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  11. TOOLTIP
         *  Figma node 2:4052
         *  - bg: rgba(0,0,0,0.75) = alpha-black-75
         *  - text: white, label/xsmall (13px, Regular)
         *  - padding: px-[6px] py-[4px]
         *  - radius: lg (8px)
         *  - shadow-tooltip
         * ═══════════════════════════════════════════ */}
        <div id={toId('Tooltip')}>
          <Section
            title="Tooltip"
            description="SNB 접힌 상태 호버시 Tooltip 인스턴스. bg-alpha-black-75, shadow-tooltip."
          >
            <p className="text-body-xsmall text-gray-50 mb-2">
              (TooltipProvider가 필요합니다. 아래는 Tooltip이 적용될 SNB 아이콘 예시입니다.)
            </p>
              <div className="flex items-center gap-6">
                {[
                  { icon: <HomeIcon className={IC} />, label: '홈' },
                  { icon: <SearchIcon className={IC} />, label: '캐치스턴트 AI' },
                  { icon: <SettingsIcon className={IC} />, label: '업무 대시보드' },
                ].map((item) => (
                  <Tooltip key={item.label}>
                    <TooltipTrigger asChild>
                      <div className="flex size-10 cursor-pointer items-center justify-center rounded-lg text-gray-50 hover:bg-neutral-2">
                        {item.icon}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="right">{item.label}</TooltipContent>
                  </Tooltip>
                ))}
              </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  12. SCROLL AREA
         * ═══════════════════════════════════════════ */}
        <div id={toId('ScrollArea')}>
          <Section title="ScrollArea" description="SNB 팀스페이스 리스트 등 스크롤이 필요한 영역에 사용됩니다.">
            <div className="w-64 rounded-2xl border border-neutral-4 bg-white">
              <ScrollArea className="h-48 p-3">
                {Array.from({ length: 20 }, (_, i) => (
                  <div key={i} className="flex h-9 items-center rounded-lg px-2 text-body-small text-gray-80 hover:bg-neutral-2">
                    팀스페이스 {i + 1}
                  </div>
                ))}
              </ScrollArea>
            </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  13. TABS
         * ═══════════════════════════════════════════ */}
        <div id={toId('Tabs')}>
          <Section title="Tabs" description="CARD 리스트 탭, 라이트/다크 세그먼트에 사용됩니다.">
            <SubSection title="기본 탭">
              <Tabs defaultValue="all" className="w-80">
                <TabsList>
                  <TabsTrigger value="all">전체</TabsTrigger>
                  <TabsTrigger value="progress">진행중</TabsTrigger>
                  <TabsTrigger value="done">완료</TabsTrigger>
                </TabsList>
                <TabsContent value="all">
                  <div className="rounded-lg border border-neutral-3 p-4 text-body-small text-gray-70">전체 리스트 콘텐츠 영역</div>
                </TabsContent>
                <TabsContent value="progress">
                  <div className="rounded-lg border border-neutral-3 p-4 text-body-small text-gray-70">진행중 리스트 콘텐츠 영역</div>
                </TabsContent>
                <TabsContent value="done">
                  <div className="rounded-lg border border-neutral-3 p-4 text-body-small text-gray-70">완료 리스트 콘텐츠 영역</div>
                </TabsContent>
              </Tabs>
            </SubSection>

            <SubSection title="라이트/다크 세그먼트">
              <Tabs defaultValue="light" className="w-48">
                <TabsList className="w-full">
                  <TabsTrigger value="light" className="flex-1">Light</TabsTrigger>
                  <TabsTrigger value="dark" className="flex-1">Dark</TabsTrigger>
                </TabsList>
              </Tabs>
            </SubSection>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  14. SELECT
         * ═══════════════════════════════════════════ */}
        <div id={toId('Select')}>
          <Section title="Select" description="CONTROLS > Dropdown (Title/Date/State) — Headless UI Listbox 대체.">
            <div className="flex flex-wrap gap-6">
              <div className="w-48">
                <p className="mb-2 text-label-xsmall text-gray-50">Title</p>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="제목 선택" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="title-asc">제목 오름차순</SelectItem>
                    <SelectItem value="title-desc">제목 내림차순</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="w-48">
                <p className="mb-2 text-label-xsmall text-gray-50">Date</p>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="날짜 선택" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="newest">최신순</SelectItem>
                    <SelectItem value="oldest">오래된순</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="w-48">
                <p className="mb-2 text-label-xsmall text-gray-50">State</p>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="상태 선택" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todo">할 일</SelectItem>
                    <SelectItem value="in-progress">진행중</SelectItem>
                    <SelectItem value="done">완료</SelectItem>
                    <SelectItem value="hold">보류</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  15. DROPDOWN MENU
         *  Figma nodes 1:6983 / 1:6984
         *  Menu items: icon 24×24, text body/small gray-80
         * ═══════════════════════════════════════════ */}
        <div id={toId('DropdownMenu')}>
          <Section
            title="DropdownMenu"
            description="HEADER '...', SNB 프로필/더보기, CHAT 컨텍스트 메뉴. MenuItem, Sub, SubTrigger, SubContent, Separator, Label, Group 포함."
          >
            <div className="flex flex-wrap items-start gap-6">
              {/* Basic */}
              <div>
                <p className="mb-2 text-label-xsmall text-gray-50">기본 드롭다운</p>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="icon-outline-gray" size="md"><KebabIcon className={IC} /></Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuLabel>메뉴</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem><EditIcon className={IC} /> 수정하기</DropdownMenuItem>
                    <DropdownMenuItem><CopyIcon className={IC} /> 복제하기</DropdownMenuItem>
                    <DropdownMenuItem><ShareIcon className={IC} /> 공유하기</DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem className="text-red-50"><DeleteIcon className={IC} /> 삭제하기</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* With SubMenu */}
              <div>
                <p className="mb-2 text-label-xsmall text-gray-50">서브메뉴 포함</p>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="icon-outline-gray" size="md"><FilterIcon className={IC} /></Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="w-56">
                    <DropdownMenuItem><SearchIcon className={IC} /> 검색</DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuSub>
                      <DropdownMenuSubTrigger><LinkIcon className={IC} /> 연결</DropdownMenuSubTrigger>
                      <DropdownMenuSubContent>
                        <DropdownMenuItem>Jira</DropdownMenuItem>
                        <DropdownMenuItem>Confluence</DropdownMenuItem>
                        <DropdownMenuItem>Github</DropdownMenuItem>
                        <DropdownMenuItem>Slack</DropdownMenuItem>
                      </DropdownMenuSubContent>
                    </DropdownMenuSub>
                    <DropdownMenuSub>
                      <DropdownMenuSubTrigger>알림받기</DropdownMenuSubTrigger>
                      <DropdownMenuSubContent>
                        <DropdownMenuItem>모든 알림</DropdownMenuItem>
                        <DropdownMenuItem>멘션만</DropdownMenuItem>
                        <DropdownMenuItem>없음</DropdownMenuItem>
                      </DropdownMenuSubContent>
                    </DropdownMenuSub>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem><SettingsIcon className={IC} /> 설정</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  16. POPOVER
         * ═══════════════════════════════════════════ */}
        <div id={toId('Popover')}>
          <Section title="Popover" description="Filter Dropdown, 공유 모달 등에 사용됩니다. shadow-dropdown-menu, rounded-2xl.">
            <div className="flex flex-wrap items-start gap-6">
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="box-outline-gray" size="md"><ShareIcon className={IC} />공유</Button>
                </PopoverTrigger>
                <PopoverContent className="w-80">
                  <div className="space-y-3">
                    <p className="text-heading-small text-gray-90">멤버 공유</p>
                    <Input inputSize="sm" placeholder="이름 또는 이메일 검색" />
                    <Separator />
                    <div className="space-y-2">
                      {['김개발', '이디자인', '박기획'].map((name) => (
                        <div key={name} className="flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-neutral-2">
                          <div className="flex items-center gap-2">
                            <div className="flex size-7 items-center justify-center rounded-full bg-blue-5 text-label-xsmall text-blue-50">
                              {name[0]}
                            </div>
                            <span className="text-body-small text-gray-80">{name}</span>
                          </div>
                          <CheckIcon className="size-4 text-blue-50" />
                        </div>
                      ))}
                    </div>
                  </div>
                </PopoverContent>
              </Popover>

              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="box-outline-gray" size="md"><FilterIcon className={IC} />필터</Button>
                </PopoverTrigger>
                <PopoverContent className="w-72">
                  <div className="space-y-3">
                    <p className="text-heading-small text-gray-90">필터 옵션</p>
                    <div className="space-y-2">
                      {['진행중', '완료', '보류', '취소'].map((status) => (
                        <div key={status} className="flex items-center gap-2">
                          <Checkbox id={`filter-${status}`} />
                          <label htmlFor={`filter-${status}`} className="text-body-small text-gray-80 cursor-pointer">{status}</label>
                        </div>
                      ))}
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
            </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  17. COMMAND
         *  Figma node 1:6979
         *  - search icon: 24×24, gray-50
         *  - item icon: 24×24
         * ═══════════════════════════════════════════ */}
        <div id={toId('Command')}>
          <Section title="Command" description="Search Bar 자동완성, 메뉴 내 검색에 사용됩니다. cmdk 기반.">
            <div className="w-80 rounded-2xl border border-neutral-4 shadow-dropdown-menu">
              <Command>
                <CommandInput placeholder="메뉴에서 검색..." />
                <CommandList>
                  <CommandEmpty>결과가 없습니다.</CommandEmpty>
                  <CommandGroup heading="페이지">
                    <CommandItem><HomeIcon className={IC} /> 홈</CommandItem>
                    <CommandItem><SearchIcon className={IC} /> 검색</CommandItem>
                    <CommandItem><SettingsIcon className={IC} /> 설정</CommandItem>
                  </CommandGroup>
                  <CommandSeparator />
                  <CommandGroup heading="액션">
                    <CommandItem><EditIcon className={IC} /> 새 문서 작성</CommandItem>
                    <CommandItem><ShareIcon className={IC} /> 공유하기</CommandItem>
                    <CommandItem><DownloadIcon className={IC} /> 내보내기</CommandItem>
                  </CommandGroup>
                </CommandList>
              </Command>
            </div>
          </Section>
        </div>

        <Separator />

        {/* ═══════════════════════════════════════════
         *  18. DIALOG
         * ═══════════════════════════════════════════ */}
        <div id={toId('Dialog')}>
          <Section title="Dialog" description="공유 모달, 태스크 상세 모달에 사용됩니다. shadow-modal, overlay: bg-alpha-white-50.">
            <div className="flex flex-wrap gap-4">
              <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="box-solid-primary" size="md">Dialog 열기</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>태스크 상세</DialogTitle>
                    <DialogDescription>
                      태스크의 상세 정보를 확인하고 수정할 수 있습니다.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <label className="text-heading-small text-gray-90">제목</label>
                      <Input inputSize="sm" placeholder="태스크 제목을 입력하세요" defaultValue="일본 시장 경쟁사 분석" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-heading-small text-gray-90">상태</label>
                      <Select defaultValue="in-progress">
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="todo">할 일</SelectItem>
                          <SelectItem value="in-progress">진행중</SelectItem>
                          <SelectItem value="done">완료</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-heading-small text-gray-90">태그</label>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="default">리서치</Badge>
                        <Badge variant="violet">마케팅</Badge>
                        <Badge variant="orange">우선순위 높음</Badge>
                      </div>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="box-outline-gray" size="md" onClick={() => setDialogOpen(false)}>취소</Button>
                    <Button variant="box-solid-primary" size="md" onClick={() => setDialogOpen(false)}>저장</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </Section>
        </div>

        {/* Bottom padding */}
        <div className="h-20" />
      </main>
    </div>
    </TooltipProvider>
  );
}
