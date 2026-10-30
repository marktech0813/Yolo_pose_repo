#!/usr/bin/env python3
"""
Download offline Python wheelhouses for Northline.

Targets:
  - Linux x86_64 + Windows amd64
  - Python 3.10 GPU (CUDA 11.8)  [recommended]
  - Python 3.13 CPU             [best-effort; no cu118 torch wheels]

Run on a machine WITH internet once, then copy wheelhouse/ + models/ to offline PCs.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "requirements"
OUT = ROOT / "wheelhouse"
TORCH_INDEX = "https://download.pytorch.org/whl/cu118"
PYPI = "https://pypi.org/simple"

# Packages that are source-only (or rarely have binary wheels)
SDIST_OK = {
    "openai-whisper",
}

# Extra deps when torch/whisper are installed with --no-deps
TORCH_WHISPER_EXTRAS = [
    "networkx==3.4.2",
    "jinja2==3.1.6",
    "MarkupSafe==3.0.4",
    "colorama==0.4.6",
    "more-itertools==10.5.0",
    "numba==0.60.0",
    "llvmlite==0.43.0",
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def flatten_requirements(req: Path, *, strip_markers: bool = False, skip_cudnn: bool = False) -> list[str]:
    lines: list[str] = []

    def consume(path: Path) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("-r "):
                consume(path.parent / s[3:].strip())
                continue
            if skip_cudnn and "nvidia-cudnn-cu11" in s:
                continue
            if strip_markers and ";" in s:
                s = s.split(";", 1)[0].strip()
            lines.append(s)

    consume(req)
    return lines


def pkg_name(spec: str) -> str:
    raw = spec.split(";")[0].strip()
    return raw.split("==")[0].split(">=")[0].split("[")[0].strip().lower().replace("_", "-")


def has_artifact(dest: Path, name: str) -> bool:
    key = name.lower().replace("_", "-")
    for p in list(dest.glob("*.whl")) + list(dest.glob("*.tar.gz")):
        stem = p.name.split("-")[0].lower().replace("_", "-")
        if stem == key:
            return True
    return False


def pip_download_native(dest: Path, specs: list[str], extra_index: str | None = None) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "pip", "install", "-q", "setuptools", "wheel"])
    flat = dest / "_flat.txt"
    flat.write_text("\n".join(specs) + "\n", encoding="utf-8")
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "-r",
        str(flat),
        "-d",
        str(dest),
        "--no-build-isolation",
        "-i",
        PYPI,
    ]
    if extra_index:
        cmd.extend(["--extra-index-url", extra_index])
    run(cmd)
    flat.unlink(missing_ok=True)


def pip_download_cross(
    dest: Path,
    specs: list[str],
    *,
    python_version: str,
    plat: str,
    extra_index: str | None = None,
) -> None:
    """Download Windows/Linux wheels from the other OS (with deps)."""
    dest.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "pip", "install", "-q", "setuptools", "wheel"])
    abi = f"cp{python_version}"

    torch_specs = [s for s in specs if pkg_name(s) in {"torch", "torchaudio"}]
    sdist_specs = [s for s in specs if pkg_name(s) in SDIST_OK]
    other_specs = [
        s
        for s in specs
        if pkg_name(s) not in SDIST_OK and pkg_name(s) not in {"torch", "torchaudio"}
    ]

    # 1) torch/torchaudio from the official cu118 index only (avoid cu12 dep resolution)
    if torch_specs and extra_index:
        for spec in torch_specs:
            if has_artifact(dest, pkg_name(spec)):
                continue
            run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    spec,
                    "-d",
                    str(dest),
                    "--no-deps",
                    "--python-version",
                    python_version,
                    "--platform",
                    plat,
                    "--implementation",
                    "cp",
                    "--abi",
                    abi,
                    "--only-binary=:all:",
                    "--index-url",
                    extra_index,
                ]
            )

    # 2) remaining binary deps from PyPI for the target platform
    flat = dest / "_flat_binary.txt"
    flat.write_text("\n".join(other_specs) + "\n", encoding="utf-8")
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "-r",
            str(flat),
            "-d",
            str(dest),
            "--python-version",
            python_version,
            "--platform",
            plat,
            "--implementation",
            "cp",
            "--abi",
            abi,
            "--only-binary=:all:",
            "-i",
            PYPI,
        ]
    )
    flat.unlink(missing_ok=True)

    # 3) torch/whisper extras (because torch was fetched with --no-deps)
    for spec in TORCH_WHISPER_EXTRAS:
        if has_artifact(dest, pkg_name(spec)):
            continue
        try:
            run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    spec,
                    "-d",
                    str(dest),
                    "--no-deps",
                    "--python-version",
                    python_version,
                    "--platform",
                    plat,
                    "--implementation",
                    "cp",
                    "--abi",
                    abi,
                    "--only-binary=:all:",
                    "-i",
                    PYPI,
                ]
            )
        except subprocess.CalledProcessError:
            # pure-python fallback
            run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    spec,
                    "-d",
                    str(dest),
                    "--no-deps",
                    "-i",
                    PYPI,
                ]
            )

    # 4) sdists (openai-whisper)
    for spec in sdist_specs:
        if has_artifact(dest, pkg_name(spec)):
            continue
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                spec,
                "-d",
                str(dest),
                "--no-deps",
                "--no-build-isolation",
                "-i",
                PYPI,
            ]
        )

    cudnn = "nvidia-cudnn-cu11==8.9.5.29" if plat.startswith("win") else "nvidia-cudnn-cu11==8.9.6.50"
    if not has_artifact(dest, "nvidia-cudnn-cu11"):
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                cudnn,
                "-d",
                str(dest),
                "--no-deps",
                "--python-version",
                python_version,
                "--platform",
                plat,
                "--implementation",
                "cp",
                "--abi",
                abi,
                "--only-binary=:all:",
                "-i",
                PYPI,
            ]
        )

    if plat.startswith("win"):
        for p in list(dest.glob("*manylinux*.whl")) + list(dest.glob("*linux_x86_64*.whl")):
            print(f"Removing non-Windows wheel: {p.name}")
            p.unlink()
        # Drop accidental CUDA 12 nvidia wheels pulled by bad resolvers
        for p in dest.glob("nvidia_*_cu12-*.whl"):
            print(f"Removing cu12 wheel: {p.name}")
            p.unlink()


def write_manifest(dest: Path, label: str) -> None:
    files = sorted(p.name for p in dest.glob("*.whl")) + sorted(p.name for p in dest.glob("*.tar.gz"))
    (dest / "MANIFEST.txt").write_text(
        f"# Northline wheelhouse: {label}\n# count={len(files)}\n" + "\n".join(files) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {dest / 'MANIFEST.txt'} ({len(files)} artifacts)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=["all", "linux310-gpu", "windows310-gpu", "linux313-cpu", "windows313-cpu"],
        default="all",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    host = platform.system().lower()

    jobs: list[tuple[str, Path, Path, str | None, str, bool]] = []
    if args.target in {"all", "linux310-gpu"}:
        jobs.append(
            (
                "linux-cp310-cu118",
                OUT / "linux-cp310-cu118",
                REQ / "gpu-cu118.txt",
                TORCH_INDEX,
                "manylinux2014_x86_64",
                host != "linux",
            )
        )
    if args.target in {"all", "windows310-gpu"}:
        jobs.append(
            (
                "windows-cp310-cu118",
                OUT / "windows-cp310-cu118",
                REQ / "gpu-cu118.txt",
                TORCH_INDEX,
                "win_amd64",
                host != "windows",
            )
        )
    if args.target in {"all", "linux313-cpu"}:
        jobs.append(
            (
                "linux-cp313-cpu",
                OUT / "linux-cp313-cpu",
                REQ / "cpu-py313.txt",
                None,
                "manylinux2014_x86_64",
                host != "linux",
            )
        )
    if args.target in {"all", "windows313-cpu"}:
        jobs.append(
            (
                "windows-cp313-cpu",
                OUT / "windows-cp313-cpu",
                REQ / "cpu-py313.txt",
                None,
                "win_amd64",
                host != "windows",
            )
        )

    for label, dest, req, extra, plat, cross in jobs:
        print(f"\n=== Building {label} (cross={cross}) ===", flush=True)
        if cross:
            specs = flatten_requirements(req, strip_markers=True, skip_cudnn=True)
            if plat.startswith("win"):
                # uvloop has no Windows wheels; marker was stripped for cross download
                specs = [s for s in specs if pkg_name(s) != "uvloop"]
            py = "313" if "313" in label else "310"
            if dest.exists():
                for p in dest.glob("*manylinux*.whl"):
                    p.unlink()
            pip_download_cross(dest, specs, python_version=py, plat=plat, extra_index=extra)
            # Reuse openai-whisper sdist from linux house if present
            if not has_artifact(dest, "openai-whisper"):
                for src in (OUT / "linux-cp310-cu118").glob("openai_whisper-*.tar.gz"):
                    shutil.copy2(src, dest / src.name)
                    print(f"Copied {src.name} into {label}")
                    break
                for src in (OUT / "linux-cp310-cu118").glob("openai-whisper-*.tar.gz"):
                    shutil.copy2(src, dest / src.name)
                    print(f"Copied {src.name} into {label}")
                    break
        else:
            specs = flatten_requirements(req)
            pip_download_native(dest, specs, extra_index=extra)
        write_manifest(dest, label)

    print("\nDone. Copy wheelhouse/ + models/ + the app to offline machines.")
    print("Install with scripts/install_offline.sh or scripts/install_offline.ps1")


if __name__ == "__main__":
    os.environ.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    main()
