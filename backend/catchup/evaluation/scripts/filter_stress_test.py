import json

def extract_stress_test_set(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    stress_cases = []
    for item in data:
        # 정답 ID가 2개 이상인 경우만 추출
        if len(item.get('ground_truth_doc_ids', [])) > 1:
            stress_cases.append(item)
            
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(stress_cases, f, ensure_ascii=False, indent=2)
        
    print(f"Extracted {len(stress_cases)} multi-hop cases out of {len(data)}.")
    print(f"Saved to: {output_file}")

# 실행
extract_stress_test_set("baseline_multi_hop.json", "stress_test_multi_hop.json")