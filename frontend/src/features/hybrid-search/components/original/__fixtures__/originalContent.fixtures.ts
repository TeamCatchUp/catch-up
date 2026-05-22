// dev preview 갤러리(app/(dev)/original-panel) 전용 목 데이터 진입점.
// 1.3 케이스 매트릭스를 content / message / metadata / response 파일로 분할해 재노출한다.
// 모든 fixture는 originalApi.ts 타입으로 검증됨.

export {
  blockContentBulletsNested,
  blockContentBulletsSingle,
  blockContentCodeLong,
  blockContentCodeShort,
  // block
  blockContentMarkdown,
  blockContentMixed,
  blockContentPlainText,
  buttonContentMultiple,
  // button
  buttonContentSingle,
  fileContentMultiple,
  // file
  fileContentSingle,
  formContentEmptyInputs,
  // form
  formContentVariedInputs,
  textContentLong,
  // text
  textContentShort,
} from './content.fixtures';
export {
  messageAuthorNull,
  messageAvatarNull,
  messageCreatedAtNull,
  messageCustomerPublic,
  messageInternal,
  messageItemVariants,
  messageManagerPublic,
  messageMultiContentBlockButton,
  messageMultiContentBlockFile,
  messageNameNull,
} from './message.fixtures';
export {
  customerFull,
  customerPartial,
  metadataDetailAbsent,
  metadataFull,
  metadataNoTags,
  metadataVariants,
} from './metadata.fixtures';
export {
  emptyConversationResponse,
  fullConversationResponse,
} from './response.fixtures';
