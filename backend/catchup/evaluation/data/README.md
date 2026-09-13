# 평가 데이터

이 디렉토리에는 두 종류의 파일이 있다.

- 추적하는 파일: `vocabulary_v2.json`. 조직·문서 종류 사전이다.
- 추적하지 않는 파일: `baseline_v1.json`, `baseline_ragas_v1.json`, `baseline_multihop_v1.json`, `llm_wiki_extraction_sources_v1.yaml`. 실측 데이터라 저장소에 넣지 않는다.

추적하지 않는 파일은 별도 스토리지에서 받아 이 디렉토리에 그대로 두면 `eval_rag.py`, `eval_retriever.py`, `llm_wiki_extraction_dataset.py`가 기본 경로로 읽는다.
