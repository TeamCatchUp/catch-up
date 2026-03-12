import httpx

# 전역 AsyncClient
_shared_client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
)


def get_global_async_client() -> httpx.AsyncClient:
    return _shared_client
