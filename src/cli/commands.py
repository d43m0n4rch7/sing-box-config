"""
Command handlers for the sing-box CLI tools.

Contains the logic for configuration generation, formatting, binary packing,
rule-set compilation, and system monitoring.
"""

import argparse
import io
import json
import time
from pathlib import Path
from typing import Any, NoReturn

import httpx
import plotext as plt
import psutil
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter, WordCompleter
from rich import print as rprint
from rich.status import Status

from .models import ProfileContent, ProfileType
from .utils import (
    box,
    encode_profile_content,
    load_template,
    parse_vless_url,
    sanitize_filename,
    update_vless_outbound,
)

# Strict Project Directory Isolation
SRC_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SRC_DIR / "templates"
GENERATE_DIR = SRC_DIR / "generate"
PACK_DIR = SRC_DIR / "pack"
RULES_DIR = SRC_DIR / "rules"
SRS_DIR = RULES_DIR / "srs"


class SBCParser(argparse.ArgumentParser):
    """Custom parser to intercept argparse errors and format them natively in Catppuccin."""

    def error(self, message: str) -> NoReturn:
        """
        Overrides default argparse error handling to prevent generic CLI exits.

        Parameters
        ----------
        message : str
            The error message provided by argparse.
        """
        rprint(f"[bold #f38ba8]❌  Argument Error:[/] {message}")
        self.print_usage()
        import sys
        sys.exit(2)


def cmd_generate(args: list[str]) -> None:
    """
    Generates a sing-box configuration file from a VLESS URL and a chosen template.

    Parameters
    ----------
    args : list[str]
        Command line arguments passed to the generate action.
    """
    parser = SBCParser(prog="config generate", description="Generate a sing-box config from a VLESS URL")
    parser.add_argument("url", nargs="?", help="VLESS subscription link")
    parser.add_argument("-t", "--template", type=Path, help="Path to sing-box template (.json)")
    parser.add_argument("-o", "--output", type=Path, help="Output filename")

    parsed = parser.parse_args(args)
    url_input: str | None = parsed.url
    template_input: Path | None = parsed.template

    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    GENERATE_DIR.mkdir(parents=True, exist_ok=True)

    # Type Narrowing for strict pyright adherence
    final_url: str
    if url_input:
        final_url = url_input
    else:
        rprint("[bold #89b4fa]✨  Interactive Configuration Wizard[/]")
        prompted_url = prompt("  Enter VLESS URL: ").strip()
        if not prompted_url:
            rprint("[bold #f38ba8]❌  Generation cancelled: No URL provided.[/]")
            return
        final_url = prompted_url

    final_template: Path
    if template_input:
        final_template = template_input
    else:
        available_templates = [f.name for f in TEMPLATES_DIR.glob("*.json")]
        rprint("[dim #a6adc8]  Select sing-box JSON template (Tab for suggestions):[/]")

        completer = WordCompleter(available_templates) if available_templates else PathCompleter(expanduser=True)
        tmpl_str = prompt("  Template name or path: ", completer=completer).strip()

        chosen_path = Path(tmpl_str)
        if (TEMPLATES_DIR / chosen_path).exists():
            final_template = TEMPLATES_DIR / chosen_path
        elif (TEMPLATES_DIR / f"{tmpl_str}.json").exists():
            final_template = TEMPLATES_DIR / f"{tmpl_str}.json"
        else:
            final_template = chosen_path

    try:
        params = parse_vless_url(final_url)
        cfg = load_template(final_template)
        update_vless_outbound(cfg, params)

        out_path: Path
        if parsed.output:
            out_path = parsed.output
        else:
            safe_name = sanitize_filename(params.name)
            out_path = GENERATE_DIR / f"{safe_name}.json"

        out_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

        rprint(f"\n[bold #a6e3a1]Successfully parsed VLESS URL for server:[/] {params.name}")
        rprint(f"  [dim #a6adc8]Server:[/] {params.server}:{params.port}")
        rprint(f"  [dim #a6adc8]UUID:[/] {params.uuid}")
        rprint(f"  [dim #a6adc8]Security:[/] {params.security}")

        if getattr(params, "sni", None):
            rprint(f"  [dim #a6adc8]SNI:[/] {params.sni}")

        rprint(f"\n[bold #a6e3a1]✔  Configuration saved:[/] [bold #89b4fa]{out_path.name}[/]")
    except Exception as e:
        rprint(f"[bold #f38ba8]❌  Generation failed:[/] {e}")


def cmd_format(args: list[str]) -> None:
    """
    Formats JSON configurations in the generate directory using sing-box core.

    Parameters
    ----------
    args : list[str]
        Command line arguments passed to the format action.
    """
    parser = SBCParser(prog="config format", description="Format generated JSON configurations.")
    parser.add_argument("-d", "--dir", type=Path, default=GENERATE_DIR, help="Directory with JSON configs")
    parsed = parser.parse_args(args)

    target_dir: Path = parsed.dir
    if not target_dir.exists():
        rprint(f"[dim #a6adc8]Target directory {target_dir.name} does not exist. Skipping.[/]")
        return

    files = list(target_dir.glob("*.json"))
    if not files:
        rprint("[dim #a6adc8]No JSON files found to format.[/]")
        return

    for f in files:
        try:
            box.run(["format", "-w", "-c", str(f)])
            rprint(f"[bold #a6e3a1]Formatted:[/] {f.name}")
        except io.UnsupportedOperation:
            continue


def cmd_pack(args: list[str]) -> None:
    """
    Encodes a JSON configuration file into a binary .bpf profile.

    Parameters
    ----------
    args : list[str]
        Command line arguments passed to the pack action.
    """
    parser = SBCParser(prog="config pack", description="Pack a JSON configuration into a binary profile (.bpf)")
    parser.add_argument("config", nargs="?", help="Path to .json file or raw JSON string")
    parser.add_argument("-n", "--name", help="Profile display name")
    parser.add_argument("-t", "--type", default="local", choices=["local", "remote", "icloud"], help="Profile type")

    parsed = parser.parse_args(args)
    config_input: str | None = parsed.config
    profile_name: str | None = parsed.name
    profile_type_str: str = parsed.type

    GENERATE_DIR.mkdir(parents=True, exist_ok=True)
    PACK_DIR.mkdir(parents=True, exist_ok=True)

    final_config_input: str
    if config_input:
        final_config_input = config_input
    else:
        rprint("[bold #89b4fa]📦  Interactive Profile Packing Wizard[/]")
        available_configs = [f.name for f in GENERATE_DIR.glob("*.json")]
        rprint("[dim #a6adc8]  Select generated configuration (Tab for suggestions):[/]")

        completer = WordCompleter(available_configs) if available_configs else PathCompleter(expanduser=True)
        prompted_config = prompt("  Config name or path: ", completer=completer).strip()

        if not prompted_config:
            rprint("[bold #f38ba8]❌  Packing cancelled: No file specified.[/]")
            return
        final_config_input = prompted_config

    config_path = Path(final_config_input)
    if (GENERATE_DIR / config_path).exists():
        config_path = GENERATE_DIR / config_path
    elif (GENERATE_DIR / f"{final_config_input}.json").exists():
        config_path = GENERATE_DIR / f"{final_config_input}.json"

    if not profile_name:
        default_name = config_path.stem if config_path.exists() else "MyProfile"
        rprint(f"[dim #a6adc8]  Enter profile display name [default: {default_name}]:[/]")
        profile_name = prompt(f"  Profile name ({default_name}): ").strip() or default_name

    if not args:
        rprint("[dim #a6adc8]  Select profile type (local, remote, icloud) [default: local]:[/]")
        prompt_type = prompt("  Profile type (local): ").strip().lower()
        if prompt_type in ["local", "remote", "icloud"]:
            profile_type_str = prompt_type

    try:
        content = config_path.read_text(encoding="utf-8") if config_path.exists() else final_config_input
        p_type = ProfileType[profile_type_str.upper()]

        binary = encode_profile_content(ProfileContent(name=profile_name, type=p_type, config=content))

        out_path = PACK_DIR / f"{profile_name}.bpf"
        out_path.write_bytes(binary)

        rprint(f"[bold #a6e3a1]✔  Encoded profile saved to:[/] [bold #89b4fa]{out_path.name}[/]")
        rprint(f"  [dim #a6adc8]Size:[/] {len(binary)} bytes")
    except Exception as e:
        rprint(f"[bold #f38ba8]❌  Packing failed:[/] {e}")


def cmd_compile(args: list[str]) -> None:
    """
    Compiles JSON rule-sets into binary .srs files using sing-box core.

    Parameters
    ----------
    args : list[str]
        Command line arguments passed to the compile action.
    """
    parser = SBCParser(prog="rules compile", description="Compile rule-sets into .srs format.")
    parser.add_argument("-d", "--dir", type=Path, default=RULES_DIR, help="Input directory")
    parser.add_argument("-o", "--output", type=Path, default=SRS_DIR, help="Output directory for .srs files")
    parsed = parser.parse_args(args)

    input_dir: Path = parsed.dir
    output_dir: Path = parsed.output

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = list(input_dir.glob("*.json"))
    if not files:
        rprint("[dim #a6adc8]No rule-set JSON files found to compile.[/]")
        return

    for f in files:
        try:
            box.run(["rule-set", "format", "-w", str(f)])
            box.run(["rule-set", "compile", str(f), "-o", str(output_dir / f"{f.stem}.srs")])
            rprint(f"[bold #a6e3a1]Compiled:[/] {f.stem}.srs")
        except io.UnsupportedOperation:
            continue


def cmd_fetch_assets(args: list[str]) -> None:
    """
    Downloads necessary geoip and antizapret assets.

    Parameters
    ----------
    args : list[str]
        Command line arguments passed to the fetch-assets action.
    """
    parser = SBCParser(prog="other fetch-assets", description="Download required DB assets.")
    parser.add_argument("-o", "--output", type=Path, default=SRC_DIR / "antizapret", help="Output directory")
    parsed = parser.parse_args(args)

    out_dir: Path = parsed.output
    out_dir.mkdir(parents=True, exist_ok=True)

    urls = {
        "antizapret.srs": "https://krasovs.ky/sing-box/antizapret.srs",
        "geoip.db": "https://krasovs.ky/sing-box/geoip.db",
        "geosite.db": "https://krasovs.ky/sing-box/geosite.db",
    }

    with httpx.Client(follow_redirects=True) as client:
        for name, url in urls.items():
            rprint(f"[dim #a6adc8]Downloading {name}...[/]")
            try:
                (out_dir / name).write_bytes(client.get(url).content)
                rprint(f"[bold #a6e3a1]✔  Downloaded:[/] {name}")
            except httpx.RequestError as e:
                rprint(f"[bold #f38ba8]❌  Failed to download {name}:[/] {e}")


def cmd_monitor(_args: list[str]) -> None:
    """
    Provides real-time telemetry on active sing-box instances.

    Parameters
    ----------
    _args : list[str]
        Unused command line arguments.
    """
    rprint("[bold #89b4fa]📊  Sing-box Core & System Telemetry[/]\n")

    sb_processes: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            name_info = proc.info.get("name")
            if name_info and "sing-box" in str(name_info).lower():
                sb_processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sb_processes:
        rprint("[bold #a6e3a1]✔  Active sing-box core(s) detected:[/]")
        for sp in sb_processes:
            mem_info = sp.get("memory_info")
            # Safe extraction avoiding PyCharm's UnresolvedAttribute error for NamedTuples
            ram_mb = (getattr(mem_info, "rss", 0) // (1024 * 1024)) if mem_info else 0
            pid = sp.get("pid", "Unknown")
            cpu = sp.get("cpu_percent", 0.0)
            rprint(f"  [dim]• PID:[/] [bold #89b4fa]{pid}[/] | [dim]CPU:[/] {cpu}% | [dim]RAM:[/] {ram_mb} MB")
    else:
        rprint("[bold #f9e2af]⚠  No active sing-box processes running locally.[/]")

    rprint("\n[dim #a6adc8]Sampling live system metrics...[/]")
    cpu_history: list[float] = []
    ram_history: list[float] = []

    with Status("[dim]Collecting metrics...[/]", spinner="dots"):
        for _ in range(7):
            cpu_history.append(psutil.cpu_percent())
            ram_history.append(psutil.virtual_memory().percent)
            time.sleep(0.2)

    plt.clf()
    plt.plotsize(65, 12)
    plt.plot(cpu_history, label="CPU Usage %", color="green")
    plt.plot(ram_history, label="RAM Usage %", color="blue")
    plt.title("System Analytics Snapshot")
    plt.theme("dark")

    rprint("\n[bold #cba6f7]📈  Resource Utilization Grid:[/]\n")
    plt.show()
