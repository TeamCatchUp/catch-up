import json
import re
from collections import defaultdict

def upgrade_to_multihop(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Jira Key(CAT-숫자)를 기준으로 문서 그룹핑
    # key: "CAT-129", value: ["jira:issue:CAT-129", "github:pr:...", "slack:msg:..."]
    jira_key_map = defaultdict(set)
    
    # 전체 데이터셋을 훑으면서 ID와 텍스트 매핑
    doc_lookup = {} # doc_id -> content

    print("Analyzing relationships between documents...")
    
    # 모든 질문/문서에서 연결고리(Jira Key) 추출
    for item in data:
        doc_id = item['ground_truth_doc_id']
        question = item['question']
        
        # 문서 ID 자체에 Jira Key가 있는 경우 (Jira 문서)
        jira_match = re.search(r"(CAT-\d+)", doc_id)
        if jira_match:
            jira_key = jira_match.group(1)
            jira_key_map[jira_key].add(doc_id)
        
        # 질문 내용에 Jira Key가 있는 경우 (Slack/GitHub가 Jira 언급)
        q_match = re.search(r"(CAT-\d+)", question)
        if q_match:
            jira_key = q_match.group(1)
            jira_key_map[jira_key].add(doc_id)

    # 데이터셋 변환 (Single -> Multi)
    new_dataset = []
    converted_count = 0

    for item in data:
        question = item['question']
        original_id = item['ground_truth_doc_id']
        
        # 질문에 Jira Key가 포함되어 있다면 -> 연관된 모든 문서를 정답으로 확장
        q_match = re.search(r"(CAT-\d+)", question)
        
        if q_match:
            key = q_match.group(1)
            related_docs = list(jira_key_map[key])
            
            # 본인 하나만 있으면 그냥 유지, 2개 이상이면 Multi-hop으로 변환
            if len(related_docs) > 1:
                item['ground_truth_doc_ids'] = related_docs # 리스트로 저장
                item['type'] = 'auto_multi_hop'
                # 기존 단일 ID 필드는 삭제하거나 참고용으로 둠
                converted_count += 1
            else:
                # 연관 문서가 없으면 기존대로 리스트에 하나만 넣음
                item['ground_truth_doc_ids'] = [original_id]
        else:
            # Jira Key가 없는 일반 질문은 그냥 자기 자신만 정답
            item['ground_truth_doc_ids'] = [original_id]

        new_dataset.append(item)

    # 저장
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(new_dataset, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Converted {converted_count} queries to Multi-Hop (Set) targets.")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    upgrade_to_multihop("baseline_260212.json", "baseline_multi_hop.json")