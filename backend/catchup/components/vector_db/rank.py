from typing import List
from langchain_core.documents import Document

def weighted_reciprocal_rank(
    doc_lists: List[List[Document]], 
    weights: List[float], 
    c: int = 60
) -> List[Document]:
    """
    Weighted Reciprocal Rank Fusion (RRF) 알고리즘 구현
    
    doc_lists: 각 리트리버의 검색 결과 리스트들의 리스트 [[doc1, doc2], [doc3, doc4]]
    weights: 각 리트리버에 부여할 가중치
    c: RRF 상수 (default=60)
    """
    if len(doc_lists) != len(weights):
        raise ValueError("검색 결과 리스트 수와 가중치 수가 일치해야 합니다.")

    doc_scores = {}
    doc_map = {}

    for doc_list, weight in zip(doc_lists, weights):
        if not doc_list: continue
        
        for rank, doc in enumerate(doc_list):
            # 문서 식별
            doc_key = doc.id if doc.id else doc.metadata.get('id')
            if doc_key not in doc_map:
                doc_map[doc_key] = doc
            
            # RRF 공식: Weight * (1 / (rank + c))
            score = weight * (1 / (rank + c))
            doc_scores[doc_key] = doc_scores.get(doc_key, 0) + score

    # 점수 내림차순 정렬
    sorted_docs = sorted(doc_scores.items(), key=lambda item: item[1], reverse=True)
    
    return [doc_map[doc_key] for doc_key, score in sorted_docs]