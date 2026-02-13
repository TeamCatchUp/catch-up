import json
import time
import math
import sys
import os
import csv
from datetime import datetime
from tqdm import tqdm


current_dir = os.path.dirname(os.path.abspath(__file__))  # evaluation
catchup_dir = os.path.dirname(current_dir)                   # catchup
backend_dir = os.path.dirname(catchup_dir)                   # backend (ROOT)

if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from catchup.components.vector_db.factory import VectorDbProvider, get_vector_db_service

vector_service = get_vector_db_service(VectorDbProvider.PGVECTOR)

# CSV & Data Paths
CSV_FILE_PATH = os.path.join(current_dir, "evaluation_history.csv")
DATA_DIR = os.path.join(current_dir, "data")

def save_result_to_csv(filename, s_weight, k_weight, top_k, metrics):
    file_exists = os.path.isfile(CSV_FILE_PATH)
    
    with open(CSV_FILE_PATH, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        if not file_exists:
            header = [
                "Timestamp", 
                "Dataset File", 
                "Semantic Weight", 
                "Keyword Weight", 
                "Top K", 
                "Hit Rate", 
                "MRR", 
                "NDCG", 
                "Avg Latency (s)"
            ]
            writer.writerow(header)
            
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            filename,
            s_weight,
            k_weight,
            top_k,
            f"{metrics['hit_rate']:.4f}",
            f"{metrics['mrr']:.4f}",
            f"{metrics['ndcg']:.4f}",
            f"{metrics['avg_latency']:.4f}"
        ]
        writer.writerow(row)
    
    print(f"Result saved to {os.path.basename(CSV_FILE_PATH)}")

def evaluate_retrieval(dataset_path: str, semantic_weight: float, keyword_weight: float, top_k: int):
    if not os.path.exists(dataset_path):
        print(f"Error: Dataset file not found at {dataset_path}")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    filename = os.path.basename(dataset_path)
    print(f"Evaluation Started: {len(test_cases)} cases")
    print(f"Configuration: File={filename}, Semantic={semantic_weight}, Keyword={keyword_weight}, K={top_k}")

    hits = 0
    mrr_sum = 0.0
    ndcg_sum = 0.0
    start_time = time.time()

    for case in tqdm(test_cases, desc="Processing"):
        query = case['question']
        gt_id = case['ground_truth_doc_id']

        try:
            results = vector_service.hybrid_search(
                query=query,
                k=top_k,
                weights=[semantic_weight, keyword_weight]
            )

            found_rank = -1
            for rank, doc in enumerate(results):
                ret_id = doc.id if hasattr(doc, 'id') and doc.id else doc.metadata.get('id')
                
                if str(ret_id) == str(gt_id):
                    found_rank = rank + 1
                    break

            if found_rank > 0:
                hits += 1
                mrr_sum += 1.0 / found_rank
                ndcg_sum += 1.0 / math.log2(found_rank + 1)

        except Exception as e:
            print(f"Query Error: {query} -> {str(e)}")

    total = len(test_cases)
    metrics = {
        "hit_rate": hits / total,
        "mrr": mrr_sum / total,
        "ndcg": ndcg_sum / total,
        "avg_latency": (time.time() - start_time) / total
    }

    print("\n" + "="*50)
    print(f"Evaluation Results (K={top_k})")
    print(f"Weights: Semantic={semantic_weight}, Keyword={keyword_weight}")
    print("="*50)
    print(f"HIT_RATE    : {metrics['hit_rate']:.2%}")
    print(f"MRR         : {metrics['mrr']:.4f}")
    print(f"NDCG        : {metrics['ndcg']:.4f}")
    print(f"AVG_LATENCY : {metrics['avg_latency']:.4f}s")
    print("="*50)

    save_result_to_csv(filename, semantic_weight, keyword_weight, top_k, metrics)

if __name__ == "__main__":
    default_filename = "baseline_v1.json"
    
    filename = input(f"Enter filename (default: {default_filename}): ").strip()
    if not filename:
        filename = default_filename

    semantic_input = input("Enter semantic weight (default: 0.8): ").strip()
    semantic_weight = float(semantic_input) if semantic_input else 0.8

    keyword_input = input("Enter keyword weight (default: 0.2): ").strip()
    keyword_weight = float(keyword_input) if keyword_input else 0.2

    top_k_input = input("Enter top_k (default: 5): ").strip()
    top_k = int(top_k_input) if top_k_input else 5

    full_path = os.path.join(DATA_DIR, filename)
    
    evaluate_retrieval(full_path, semantic_weight, keyword_weight, top_k)