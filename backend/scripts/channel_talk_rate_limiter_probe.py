from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catchup.connectors.channel_talk.core.http_client import ChannelTalkCoreHttpClient
from catchup.connectors.channel_talk.core.rate_limiter import (
    ChannelTalkCoreRateLimiterRegistry,
)
from catchup.connectors.channel_talk.document_space.http_client import (
    ChannelTalkDocumentsHttpClient,
)
from catchup.connectors.channel_talk.document_space.rate_limiter import (
    ChannelTalkDocumentSpaceRateLimiterRegistry,
)


@dataclass(frozen=True)
class ProbeResult:
    request_index: int
    elapsed_ms: float
    interval_ms: float | None
    status_code: int


class _ProbeServer:
    def __init__(self) -> None:
        self.arrival_times: list[float] = []
        self._lock = threading.Lock()

        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                with server_ref._lock:
                    server_ref.arrival_times.append(perf_counter())

                body = json.dumps(_response_payload(self.path)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="channel-talk-rate-limiter-probe",
            daemon=True,
        )

    def __enter__(self) -> "_ProbeServer":
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def _response_payload(path: str) -> dict[str, object]:
    if path.startswith("/open/v5/user-chats"):
        return {"userChats": []}
    if path.startswith("/open/v1/spaces/$me/articles"):
        return {"articles": []}
    return {"ok": True}


async def _run_core_probe(
    *,
    base_url: str,
    request_count: int,
    rps: float,
) -> list[int]:
    registry = ChannelTalkCoreRateLimiterRegistry(requests_per_second=rps)
    transport = ChannelTalkCoreHttpClient(
        base_url=base_url,
        rate_limiter_getter=registry.get_for_request,
        max_rate_limit_retries=0,
    )
    status_codes: list[int] = []
    for _ in range(request_count):
        response = await transport.send(
            method="GET",
            path="/open/v5/user-chats",
            headers={
                "Accept": "application/json",
                "x-access-key": "probe-access-key",
                "x-access-secret": "probe-access-secret",
            },
            params={"state": "opened", "limit": 1},
            channel_id="probe-channel",
        )
        status_codes.append(response.status_code)
    return status_codes


async def _run_documents_probe(
    *,
    base_url: str,
    request_count: int,
    rps: float,
) -> list[int]:
    registry = ChannelTalkDocumentSpaceRateLimiterRegistry(requests_per_second=rps)
    transport = ChannelTalkDocumentsHttpClient(
        access_key="probe-access-key",
        access_secret="probe-access-secret",
        space_id="probe-space",
        base_url=base_url,
        rate_limiter_getter=registry.get,
        max_rate_limit_retries=0,
    )
    status_codes: list[int] = []
    for _ in range(request_count):
        response = await transport.send(
            method="GET",
            path="/open/v1/spaces/$me/articles",
            params={"language": "ko", "state": "published", "limit": 1},
        )
        status_codes.append(response.status_code)
    return status_codes


def _build_results(
    *,
    start_time: float,
    arrival_times: list[float],
    status_codes: list[int],
) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    previous: float | None = None
    for index, (arrival_time, status_code) in enumerate(
        zip(arrival_times, status_codes, strict=True),
        start=1,
    ):
        results.append(
            ProbeResult(
                request_index=index,
                elapsed_ms=(arrival_time - start_time) * 1000,
                interval_ms=None
                if previous is None
                else (arrival_time - previous) * 1000,
                status_code=status_code,
            )
        )
        previous = arrival_time
    return results


def _print_results(*, target: str, rps: float, results: list[ProbeResult]) -> None:
    intervals = [
        result.interval_ms for result in results if result.interval_ms is not None
    ]
    print(f"target={target} requested_rps={rps} requests={len(results)}")
    if intervals:
        print(
            "interval_ms "
            f"min={min(intervals):.2f} "
            f"avg={statistics.fmean(intervals):.2f} "
            f"p50={statistics.median(intervals):.2f} "
            f"max={max(intervals):.2f}"
        )
    print("idx,status,elapsed_ms,interval_ms")
    for result in results:
        interval = "" if result.interval_ms is None else f"{result.interval_ms:.2f}"
        print(
            f"{result.request_index},"
            f"{result.status_code},"
            f"{result.elapsed_ms:.2f},"
            f"{interval}"
        )


def _write_csv(*, csv_path: Path, results: list[ProbeResult]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["idx", "status", "elapsed_ms", "interval_ms"])
        for result in results:
            writer.writerow(
                [
                    result.request_index,
                    result.status_code,
                    f"{result.elapsed_ms:.2f}",
                    ""
                    if result.interval_ms is None
                    else f"{result.interval_ms:.2f}",
                ]
            )


async def _amain() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Send real local TCP requests through Channel Talk HTTP clients and "
            "print per-request arrival intervals."
        )
    )
    parser.add_argument("--target", choices=("core", "documents"), default="core")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--rps", type=float, default=20.0)
    parser.add_argument("--csv-path", type=Path)
    args = parser.parse_args()

    if args.requests < 1:
        raise SystemExit("--requests must be positive")
    if args.rps <= 0:
        raise SystemExit("--rps must be positive")

    with _ProbeServer() as server:
        start_time = perf_counter()
        if args.target == "core":
            status_codes = await _run_core_probe(
                base_url=server.url,
                request_count=args.requests,
                rps=args.rps,
            )
        else:
            status_codes = await _run_documents_probe(
                base_url=server.url,
                request_count=args.requests,
                rps=args.rps,
            )

        results = _build_results(
            start_time=start_time,
            arrival_times=server.arrival_times,
            status_codes=status_codes,
        )
    _print_results(target=args.target, rps=args.rps, results=results)
    if args.csv_path is not None:
        _write_csv(csv_path=args.csv_path, results=results)


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
