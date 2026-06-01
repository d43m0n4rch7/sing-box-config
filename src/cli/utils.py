"""
Core utility functions and managers for the sing-box CLI.

Handles binary execution, VLESS URI parsing, JSON template injection,
and custom binary serialization for the .bpf format.
"""

import gzip
import io
import json
import re
import shutil
import struct
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

from rich import print as rprint
from rich.panel import Panel
from sing_box_bin import get_bin_path

from .models import ProfileContent, ProfileType, VlessParams


class SingBoxManager:
    """
    Wrapper for executing sing-box binary commands with error capturing.
    """

    @property
    def bin_path(self) -> Path:
        """
        Resolves the absolute path to the sing-box executable.

        Safely handles environment PATH lookups across different OS platforms
        without raising type errors on Windows before Python 3.12.

        Returns
        -------
        Path
            Absolute path to the executable binary.
        """
        binary_str: str | None = shutil.which("sing-box") or shutil.which("sing-box-beta")
        if binary_str:
            return Path(binary_str).absolute()

        # get_bin_path() strictly returns a Path object
        return get_bin_path().absolute()

    def run(self, args: list[str]) -> None:
        """
        Executes a command via the sing-box binary and surfaces stderr on failure.

        Parameters
        ----------
        args : list[str]
            Arguments to pass to the sing-box binary.

        Raises
        ------
        io.UnsupportedOperation
            If the subprocess returns a non-zero exit code.
        """
        try:
            subprocess.run([str(self.bin_path), *args], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            rprint(
                Panel(
                    f"[bold #f38ba8]Error executing sing-box command:[/\n"
                    f"[dim #a6adc8]Command:[/] sing-box {' '.join(args)}\n\n"
                    f"[bold #f38ba8]Stderr Output:[/\n{e.stderr.strip()}",
                    title="[bold #f38ba8]Sing-box Failure[/]",
                    border_style="#f38ba8",
                )
            )
            raise io.UnsupportedOperation("Sing-box binary execution failed.") from e


box = SingBoxManager()


def parse_vless_url(vless_url: str) -> VlessParams:
    """
    Parses a standard VLESS URI into a structured Pydantic model.

    Parameters
    ----------
    vless_url : str
        The raw `vless://` link containing connection metrics.

    Returns
    -------
    VlessParams
        Strictly typed model containing parsed outbound details.

    Raises
    ------
    ValueError
        If the URL does not start with the 'vless://' scheme.
    """
    if not vless_url.startswith("vless://"):
        raise ValueError("Invalid URL format. Must start with 'vless://'.")

    p = urllib.parse.urlparse(vless_url)
    qs: dict[str, list[str]] = urllib.parse.parse_qs(p.query)
    q: dict[str, str] = {k: v[0] for k, v in qs.items()}

    return VlessParams(
        name=urllib.parse.unquote(p.fragment or "VLESS"),
        uuid=p.username or "",
        server=p.hostname or "",
        port=p.port or 443,
        all_params=qs,
        **q,
    )


def load_template(path: Path) -> dict[str, Any]:
    """
    Loads and safely parses a JSON template file into a dictionary.

    Parameters
    ----------
    path : Path
        The file path to the JSON template.

    Returns
    -------
    dict[str, Any]
        The parsed JSON payload represented as a dictionary.

    Raises
    ------
    ValueError
        If the parsed JSON is not a dictionary.
    """
    raw_data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError("Invalid JSON template: root element must be an object.")

    # Dictionary comprehension guarantees Pyright type safety without explicit cast calls.
    return {str(k): v for k, v in raw_data.items()}


def update_vless_outbound(config: dict[str, Any], vless: VlessParams) -> None:
    """
    Injects parsed VLESS parameters into the designated VLESS outbound configuration.

    Parameters
    ----------
    config : dict[str, Any]
        The full sing-box configuration dictionary.
    vless : VlessParams
        The parsed VLESS parameters model.
    """
    for outbound in config.get("outbounds", []):
        if outbound.get("type") != "vless":
            continue

        outbound["server"] = vless.server
        outbound["server_port"] = vless.port
        outbound["uuid"] = vless.uuid

        if vless.flow:
            outbound["flow"] = vless.flow

        if vless.security in ("reality", "tls"):
            tls = outbound.setdefault("tls", {})
            tls["enabled"] = True
            if vless.sni:
                tls["server_name"] = vless.sni

            utls = tls.setdefault("utls", {})
            utls["enabled"] = True
            utls["fingerprint"] = vless.fp

            if vless.security == "reality":
                reality = tls.setdefault("reality", {})
                reality["enabled"] = True
                if vless.pbk:
                    reality["public_key"] = vless.pbk
                if vless.sid:
                    reality["short_id"] = vless.sid

        if vless.type_ in ("ws", "grpc"):
            transport = outbound.setdefault("transport", {})
            transport["type"] = vless.type_

            if vless.type_ == "ws":
                ws = transport.setdefault("ws", {})
                if vless.path:
                    ws["path"] = vless.path
                if vless.host:
                    ws["headers"] = {"Host": vless.host}
            elif vless.type_ == "grpc" and vless.path:
                grpc = transport.setdefault("grpc", {})
                grpc["service_name"] = vless.path


def sanitize_filename(name: str) -> str:
    """
    Strips special characters, emojis, and consecutive spaces to generate a safe OS filename.

    Parameters
    ----------
    name : str
        The raw input string.

    Returns
    -------
    str
        A sanitized string safe for use as a cross-platform filename.
    """
    sanitized = re.sub(r"[^\w\s\-.]", "", name)
    sanitized = re.sub(r"[\s_]+", "_", sanitized)
    return sanitized.strip("_-. ")[:100] or "config"


def write_uvarint(writer: io.BytesIO, value: int) -> None:
    """
    Writes an unsigned variable-length integer to the buffer.

    Parameters
    ----------
    writer : io.BytesIO
        The target byte stream.
    value : int
        The integer to encode.
    """
    while value >= 0x80:
        writer.write(struct.pack("B", (value & 0x7F) | 0x80))
        value >>= 7
    writer.write(struct.pack("B", value & 0x7F))


def write_varbin_string(writer: io.BytesIO, value: str) -> None:
    """
    Encodes a string as UTF-8 and writes it to the buffer prefixed by its uvarint length.

    Parameters
    ----------
    writer : io.BytesIO
        The target byte stream.
    value : str
        The string to encode and write.
    """
    data = value.encode("utf-8")
    write_uvarint(writer, len(data))
    writer.write(data)


def encode_profile_content(profile: ProfileContent) -> bytes:
    """
    Encodes ProfileContent into the compressed binary format required by sing-box clients.

    Parameters
    ----------
    profile : ProfileContent
        The populated profile model.

    Returns
    -------
    bytes
        The fully compressed binary payload (.bpf format).
    """
    buffer = io.BytesIO()
    buffer.write(struct.pack("B", 3))
    buffer.write(struct.pack("B", 1))

    comp = io.BytesIO()
    with gzip.GzipFile(fileobj=comp, mode="wb") as gz:
        inner = io.BytesIO()
        write_varbin_string(inner, profile.name)
        inner.write(struct.pack(">i", profile.type.value))
        write_varbin_string(inner, profile.config)

        if profile.type != ProfileType.LOCAL:
            write_varbin_string(inner, profile.remote_path)

        gz.write(inner.getvalue())

    buffer.write(comp.getvalue())
    return buffer.getvalue()
