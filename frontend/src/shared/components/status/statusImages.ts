interface StatusImageVariant {
  src: string;
  width: number;
  height: number;
}

export interface StatusImageSource {
  light: StatusImageVariant;
  dark: StatusImageVariant;
}

export const STATUS_IMAGES = {
  forbidden: {
    light: {
      src: '/image/status/forbidden-security-light.png',
      width: 199,
      height: 110,
    },
    dark: {
      src: '/image/status/forbidden-security-dark.png',
      width: 199,
      height: 109,
    },
  },
  notFound: {
    light: {
      src: '/image/status/not-found-light.png',
      width: 164,
      height: 110,
    },
    dark: {
      src: '/image/status/not-found-dark.png',
      width: 199,
      height: 125,
    },
  },
} satisfies Record<string, StatusImageSource>;
