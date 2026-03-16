# pcc — ProXy Checker CLI 🚀

A lightning-fast, asynchronous, and strictly typed proxy checker for Linux. Optimized for Telegram and high-concurrency tasks.

> **Credits:** This project is a complete CLI refactor and modernization of the original logic by [Magerko](https://github.com/Magerko/High-Load-Proxy-Checker).

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-linux-lightgrey?style=for-the-badge&logo=linux)

## ✨ Features

- **Async Engine**: Built with `aiohttp` and `asyncio` for maximum speed and performance.
- **Strictly Typed**: Developed with zero `Any` usage, fully compliant with `Pyright` (strict mode) and `Ruff`.
- **GitHub Integration**: Automatically find and parse proxy lists from GitHub repositories or raw text URLs.
- **Smart Presets**: Instant access to popular proxy providers (SpeedX, Monosans, Proxifly) with the `--preset` flag.
- **Visual Feedback**: Professional terminal output using `Rich` with:
  - 🌍 Country flags and names.
  - ⚡ Color-coded ping (Green: <400ms, Yellow: <1000ms, Red: Slow).
  - 📱 Clickable Telegram deep-links (`tg://socks...`).
- **Clean CLI**: No interactive noise by default, supports `-h` / `--help` and standard UNIX-way arguments.

## 📦 Installation

### Prerequisites

- Python 3.10 or higher.
- A virtual environment (recommended).

### Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/4bstr4ct/pcc.git
   cd pcc
   ```

2. **Install dependencies:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **(Optional) Add to PATH:**
   Create a symlink or a wrapper in `~/.local/bin/pcc` to run it from anywhere.

## 🚀 Usage

### Quick Start with Presets

Check the best SOCKS5 proxies from built-in lists:

```bash
pcc --preset speedx-s5
```

### Check Custom Sources

Provide a URL (raw text or GitHub repo) or a local `.txt` file:

```bash
pcc --source https://github.com/hookzof/socks5_list
```

### Advanced Configuration

Increase concurrency and set a shorter timeout:

```bash
pcc -p speedx-s5 --threads 300 --timeout 3
```

### Command Line Options

| Option      | Shorthand | Description                                                 | Default            |
| :---------- | :-------- | :---------------------------------------------------------- | :----------------- |
| `--source`  | `-s`      | URL or local `.txt` file path                               | None               |
| `--preset`  | `-p`      | Use a built-in preset (see `--list`)                        | None               |
| `--type`    | `-t`      | Proxy protocol (`socks5`, `socks4`, `http`, `https`, `all`) | `socks5`           |
| `--export`  | `-e`      | Filename to save working proxies                            | `good_proxies.txt` |
| `--threads` | `-c`      | Number of concurrent workers                                | `100`              |
| `--timeout` | `-to`     | Connection timeout in seconds                               | `5`                |
| `--list`    |           | Show all available built-in presets                         |                    |
| `--help`    | `-h`      | Show help message and exit                                  |                    |

## 🛠 Tech Stack

- [Typer](https://typer.tiangolo.com/) - Modern CLI interface.
- [Rich](https://github.com/Textualize/rich) - Terminal formatting and tables.
- [aiohttp](https://docs.aiohttp.org/) - Async HTTP client.
- [aiohttp-socks](https://github.com/n0ppo/aiohttp-socks) - SOCKS proxy connector.

## ⚖️ License

Distributed under the MIT License. See `LICENSE` for more information.

---

Created by [4bstr4ct](https://github.com/4bstr4ct)
