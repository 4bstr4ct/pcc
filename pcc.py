import asyncio
import pathlib
import typer
import aiohttp
from typing import Annotated
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)

from checker import (
    CheckerEngine,
    Protocol,
    parse_proxies,
    parse_github_url,
    search_github_proxy_files,
    github_to_raw,
    country_flag,
)

PRESETS = {
    "speedx-s5": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    "speedx-http": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "proxifly-s5": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
    "proxifly-all": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
    "monosans-s5": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
}

app = typer.Typer(
    add_completion=False, context_settings={"help_option_names": ["-h", "--help"]}
)
console = Console()


async def fetch_text_data(source: str) -> str:
    if pathlib.Path(source).is_file():
        return pathlib.Path(source).read_text(encoding="utf-8", errors="ignore")

    if source.startswith("http"):
        gh_info = parse_github_url(source)
        if gh_info and gh_info["type"] in ("repo", "dir"):
            owner = str(gh_info.get("owner") or "")
            repo = str(gh_info.get("repo") or "")
            branch = str(gh_info.get("branch") or "")
            subpath = str(gh_info.get("path") or "")

            console.print(
                f"[yellow]Scanning GitHub repository: {owner}/{repo}[/yellow]"
            )

            files = await search_github_proxy_files(
                owner=owner,
                repo=repo,
                branch=branch if branch else None,
                subpath=subpath,
            )

            text_data = ""
            async with aiohttp.ClientSession() as session:
                for _, raw_url in files:
                    async with session.get(raw_url) as resp:
                        if resp.status == 200:
                            text_data += await resp.text() + "\n"
            return text_data

        direct_url = github_to_raw(source)
        async with aiohttp.ClientSession() as session:
            async with session.get(direct_url) as resp:
                if resp.status == 200:
                    return await resp.text()
    return ""


async def async_main(
    source: str, preset: str, proxy_type: str, export: str, threads: int, timeout: int
):
    if preset:
        if preset not in PRESETS:
            console.print(
                f"[bold red]Unknown preset.[/bold red] Available: {', '.join(PRESETS.keys())}"
            )
            raise typer.Exit()
        source = PRESETS[preset]
    elif not source:
        console.print("[bold red]You must specify --source or --preset[/bold red]")
        raise typer.Exit()

    type_map = {
        "socks5": Protocol.SOCKS5,
        "socks4": Protocol.SOCKS4,
        "http": Protocol.HTTP,
        "https": Protocol.HTTPS,
        "all": None,
    }
    proto = type_map.get(proxy_type.lower())

    console.print(f"\n[bold blue]Fetching proxies from:[/bold blue] {source}")
    text_data = await fetch_text_data(source)
    proxies = parse_proxies(text_data)

    if not proxies:
        console.print("[bold red]No proxies found.[/bold red]")
        raise typer.Exit()

    console.print(
        f"[bold green]Proxies found for checking:[/bold green] {len(proxies)}\n"
    )

    engine = CheckerEngine(
        proxies=proxies, protocol=proto, concurrency=threads, timeout=timeout
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Checking proxies...", total=len(proxies))
        engine.on_progress = lambda checked, _: progress.update(task, completed=checked)
        valid_proxies = await engine.run()

    if valid_proxies:
        table = Table(title="Working Proxies", header_style="bold magenta")
        table.add_column("Flag", justify="center")
        table.add_column("Country", style="dim")
        table.add_column("IP:Port", style="cyan")
        table.add_column("Type", justify="center", style="green")
        table.add_column("Ping", justify="right")
        table.add_column("TG Link", style="blue")

        for p in valid_proxies:
            flag = country_flag(p.country_code)
            tg_link = (
                p.tg_link()
                if p.protocol in (Protocol.SOCKS5, Protocol.SOCKS4)
                else "N/A"
            )

            if p.ping_ms < 400:
                ping_str = f"[green]{p.ping_ms} ms[/green]"
            elif p.ping_ms < 1000:
                ping_str = f"[yellow]{p.ping_ms} ms[/yellow]"
            else:
                ping_str = f"[red]{p.ping_ms} ms[/red]"

            table.add_row(
                flag,
                p.country or "Unknown",
                p.address,
                p.protocol.value,
                ping_str,
                tg_link,
            )

        console.print(table)

        if export:
            with open(file=export, mode="w", encoding="utf-8") as f:
                for p in valid_proxies:
                    _ = f.write(p.export_line() + "\n")
            console.print(
                f"\n[bold green]Saved {len(valid_proxies)} proxies to:[/bold green] {export}"
            )
    else:
        console.print("[bold red]No proxies passed the check.[/bold red]")


@app.command()
def main(
    source: Annotated[
        str | None,
        typer.Option("--source", "-s", help="Path to local .txt file or URL"),
    ] = None,
    preset: Annotated[
        str | None,
        typer.Option("--preset", "-p", help="Use built-in preset (e.g. speedx-s5)"),
    ] = None,
    proxy_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Type (socks5, socks4, http, https, all)"),
    ] = "socks5",
    export: Annotated[
        str, typer.Option("--export", "-e", help="File to save working proxies")
    ] = "good_proxies.txt",
    threads: Annotated[
        int, typer.Option("--threads", "-c", help="Concurrency limit")
    ] = 100,
    timeout: Annotated[
        int, typer.Option("--timeout", "-to", help="Timeout in seconds")
    ] = 5,
    list_presets: Annotated[
        bool, typer.Option("--list", help="Show all available presets")
    ] = False,
) -> None:
    console.print(
        Panel.fit("[bold cyan]pcc[/bold cyan] - Proxy Checker CLI", style="magenta")
    )

    if list_presets:
        table = Table(title="Available Presets")
        table.add_column("Name", style="cyan")
        table.add_column("URL", style="dim")
        for name, url in PRESETS.items():
            table.add_row(name, url)
        console.print(table)
        return

    if not source and not preset:
        console.print("[bold red]Error:[/bold red] No source or preset specified.")
        console.print(
            "Use [bold cyan]--help[/bold cyan] or [bold cyan]-h[/bold cyan] to see available commands and options."
        )
        raise typer.Exit(code=1)

    asyncio.run(
        async_main(source or "", preset or "", proxy_type, export, threads, timeout)
    )


if __name__ == "__main__":
    app()
