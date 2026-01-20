import asyncio
import logging
import httpx
import re
from typing import Any, Dict, List

from app.core.config import settings
from app.rag.models.pr_base import PRFileContext

logger = logging.getLogger(__name__)


class GithubService:
    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self.base_url = settings.GITHUB_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v3+json",
        }

    async def get_pr_context(
            self, owner: str, repo: str, pr_number: int
    ) -> List[PRFileContext]:

        async with httpx.AsyncClient(headers=self.headers, timeout=20.0) as client:
            try:
                base_path = f"{self.base_url}/{owner}/{repo}/pulls/{pr_number}"
                files_url = f"{base_path}/files"
                comments_url = f"{base_path}/comments"

                logger.info(f"Fetching file context for PR {owner}/{repo}#{pr_number}")

                # Diff와 Review를 병렬 조회
                responses = await asyncio.gather(
                    client.get(files_url, params={"per_page": 100}),
                    client.get(comments_url, params={"per_page": 100}),
                )

                for resp in responses:
                    resp.raise_for_status()

                files_data = responses[0].json()
                comments_data = responses[1].json()

                return self._merge_files_and_comments(files_data, comments_data)

            except httpx.HTTPStatusError as e:
                logger.error(f"GitHub API Error: {e.response.status_code} - {e.response.text}")
                return []
            except Exception as e:
                logger.error(f"Failed to fetch PR file context: {e}")
                return []

    def _merge_files_and_comments(
            self,
            files_data: List[Dict[str, Any]],
            comments_data: List[Dict[str, Any]]
    ) -> List[PRFileContext]:
        merged_files: Dict[str, dict] = {}

        for file in files_data:
            filename = file["filename"]
            status = file["status"]
            patch_content = file.get("patch", "")
            prev_filename = file.get("previous_filename")

            additions = file["additions"]
            deletions = file["deletions"]

            # RENAMED이고 additions, deletions이 0인 경우 파일 이름만 변경 -> File Diff 저장 안함
            if status == "renamed":
                if additions == 0 and deletions == 0:
                    patch_content = None

            merged_files[filename] = {
                "path": filename,
                "status": status,
                "additions": additions,
                "deletions": deletions,
                "previous_filename": prev_filename,
                "patch": patch_content,
                "comments": []
            }

        for comment in comments_data:
            path = comment["path"]

            if path in merged_files:
                comment_obj = {
                    "id": comment["id"],
                    "author": comment["user"]["login"] if comment["user"] else "unknown",
                    "body": comment["body"],
                    "created_at": comment["created_at"],
                    "diff_hunk": comment.get("diff_hunk", ""),
                    "line": comment.get("line"),
                    "original_line": comment.get("original_line")
                }
                merged_files[path]["comments"].append(comment_obj)

        result = []
        for file_data in merged_files.values():
            result.append(PRFileContext(**file_data))

        return result