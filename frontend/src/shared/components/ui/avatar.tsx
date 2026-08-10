'use client';

import type { ComponentProps } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import DefaultProfileIcon from '@/public/icons/icon/default_profile.svg';
import { cn } from '@/shared/utils/cn';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

/**
 * 프로필 아바타. Figma 디자인 시스템의 `imagebox/profile`(componentSet 582:2674)에 대응한다.
 *
 * size 5종은 Figma가 정의한 전부이고, 리포에서 `default_profile.svg`를 개별 import하던
 * 17곳의 크기와 그대로 겹친다. 예외는 56px(question-logs SelectedUserProfile)와
 * 70px(token-usage MemberProfileCard) 둘뿐인데, Figma에 대응 variant가 없어 넣지 않았다.
 */
const avatarVariants = cva(
  // 링(border)은 Figma가 모든 size에 거는 1px `Fill/Normal/Strong` stroke다.
  // 겹쳐 쌓았을 때 아래 아바타와의 경계를 만드는 것이 이 링의 역할이라 기본값으로 둔다.
  'border-fill-normal-strong inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border',
  {
    variants: {
      size: {
        xsmall: 'size-5', // 20px — Figma size=xsmall
        small: 'size-6.25', // 25px — size=small
        medium: 'size-7', // 28px — size=medium
        large: 'size-7.5', // 30px — size=large
        xlarge: 'size-10', // 40px — size=xlarge
      },
    },
    defaultVariants: {
      size: 'small',
    },
  },
);

export type AvatarSize = NonNullable<VariantProps<typeof avatarVariants>['size']>;

type AvatarProps = Omit<ComponentProps<'span'>, 'children'> &
  VariantProps<typeof avatarVariants> & {
    /** 프로필 이미지 URL. 비었거나 http(s)가 아니면 기본 프로필로 폴백한다. */
    src?: string | null;
    /** 이미지 대체 텍스트. 바로 옆에 이름 텍스트가 이미 있으면 비워 둔다(중복 낭독 방지). */
    alt?: string;
  };

function Avatar({ src, alt = '', size, className, ...props }: AvatarProps) {
  // 폴백 판정을 컴포넌트 안에 두는 이유: 17곳이 각자 isSafeUrl 가드를 반복하던 것을 흡수한다.
  const safeSrc = src && isSafeUrl(src) ? src : null;

  return (
    <span className={cn(avatarVariants({ size, className }))} {...props}>
      {safeSrc ? (
        // eslint-disable-next-line @next/next/no-img-element -- 임의 도메인의 프로필 URL이라 next/image 최적화 대상이 아니다
        <img src={safeSrc} alt={alt} className="size-full object-cover" />
      ) : (
        <>
          <DefaultProfileIcon aria-hidden className="size-full" />
          {alt ? <span className="sr-only">{alt}</span> : null}
        </>
      )}
    </span>
  );
}

export { Avatar, avatarVariants };
