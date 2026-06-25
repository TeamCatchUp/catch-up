import Image from 'next/image';
import Link from 'next/link';

import ArrowLeftIcon from '@/public/icons/icon/arrow_left.svg';
import { Button } from '@/shared/components/ui/button';

import type { HelpArticleLayoutProps } from '../../types/helpArticle';
import HelpArticlePrevNext from './HelpArticlePrevNext';
import HelpArticleSideNav from './HelpArticleSideNav';

export default function HelpArticleLayout({
  category,
  title,
  heroImage,
  navItems,
  prevItem,
  nextItem,
  children,
}: HelpArticleLayoutProps) {
  return (
    <div className="bg-background-normal-normal flex flex-1 overflow-y-auto">
      <main className="flex w-full flex-col px-6 pt-9 pb-30 lg:px-16">
        <div className="mx-auto flex w-full max-w-[1040px] flex-col gap-3">
          <Button
            asChild
            variant="text-secondary-mono"
            size="lg"
            className="text-heading-small text-text-normal-alternative h-9 w-fit rounded-lg px-2 py-1"
          >
            <Link href="/mypage/help">
              <ArrowLeftIcon className="text-icon-normal-alternative size-5" />
              목록보기
            </Link>
          </Button>

          <div className="border-line-normal-neutral bg-fill-normal-assistive-dark flex w-full flex-wrap items-start gap-x-14 gap-y-6 rounded-[20px] border px-8 pt-8 pb-16">
            <article className="flex min-w-0 flex-1 flex-col gap-14 lg:max-w-[680px] lg:min-w-100">
              <header className="flex w-full flex-col items-start gap-3 break-words">
                <span className="text-body-small text-text-normal-alternative">{category}</span>
                <h1 className="text-display-large text-text-normal-strong">{title}</h1>
              </header>
              {heroImage && (
                <div className="relative aspect-[1416/600] w-full max-w-[520px] overflow-hidden rounded-2xl">
                  <Image src={heroImage} alt={title} fill className="object-cover dark:hidden" />
                  <Image
                    src={heroImage.replace('/light/', '/dark/')}
                    alt={title}
                    fill
                    className="hidden object-cover dark:block"
                  />
                </div>
              )}

              <div className="flex w-full flex-col gap-14">{children}</div>
            </article>

            <HelpArticleSideNav items={navItems} />
          </div>

          <HelpArticlePrevNext prevItem={prevItem} nextItem={nextItem} />
        </div>
      </main>
    </div>
  );
}
