#!/usr/bin/env python3
"""Inspect, match, and symbolize firmware ELF/log evidence deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


EXIT_OK = 0
EXIT_INPUT = 2
EXIT_INSUFFICIENT_EVIDENCE = 3
EXIT_TOOL_FAILURE = 4


class InputError(ValueError):
    """Raised for malformed command input or log data."""


class EvidenceError(RuntimeError):
    """Raised when evidence cannot support matching or symbolization."""


class ToolError(RuntimeError):
    """Raised when a required external tool is unavailable or fails."""


def run_tool(command: Iterable[str]) -> str:
    rendered = [str(part) for part in command]
    try:
        completed = subprocess.run(
            rendered,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        raise ToolError(f"cannot run {' '.join(rendered)}: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ToolError(
            f"command failed with exit code {completed.returncode}: "
            f"{' '.join(rendered)}\n{detail}"
        )
    return completed.stdout


def resolve_tool(explicit: str | None, candidates: tuple[str, ...]) -> str:
    if explicit:
        resolved = shutil.which(explicit)
        if resolved:
            return resolved
        path = Path(explicit)
        if path.is_file():
            return str(path.resolve())
        raise ToolError(f"required tool does not exist: {explicit}")
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise ToolError("required tool not found; tried: " + ", ".join(candidates))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise InputError(f"cannot read {path}: {error}") from error
    return digest.hexdigest()


def read_build_id(elf: Path, readelf: str) -> str:
    match = re.search(r"Build ID:\s*([0-9A-Fa-f]+)", run_tool((readelf, "-n", str(elf))))
    if not match:
        raise EvidenceError(f"no GNU build ID found in {elf}")
    return match.group(1).lower()


def read_symbol_address(elf: Path, symbol: str, nm: str) -> str:
    for line in run_tool((nm, "-an", str(elf))).splitlines():
        fields = line.split()
        if (
            len(fields) >= 3
            and fields[-1] == symbol
            and re.fullmatch(r"[0-9A-Fa-f]+", fields[0])
            and fields[-2].upper() != "U"
        ):
            return f"0x{int(fields[0], 16):x}"
    raise EvidenceError(f"defined symbol {symbol!r} was not found in {elf}")


def parse_log(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise InputError(f"cannot read log {path}: {error}") from error
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key or not value:
            raise InputError(f"invalid log line {line_number}: {raw_line!r}")
        if key in values:
            raise InputError(f"duplicate log key: {key}")
        values[key] = value
    return values


def inspect_elf(elf: Path, map_path: Path | None, symbol: str, readelf: str, nm: str) -> dict[str, Any]:
    if not elf.is_file():
        raise InputError(f"ELF does not exist: {elf}")
    result: dict[str, Any] = {
        "artifact": elf.name,
        "elf": str(elf),
        "elf_sha256": sha256(elf),
        "build_id": read_build_id(elf, readelf),
        "symbol": symbol,
        "symbol_address": read_symbol_address(elf, symbol, nm),
        "tools": {"readelf": readelf, "nm": nm},
    }
    if map_path is not None:
        if not map_path.is_file():
            raise InputError(f"MAP does not exist: {map_path}")
        result["map"] = str(map_path)
        result["map_sha256"] = sha256(map_path)
    return result


def generate_log(path: Path, identity: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (
                "# Generated from the matching ELF; do not edit addresses manually.",
                "format_version=1",
                f"artifact={identity['artifact']}",
                f"build_id={identity['build_id']}",
                f"elf_sha256={identity['elf_sha256']}",
                f"symbol={identity['symbol']}",
                f"pc={identity['symbol_address']}",
                "evidence=generated_from_matching_elf",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )


def match_log(identity: dict[str, Any], log_path: Path) -> tuple[dict[str, Any], list[str]]:
    values = parse_log(log_path)
    required = {"artifact", "build_id", "symbol", "pc", "evidence"}
    gaps = [f"log key missing: {key}" for key in sorted(required - set(values))]
    if gaps:
        return values, gaps
    if values["artifact"] != identity["artifact"]:
        gaps.append(
            f"artifact mismatch: log={values['artifact']} elf={identity['artifact']}"
        )
    if values["build_id"].lower() != identity["build_id"]:
        gaps.append(
            f"build ID mismatch: log={values['build_id']} elf={identity['build_id']}"
        )
    if "elf_sha256" in values and values["elf_sha256"].lower() != identity["elf_sha256"]:
        gaps.append("ELF SHA-256 mismatch")
    if values["symbol"] != identity["symbol"]:
        gaps.append(f"symbol mismatch: log={values['symbol']} elf={identity['symbol']}")
    try:
        log_address = f"0x{int(values['pc'], 0):x}"
    except ValueError:
        gaps.append(f"invalid pc value: {values['pc']}")
    else:
        if log_address != identity["symbol_address"]:
            gaps.append(
                f"symbol address mismatch: log={log_address} elf={identity['symbol_address']}"
            )
    return values, gaps


def symbolize(identity: dict[str, Any], addr2line: str) -> dict[str, str]:
    lines = run_tool(
        (
            addr2line,
            "-e",
            identity["elf"],
            "-f",
            "-C",
            identity["symbol_address"],
        )
    ).splitlines()
    if len(lines) < 2:
        raise EvidenceError("addr2line returned incomplete function/source evidence")
    function_name = lines[0].strip()
    source_location = lines[1].strip()
    if function_name != identity["symbol"]:
        raise EvidenceError(
            f"symbolization mismatch: expected {identity['symbol']}, got {function_name}"
        )
    if source_location.startswith("??") or source_location.endswith(":0"):
        raise EvidenceError(f"addr2line did not resolve a source line: {source_location}")
    return {"function": function_name, "source": source_location, "tool": addr2line}


def emit(result: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "match", "symbolize", "roundtrip"))
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--map", dest="map_path", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--symbol", default="status_led_set")
    parser.add_argument("--readelf")
    parser.add_argument("--nm")
    parser.add_argument("--addr2line")
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output.resolve() if args.output else None
    try:
        if args.mode != "inspect" and args.log is None:
            raise InputError(f"{args.mode} requires --log")
        readelf = resolve_tool(args.readelf, ("readelf", "llvm-readelf"))
        nm = resolve_tool(args.nm, ("nm", "llvm-nm"))
        identity = inspect_elf(
            args.elf.resolve(),
            args.map_path.resolve() if args.map_path else None,
            args.symbol,
            readelf,
            nm,
        )
        result: dict[str, Any] = {"status": "COMPLETE", "identity": identity}
        if args.mode == "roundtrip":
            generate_log(args.log.resolve(), identity)
            result["generated_log"] = str(args.log.resolve())
        if args.mode in {"match", "symbolize", "roundtrip"}:
            log_values, gaps = match_log(identity, args.log.resolve())
            result["log"] = log_values
            result["evidence_gaps"] = gaps
            if gaps:
                result["status"] = "INSUFFICIENT_EVIDENCE"
                emit(result, output)
                return EXIT_INSUFFICIENT_EVIDENCE
        if args.mode in {"symbolize", "roundtrip"}:
            addr2line = resolve_tool(args.addr2line, ("addr2line", "llvm-addr2line"))
            result["symbolization"] = symbolize(identity, addr2line)
        emit(result, output)
        return EXIT_OK
    except InputError as error:
        emit({"status": "FAILED", "error": str(error)}, output)
        return EXIT_INPUT
    except EvidenceError as error:
        emit({"status": "INSUFFICIENT_EVIDENCE", "error": str(error)}, output)
        return EXIT_INSUFFICIENT_EVIDENCE
    except ToolError as error:
        emit({"status": "FAILED", "error": str(error)}, output)
        return EXIT_TOOL_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
