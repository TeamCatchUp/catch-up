#!/usr/bin/env python3
"""
릴리즈 자동화 스크립트

Phase 1: 브랜치 생성, 버전 업데이트, PR 생성
Phase 2: 머지 후 태그 생성, upstream/develop PR 생성

Usage:
    python release.py          # Phase 1
    python release.py --phase2 # Phase 2 (머지 완료 후)
"""

import subprocess
import sys
import re
import argparse
from pathlib import Path


UPSTREAM_REMOTE = "upstream"
ORIGIN_REMOTE = "origin"
MAIN_BRANCH = "main"
DEVELOP_BRANCH = "develop"
PYPROJECT_PATH = Path("../pyproject.toml")


def run(cmd: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if not capture:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    if check and result.returncode != 0:
        print(f"\n[Error] 명령 실패: {cmd}")
        if result.stderr.strip():
            print(f"  {result.stderr.strip()}")
        sys.exit(1)
    return result


def get_remote_repo(remote: str) -> str:
    url = run(f"git remote get-url {remote}", capture=True).stdout.strip()
    match = re.search(r'[:/]([^/]+/[^/]+?)(?:\.git)?$', url)
    if not match:
        print(f"[Error] {remote} remote URL을 파싱할 수 없습니다: {url}")
        sys.exit(1)
    return match.group(1)


def get_remote_owner(remote: str) -> str:
    return get_remote_repo(remote).split("/")[0]


def get_current_version() -> tuple[int, int, int]:
    if not PYPROJECT_PATH.exists():
        print(f"[Error] {PYPROJECT_PATH} 파일을 찾을 수 없습니다.")
        sys.exit(1)
    content = PYPROJECT_PATH.read_text()
    match = re.search(r'^version\s*=\s*["\'](\d+)\.(\d+)\.(\d+)["\']', content, re.MULTILINE)
    if not match:
        print("[Error] pyproject.toml 에서 version 필드를 찾을 수 없습니다.")
        sys.exit(1)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(major: int, minor: int, patch: int, bump_type: str) -> tuple[int, int, int]:
    if bump_type == "major":
        return major + 1, 0, 0
    elif bump_type == "minor":
        return major, minor + 1, 0
    elif bump_type == "patch":
        return major, minor, patch + 1
    print(f"[Error] 알 수 없는 bump 타입: {bump_type}")
    sys.exit(1)


def update_version_in_pyproject(new_version: str):
    content = PYPROJECT_PATH.read_text()
    new_content = re.sub(
        r'^(version\s*=\s*["\'])\d+\.\d+\.\d+(["\'])',
        rf'\g<1>{new_version}\g<2>',
        content,
        flags=re.MULTILINE,
    )
    PYPROJECT_PATH.write_text(new_content)


def select_bump_type(major: int, minor: int, patch: int) -> str:
    current = f"{major}.{minor}.{patch}"
    print(f"\n  현재 버전: {current}\n")
    print(f"  [1] major  {major}.{minor}.{patch} -> {major+1}.0.0      breaking change")
    print(f"  [2] minor  {major}.{minor}.{patch} -> {major}.{minor+1}.0      새 기능 추가")
    print(f"  [3] patch  {major}.{minor}.{patch} -> {major}.{minor}.{patch+1}      버그픽스")
    choices = {"1": "major", "2": "minor", "3": "patch"}
    while True:
        raw = input("\n  선택 (1/2/3): ").strip()
        if raw in choices:
            return choices[raw]
        print("  1, 2, 3 중에서 입력하세요.")


def confirm(prompt: str) -> bool:
    while True:
        raw = input(f"{prompt} (y/n): ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False


def get_state_file() -> Path:
    return Path(".release_state")


def save_state(ticket: str, branch: str, version: str):
    get_state_file().write_text(f"{ticket}\n{branch}\n{version}\n")


def load_state() -> tuple[str, str, str]:
    sf = get_state_file()
    if not sf.exists():
        print("[Error] .release_state 파일이 없습니다. Phase 1을 먼저 실행하세요.")
        sys.exit(1)
    lines = sf.read_text().strip().splitlines()
    if len(lines) < 3:
        print("[Error] .release_state 파일이 손상됐습니다. Phase 1을 다시 실행하세요.")
        sys.exit(1)
    return lines[0], lines[1], lines[2]


def phase1():
    print("=" * 56)
    print("  Catch Up Release  /  Phase 1")
    print("=" * 56)

    print("\n[1/6] develop 최신화")
    run(f"git switch {DEVELOP_BRANCH}")
    run(f"git pull {ORIGIN_REMOTE} {DEVELOP_BRANCH}")

    print("\n[2/6] 지라 티켓번호")
    while True:
        ticket = input("  티켓번호 (예: CATDEV-123): ").strip().upper()
        if re.match(r'^[A-Z]+-\d+$', ticket):
            break
        print("[Error] 형식이 맞지 않습니다. 예) CATDEV-123")

    print("\n[3/6] 버전 업데이트")
    major, minor, patch = get_current_version()
    bump_type = select_bump_type(major, minor, patch)
    new_major, new_minor, new_patch = bump_version(major, minor, patch, bump_type)
    new_version = f"{new_major}.{new_minor}.{new_patch}"

    print(f"\n  {major}.{minor}.{patch} -> {new_version} ({bump_type})")
    if not confirm("  진행하시겠습니까?"):
        print("  중단합니다.")
        sys.exit(0)

    branch = f"release/common/{ticket}-{new_version}-release"
    print(f"\n[4/6] 브랜치 생성  {branch}")
    run(f"git switch -c {branch}")
    update_version_in_pyproject(new_version)
    run("uv lock")
    run(f"git add {PYPROJECT_PATH} uv.lock")
    run(f'git commit -m "release(common): {new_version} 버전 범프"')

    print(f"\n[5/6] {ORIGIN_REMOTE} 푸시")
    run(f"git push {ORIGIN_REMOTE} {branch}")

    print(f"\n[6/6] PR 생성  {ORIGIN_REMOTE}/{branch} -> {UPSTREAM_REMOTE}/{MAIN_BRANCH}")
    upstream_repo = get_remote_repo(UPSTREAM_REMOTE)
    origin_owner = get_remote_owner(ORIGIN_REMOTE)
    pr_title = f"Release {new_version} ({ticket})"
    pr_body = f"## Release {new_version}\n\n- Jira: {ticket}\n- Bump type: {bump_type}"
    run(
        f'gh pr create '
        f'--title "{pr_title}" '
        f'--body "{pr_body}" '
        f'--base {MAIN_BRANCH} '
        f'--head "{origin_owner}:{branch}" '
        f'--repo "{upstream_repo}"'
    )

    save_state(ticket, branch, new_version)

    print("\n" + "=" * 56)
    print("  Phase 1 완료.")
    print(f"  PR을 머지한 뒤 Phase 2를 실행하세요.\n")
    print("    python release.py --phase2")
    print("=" * 56)


def phase2():
    print("=" * 56)
    print("  Catch Up Release  /  Phase 2")
    print("=" * 56)

    ticket, branch, version = load_state()
    print(f"\n  티켓:   {ticket}")
    print(f"  브랜치: {branch}")
    print(f"  버전:   {version}")

    if not confirm("\n  PR 머지가 완료됐습니까?"):
        print("  중단합니다.")
        sys.exit(0)

    print(f"\n[1/3] {UPSTREAM_REMOTE}/{MAIN_BRANCH} 최신화")
    run(f"git fetch {UPSTREAM_REMOTE} {MAIN_BRANCH}")
    result = run(f"git switch {MAIN_BRANCH}", check=False)
    if result.returncode != 0:
        run(f"git switch -c {MAIN_BRANCH} --track {UPSTREAM_REMOTE}/{MAIN_BRANCH}")
    else:
        run(f"git pull {UPSTREAM_REMOTE} {MAIN_BRANCH}")

    print(f"\n[2/3] 태그 생성  {version}")
    run(f'git tag -a {version} -m "Release {version}"')
    run(f"git push {UPSTREAM_REMOTE} {version}")

    print(f"\n[3/3] PR 생성  {UPSTREAM_REMOTE}/{MAIN_BRANCH} -> {UPSTREAM_REMOTE}/{DEVELOP_BRANCH}")
    upstream_repo = get_remote_repo(UPSTREAM_REMOTE)
    pr_title = f"Merge release {version} back to develop"
    pr_body = f"Release {version} ({ticket})을 develop에 반영합니다."
    run(
        f'gh pr create '
        f'--title "{pr_title}" '
        f'--body "{pr_body}" '
        f'--base {DEVELOP_BRANCH} '
        f'--head {MAIN_BRANCH} '
        f'--repo "{upstream_repo}"'
    )

    get_state_file().unlink(missing_ok=True)

    print("\n" + "=" * 56)
    print(f"  Release {version} 완료.")
    print(f"  upstream/{DEVELOP_BRANCH} PR을 머지하면 릴리즈가 마무리됩니다.")
    print("=" * 56)


def main():
    parser = argparse.ArgumentParser(description="릴리즈 자동화 스크립트")
    parser.add_argument("--phase2", action="store_true", help="Phase 2 실행 (머지 완료 후)")
    args = parser.parse_args()

    if args.phase2:
        phase2()
    else:
        phase1()


if __name__ == "__main__":
    main()