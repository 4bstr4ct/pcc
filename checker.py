import asyncio
import time
import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, cast

import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType


class Protocol(Enum):
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    SOCKS4 = "SOCKS4"
    SOCKS5 = "SOCKS5"


@dataclass
class Proxy:
    ip: str
    port: int
    login: str | None = None
    password: str | None = None
    country: str = ""
    country_code: str = ""
    ping_ms: int = -1
    speed_kbs: float = -1
    valid: bool = False
    protocol: Protocol = Protocol.SOCKS5

    @property
    def has_auth(self) -> bool:
        return bool(self.login and self.password)

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    def tg_link(self) -> str:
        if self.protocol in (Protocol.SOCKS5, Protocol.SOCKS4):
            base = f"https://t.me/socks?server={self.ip}&port={self.port}"
        else:
            base = f"https://t.me/proxy?server={self.ip}&port={self.port}&secret="

        if self.has_auth:
            base += f"&user={self.login}&pass={self.password}"
        return base

    def export_line(self) -> str:
        if self.has_auth:
            return f"{self.ip}:{self.port}:{self.login}:{self.password}"
        return f"{self.ip}:{self.port}"


FLAG_OFFSET: int = 0x1F1E6 - ord("A")


def country_flag(code: str) -> str:
    if not code or len(code) != 2:
        return ""
    try:
        return chr(ord(code[0].upper()) + FLAG_OFFSET) + chr(
            ord(code[1].upper()) + FLAG_OFFSET
        )
    except (ValueError, IndexError):
        return ""


def parse_proxies(text: str) -> list[Proxy]:
    proxies: list[Proxy] = []
    seen: set[tuple[str, int, str | None, str | None]] = set()

    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^(https?|socks[45])://", "", line, flags=re.IGNORECASE)
        parts = line.split(":")
        if len(parts) < 2:
            continue

        ip = parts[0].strip()
        try:
            port = int(parts[1].strip())
        except ValueError:
            continue

        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
            continue
        if not (1 <= port <= 65535):
            continue

        login = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
        password = parts[3].strip() if len(parts) > 3 and parts[3].strip() else None

        key = (ip, port, login, password)
        if key in seen:
            continue
        seen.add(key)
        proxies.append(Proxy(ip=ip, port=port, login=login, password=password))
    return proxies


def github_to_raw(url: str) -> str:
    m: re.Match[str] | None = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/(?:blob|raw)/(.+)",
        url,
    )
    if m:
        return (
            f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"
        )
    return url


def parse_github_url(url: str) -> dict[str, str | None] | None:
    m: re.Match[str] | None = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/(?:blob|raw)/([^/]+)/(.+)",
        url,
    )
    if m:
        owner, repo, branch, path = m.groups()
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        return {
            "owner": owner,
            "repo": repo,
            "type": "file",
            "branch": branch,
            "path": path,
            "raw_url": raw_url,
        }

    m = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/tree/([^/]+)(?:/(.*))?",
        url,
    )
    if m:
        owner, repo, branch = m.group(1), m.group(2), m.group(3)
        path = m.group(4) or ""
        return {
            "owner": owner,
            "repo": repo,
            "type": "dir",
            "branch": branch,
            "path": path,
        }

    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?$", url)
    if m:
        return {
            "owner": m.group(1),
            "repo": m.group(2),
            "type": "repo",
            "branch": None,
            "path": "",
        }

    return None


_PROXY_FILE_KW = re.compile(
    r"proxy|proxies|socks[45]?|https?|data|list|alive|checked|working|free",
    re.IGNORECASE,
)
_PROXY_FILE_EXT: set[str] = {".txt"}


async def search_github_proxy_files(
    owner: str,
    repo: str,
    branch: str | None = None,
    subpath: str = "",
) -> list[tuple[str, str]]:
    async with aiohttp.ClientSession() as session:
        if not branch:
            async with session.get(
                url=f"https://api.github.com/repos/{owner}/{repo}",
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Accept": "application/vnd.github.v3+json"},
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"Failed to get repo info (HTTP {resp.status})")

                info = cast(dict[str, object], await resp.json())
                branch = str(info.get("default_branch") or "main")

        async with session.get(
            url=f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"Accept": "application/vnd.github.v3+json"},
        ) as resp:
            if resp.status != 200:
                raise ValueError(f"Failed to get file tree (HTTP {resp.status})")

            data = cast(dict[str, object], await resp.json())

    results: list[tuple[str, str]] = []
    tree = cast(list[dict[str, object]], data.get("tree") or [])

    for item in tree:
        if item.get("type") != "blob":
            continue

        path = str(item.get("path") or "")

        if subpath and not path.startswith(subpath):
            continue

        name = path.rsplit("/", 1)[-1] if "/" in path else path
        ext = ("." + name.rsplit(".", 1)[-1]).lower() if "." in name else ""
        if ext not in _PROXY_FILE_EXT:
            continue

        if not _PROXY_FILE_KW.search(path):
            continue

        raw_url: str = (
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        )
        results.append((path, raw_url))

    return results


CHECK_URL: str = "https://www.google.com/generate_204"
SPEED_TEST_URL: str = "https://speed.cloudflare.com/__down?bytes=1000000"
DEFAULT_TIMEOUT: float = 5.0


async def check_single_proxy(proxy: Proxy, protocol: Protocol, timeout: float) -> Proxy:
    proxy.protocol = protocol
    proxy_type_map: dict[Protocol, ProxyType] = {
        Protocol.HTTP: ProxyType.HTTP,
        Protocol.HTTPS: ProxyType.HTTP,
        Protocol.SOCKS4: ProxyType.SOCKS4,
        Protocol.SOCKS5: ProxyType.SOCKS5,
    }
    ptype = proxy_type_map[protocol]
    rdns: bool = protocol in (Protocol.SOCKS5, Protocol.SOCKS4)

    try:
        connector = ProxyConnector(
            proxy_type=ptype,
            host=proxy.ip,
            port=proxy.port,
            username=proxy.login,
            password=proxy.password,
            rdns=rdns,
        )
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        start: float = time.monotonic()

        async with aiohttp.ClientSession(
            connector=connector, timeout=client_timeout
        ) as session:
            async with session.get(CHECK_URL, allow_redirects=False) as resp:
                elapsed: float = time.monotonic() - start
                if resp.status in (200, 204):
                    proxy.valid = True
                    proxy.ping_ms = int(elapsed * 1000)
    except Exception:
        proxy.valid = False
        proxy.ping_ms = -1
    return proxy


async def check_all_protocols(proxy: Proxy, timeout: float) -> Proxy:
    candidates: list[asyncio.Task[Proxy]] = []
    for proto in (Protocol.SOCKS5, Protocol.SOCKS4, Protocol.HTTP, Protocol.HTTPS):
        p = Proxy(
            ip=proxy.ip, port=proxy.port, login=proxy.login, password=proxy.password
        )
        candidates.append(asyncio.create_task(check_single_proxy(p, proto, timeout)))

    results = await asyncio.gather(*candidates, return_exceptions=True)

    best: Proxy | None = None
    for r in results:
        if isinstance(r, Proxy) and r.valid:
            if best is None or r.ping_ms < best.ping_ms:
                best = r

    if best:
        proxy.valid = True
        proxy.ping_ms = best.ping_ms
        proxy.protocol = best.protocol
    else:
        proxy.valid = False
        proxy.ping_ms = -1
    return proxy


async def lookup_geoip(ip: str, session: aiohttp.ClientSession) -> tuple[str, str]:
    try:
        async with session.get(
            url=f"http://ip-api.com/json/{ip}?fields=status,country,countryCode",
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status == 200:
                data = cast(dict[str, object], await resp.json())

                if data.get("status") == "success":
                    country = str(data.get("country") or "")
                    code = str(data.get("countryCode") or "")
                    return country, code
    except Exception:
        pass
    return "", ""


async def speed_test_proxy(
    proxy: Proxy, protocol: Protocol, timeout: float = 15.0
) -> float:
    proxy_type_map: dict[Protocol, ProxyType] = {
        Protocol.HTTP: ProxyType.HTTP,
        Protocol.HTTPS: ProxyType.HTTP,
        Protocol.SOCKS4: ProxyType.SOCKS4,
        Protocol.SOCKS5: ProxyType.SOCKS5,
    }
    try:
        connector = ProxyConnector(
            proxy_type=proxy_type_map[protocol],
            host=proxy.ip,
            port=proxy.port,
            username=proxy.login,
            password=proxy.password,
            rdns=protocol in (Protocol.SOCKS5, Protocol.SOCKS4),
        )
        start: float = time.monotonic()
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as session:
            async with session.get(SPEED_TEST_URL) as resp:
                content: bytes = await resp.read()
                elapsed: float = time.monotonic() - start
                if elapsed > 0 and len(content) > 0:
                    return round((len(content) / 1024) / elapsed, 1)
    except Exception:
        pass
    return -1.0


class CheckerEngine:
    proxies: list[Proxy]
    protocol: Protocol | None
    concurrency: int
    timeout: float
    _cancelled: bool
    on_progress: Callable[[int, int], None] | None
    on_result: Callable[[Proxy], None] | None
    on_finished: Callable[[list[Proxy]], None] | None

    def __init__(
        self,
        proxies: list[Proxy],
        protocol: Protocol | None,
        concurrency: int = 100,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.proxies = proxies
        self.protocol = protocol
        self.concurrency = concurrency
        self.timeout = timeout
        self._cancelled = False
        self.on_progress = None
        self.on_result = None
        self.on_finished = None

    def cancel(self) -> None:
        self._cancelled = True

    async def run(self) -> list[Proxy]:
        semaphore = asyncio.Semaphore(self.concurrency)
        valid: list[Proxy] = []
        checked: int = 0
        total: int = len(self.proxies)
        lock = asyncio.Lock()

        async def worker(proxy: Proxy) -> None:
            nonlocal checked
            if self._cancelled:
                return

            async with semaphore:
                if self._cancelled:
                    return

                if self.protocol is None:
                    result = await check_all_protocols(proxy, self.timeout)
                else:
                    result = await check_single_proxy(
                        proxy, self.protocol, self.timeout
                    )

                async with lock:
                    checked += 1
                    if result.valid:
                        valid.append(result)

                if result.valid and self.on_result:
                    self.on_result(result)
                if self.on_progress:
                    self.on_progress(checked, total)

        tasks = [asyncio.create_task(worker(p)) for p in self.proxies]
        _ = await asyncio.gather(*tasks, return_exceptions=True)

        if valid and not self._cancelled:
            geo_sem = asyncio.Semaphore(10)
            async with aiohttp.ClientSession() as session:

                async def geo_worker(proxy: Proxy) -> None:
                    if self._cancelled:
                        return
                    async with geo_sem:
                        country, code = await lookup_geoip(proxy.ip, session)
                        proxy.country = country
                        proxy.country_code = code

                geo_tasks = [asyncio.create_task(geo_worker(p)) for p in valid]
                _ = await asyncio.gather(*geo_tasks, return_exceptions=True)

        valid.sort(key=lambda p: p.ping_ms)

        if self.on_finished:
            self.on_finished(valid)

        return valid
