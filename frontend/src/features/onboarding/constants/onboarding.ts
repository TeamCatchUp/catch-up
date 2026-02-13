export const POSITION_OPTIONS = ['PM', '개발', '영업'] as const;
export const RANK_OPTIONS = ['팀원', '팀장', '파트장', 'C 레벨'] as const;
export const TEAM_SIZE_OPTIONS = ['1~5명', '6~20명', '51~100명', '100명 이상'] as const;

/**
 * Onboarding form department options (feature-specific)
 * These are the actual department choices shown during user profile setup
 * Used only in ProfileStep component during onboarding flow
 *
 * Note: This is different from MOCK_DEPARTMENT_FILTER_OPTIONS in shared/mocks/search/filterOptions.ts
 * which is used for search/chat filter UI (temporary test data)
 */
export const MOCK_DEPARTMENT_OPTIONS = ['개발팀', '기획팀', '디자인팀', '영업팀'] as const;
