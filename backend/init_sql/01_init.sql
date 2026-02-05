-- pgvector 벡터 검색 기능 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 한국어 형태소 분석기 활성화 (Dockerfile.textsearch-ko 참고)
CREATE EXTENSION IF NOT EXISTS textsearch_ko;

-- 한국어 Parser 설정
ALTER TEXT SEARCH CONFIGURATION korean ADD MAPPING FOR word WITH simple;

ALTER TEXT SEARCH CONFIGURATION korean ADD MAPPING FOR asciiword, numword, hword, email, url, host, file, version, float, int, uint WITH simple;