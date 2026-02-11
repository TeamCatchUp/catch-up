import argparse
import logging
import os

from langfuse import Langfuse
from catchup.configs.config import settings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Langfuse 프롬프트 이름 : 로컬 파일 경로 매핑
PROMPT_MAPPING = {
    # Main Nodes
    "rag/chitchat": "catchup/rag/prompts/chitchat.j2",
    "rag/rewrite": "catchup/rag/prompts/rewrite.j2",
    "rag/route": "catchup/rag/prompts/route.j2",
    "rag/search_optimizer": "catchup/rag/prompts/generate_vector_queries.j2",
    "rag/grade": "catchup/rag/prompts/grade.j2",
    "rag/generate_final_answer": "catchup/rag/prompts/generate_final_answer.j2",
    
    # Common Modules (templates/ 제거됨)
    "common/global_context": "catchup/rag/prompts/common/global_context.j2",
    "common/citation_guide": "catchup/rag/prompts/common/citation_guide.j2",
}

def get_langfuse_client():
    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_BASE_URL,
    )

def pull_prompts():
    """Langfuse(Cloud) -> Local(File) 동기화"""
    client = get_langfuse_client()
    logger.info("Starting PULL: Langfuse -> Local")
    
    success_count = 0
    
    for lf_name, local_path in PROMPT_MAPPING.items():
        try:
            # 최신 버전의 프롬프트 가져오기
            prompt_obj = client.get_prompt(lf_name)
            raw_content = prompt_obj.prompt
            
            abs_path = os.path.join(os.getcwd(), local_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(raw_content)
                
            logger.info(f"Pulled: {lf_name} -> {local_path}")
            success_count += 1
            
        except Exception as e:
            logger.error(f"Failed to pull {lf_name}: {e}")

    logger.info(f"Pull Complete. ({success_count}/{len(PROMPT_MAPPING)})")


def push_prompts(commit_message: str):
    """Local(File) -> Langfuse(Cloud) 동기화 (변경사항 있는 경우만)"""
    client = get_langfuse_client()
    logger.info(f"Starting PUSH: Local -> Langfuse (Message: {commit_message})")
    
    success_count = 0
    skipped_count = 0
    
    for lf_name, local_path in PROMPT_MAPPING.items():
        abs_path = os.path.join(os.getcwd(), local_path)
        
        if not os.path.exists(abs_path):
            logger.warning(f"File not found: {local_path}. Skipping.")
            continue
            
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                local_content = f.read()

            # Diff Check
            current_config = {"model": "gpt-4o-mini", "temperature": 0}
            current_type = "text"
            current_tags = []
            is_new_prompt = False

            try:
                # 1. Langfuse에서 최신 버전 가져오기
                existing_prompt = client.get_prompt(lf_name)
                
                # 2. 내용 비교
                remote_content = existing_prompt.prompt
                
                if local_content.strip() == remote_content.strip():
                    logger.info(f"Skipped: {lf_name} (No changes detected)")
                    skipped_count += 1
                    continue

                # 3. 기존 설정 보존
                if existing_prompt.config:
                    current_config = existing_prompt.config
                current_type = existing_prompt.type
                current_tags = existing_prompt.tags if existing_prompt.tags else []

            except Exception:
                # 신규 생성
                logger.info(f"New prompt detected: {lf_name}")
                is_new_prompt = True

            # Upload
            new_tags = [t for t in current_tags if not t.startswith("msg:")]
            new_tags.append(f"msg:{commit_message}")

            client.create_prompt(
                name=lf_name,
                prompt=local_content,
                type=current_type,
                config=current_config,
                labels=["latest"],
                tags=new_tags
            )
            
            action = "Created" if is_new_prompt else "Updated"
            logger.info(f"{action}: {local_path} -> {lf_name}")
            success_count += 1
            
        except Exception as e:
            logger.error(f"Failed to push {lf_name}: {e}")

    logger.info(f"Push Complete. (Updated: {success_count}, Skipped: {skipped_count})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Langfuse Prompt Sync Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Pull Command
    subparsers.add_parser("pull", help="Download prompts from Langfuse")

    # Push Command
    push_parser = subparsers.add_parser("push", help="Upload local prompts to Langfuse")
    push_parser.add_argument("-m", "--message", type=str, required=True, help="Commit message")

    args = parser.parse_args()

    if args.command == "pull":
        pull_prompts()
    elif args.command == "push":
        push_prompts(args.message)
