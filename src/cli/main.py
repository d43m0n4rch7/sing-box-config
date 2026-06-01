"""
Application entrypoint and interactive REPL shell management.

This module sets up the prompt_toolkit session, implements nested autocompletion,
and delegates parsed command arrays to the appropriate handler functions.
"""

import shlex
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import commands

console = Console()

# Unified command router mapping logic to execution
COMMAND_TREE: dict[str, dict[str, Callable[[list[str]], None]]] = {
    "config": {
        "generate": commands.cmd_generate,
        "format": commands.cmd_format,
        "pack": commands.cmd_pack,
    },
    "rules": {
        "compile": commands.cmd_compile,
    },
    "other": {
        "fetch-assets": commands.cmd_fetch_assets,
        "monitor": commands.cmd_monitor,
    },
}


def show_welcome_help() -> None:
    """
    Renders the stylized main menu and usage guide.
    Outputs a Rich table formatted with Catppuccin themes.
    """
    rprint("[bold #89b4fa]🚀  Welcome to sbc Interactive Shell![/]")
    rprint("[dim #a6adc8]Type commands directly. Use Tab for autocomplete.[/]\n")

    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="bold #a6e3a1")
    table.add_column(style="#89b4fa")
    table.add_column(style="dim #a6adc8")

    table.add_row("config", "generate, format, pack", "Manage and pack JSON configurations")
    table.add_row("rules", "compile", "Compile JSON rule-sets into .srs")
    table.add_row("other", "fetch-assets, monitor", "Fetch telemetry and additional utilities")
    table.add_row("clear", "", "Clear the terminal screen")
    table.add_row("exit / quit", "", "Close the interactive shell")

    rprint(
        Panel(
            table,
            title="[bold #cba6f7]Available Commands[/]",
            border_style="#b4befe",
            expand=False,
            padding=(0, 2),
        )
    )
    rprint()


def execute_command(args: list[str]) -> None:
    """
    Dispatches execution to the corresponding handler based on arguments.

    Parameters
    ----------
    args : list[str]
        The tokenized input arguments from the REPL shell or CLI.
    """
    if not args:
        show_welcome_help()
        return

    group = args[0]
    if group not in COMMAND_TREE:
        rprint(f"[bold #f38ba8]❌  Unknown command group:[/] {group}")
        rprint("[dim #a6adc8]Available groups: config, rules, other[/]")
        return

    if len(args) < 2:
        cmds = ", ".join(COMMAND_TREE[group].keys())
        rprint(f"[bold #f9e2af]⚠  Incomplete command.[/] Available in '{group}': {cmds}")
        return

    action = args[1]
    if action not in COMMAND_TREE[group]:
        rprint(f"[bold #f38ba8]❌  Unknown command:[/] {group} {action}")
        return

    func = COMMAND_TREE[group][action]
    try:
        func(args[2:])
    except SystemExit:
        pass
    except Exception as e:
        rprint(f"[bold #f38ba8]❌  Execution error:[/] {e}")


def start_interactive_shell() -> None:
    """
    Initializes the prompt_toolkit REPL session with history and completions.

    Sets up the nested autocompletion dictionary safely and starts the
    infinite prompt loop.
    """
    show_welcome_help()

    # Create a rigidly typed nested dictionary for prompt-toolkit to prevent Pyright errors
    completer_dict: dict[str, Any] = {grp: dict.fromkeys(cmds) for grp, cmds in COMMAND_TREE.items()}
    completer_dict.update({"clear": None, "exit": None, "quit": None})
    completer = NestedCompleter.from_nested_dict(completer_dict)

    history_file = Path.home() / ".sbc_history"
    session: PromptSession[str] = PromptSession(completer=completer, history=FileHistory(str(history_file)))

    while True:
        try:
            text = session.prompt(
                HTML('<style fg="#89b4fa" bold="true">sbc</style><style fg="#a6adc8"> ❯ </style>')
            ).strip()

            if not text:
                continue
            if text.lower() in ("exit", "quit"):
                rprint("[bold #f38ba8]Goodbye![/]")
                break
            if text.lower() == "clear":
                console.clear()
                continue

            execute_command(shlex.split(text))

        except KeyboardInterrupt:
            rprint()
            continue
        except EOFError:
            rprint("\n[bold #f38ba8]Goodbye![/]")
            break


def main() -> None:
    """
    Main CLI entrypoint.

    Diverts flow to either the interactive REPL shell or processes
    a single command execution if arguments are provided via argv.
    """
    if len(sys.argv) == 1:
        start_interactive_shell()
    else:
        execute_command(sys.argv[1:])


if __name__ == "__main__":
    main()
