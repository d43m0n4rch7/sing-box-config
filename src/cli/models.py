"""
Data structures and enumerations for the sing-box configuration CLI.

This module defines the strictly typed Pydantic models used to parse VLESS
URIs and construct binary profile payload structures (.bpf).
"""

from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field


class ProfileType(IntEnum):
    """
    Enumeration representing the deployment type of the sing-box profile.

    Attributes
    ----------
    LOCAL : int
        Locally stored and managed profile.
    ICLOUD : int
        Profile synchronized via Apple iCloud.
    REMOTE : int
        Profile fetched and updated from a remote URL.
    """
    LOCAL = 0
    ICLOUD = 1
    REMOTE = 2


class VlessParams(BaseModel):
    """
    Data model representing parsed parameters from a VLESS share link.

    Utilizes Pydantic v2 ConfigDict for modern validation and serialization,
    ignoring extra parameters that might be injected by various client versions.

    Attributes
    ----------
    name : str
        The display name of the proxy node.
    uuid : str
        The unique user identifier for authentication.
    server : str
        The remote server domain or IP address.
    port : int
        The server port.
    security : str
        The transport security type (e.g., 'tls', 'reality').
    encryption : str
        The encryption method.
    header_type : str
        The header type used for obfuscation.
    fp : str
        The uTLS fingerprint (e.g., 'chrome').
    type_ : str
        The transport network type (e.g., 'tcp', 'ws', 'grpc').
    flow : str
        XTLS flow control mechanisms.
    pbk : str
        The public key for Reality security.
    sni : str
        Server Name Indication for TLS/Reality.
    sid : str
        The short ID for Reality security.
    path : str
        The WebSocket path or gRPC service name.
    host : str
        The HTTP host header.
    alpn : str
        Application-Layer Protocol Negotiation values.
    all_params : dict[str, list[str]]
        A dictionary capturing all raw query parameters.
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str
    uuid: str
    server: str
    port: int
    security: str = "none"
    encryption: str = "none"
    header_type: str = Field("none", alias="headerType")
    fp: str = "chrome"
    type_: str = Field("tcp", alias="type")
    flow: str = ""
    pbk: str = ""
    sni: str = ""
    sid: str = ""
    path: str = ""
    host: str = ""
    alpn: str = ""
    all_params: dict[str, list[str]] = Field(default_factory=dict)


class ProfileContent(BaseModel):
    """
    Data model representing the payload required to build a binary profile (.bpf).

    Attributes
    ----------
    name : str
        The display name of the profile.
    type : ProfileType
        The deployment type of the profile.
    config : str
        The raw JSON configuration string.
    remote_path : str
        The path or URL for remote/iCloud profiles.
    auto_update : bool
        Whether the profile should automatically update.
    auto_update_interval : int
        Interval in minutes for automatic updates.
    last_updated : int
        Unix timestamp of the last update.
    """
    name: str
    type: ProfileType
    config: str
    remote_path: str = ""
    auto_update: bool = False
    auto_update_interval: int = 0
    last_updated: int = 0
