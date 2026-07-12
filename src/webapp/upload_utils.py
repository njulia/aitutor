"""Bounded, collision-free upload handling."""
from __future__ import annotations

import base64
import binascii
import os
import tempfile
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile

_CHUNK_SIZE = 1024 * 1024


def normalised_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def _looks_like(ext: str, header: bytes) -> bool:
    if ext == "pdf":
        return header.startswith(b"%PDF-")
    if ext == "png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in {"jpg", "jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if ext == "gif":
        return header.startswith((b"GIF87a", b"GIF89a"))
    if ext == "heic":
        return len(header) >= 12 and header[4:8] == b"ftyp"
    if ext in {"txt", "md", "csv"}:
        return b"\x00" not in header
    return False


async def stream_upload_to_temp(
    upload: UploadFile,
    *,
    allowed_extensions: Iterable[str],
    max_bytes: int,
    directory: str,
) -> str:
    ext = normalised_extension(upload.filename or "")
    allowed = {item.lower().lstrip(".") for item in allowed_extensions}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    os.makedirs(directory, exist_ok=True)
    total = 0
    header = b""
    fd, path = tempfile.mkstemp(prefix="upload_", suffix=f".{ext}", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            while True:
                chunk = await upload.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail="File too large")
                if len(header) < 64:
                    header += chunk[: 64 - len(header)]
                handle.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="The file is empty")
        if not _looks_like(ext, header):
            raise HTTPException(status_code=400, detail="The file content does not match its extension")
        return path
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    finally:
        await upload.close()


def decode_base64_image_to_temp(data_url: str, *, max_bytes: int) -> str:
    raw = str(data_url or "")
    if "," in raw:
        prefix, raw = raw.split(",", 1)
        if "base64" not in prefix.lower():
            raise HTTPException(status_code=400, detail="Invalid photo data")
    try:
        estimated = (len(raw) * 3) // 4
        if estimated > max_bytes:
            raise HTTPException(status_code=413, detail="Photo too large")
        image = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid photo data") from exc
    if len(image) > max_bytes:
        raise HTTPException(status_code=413, detail="Photo too large")
    suffix = ".jpg"
    if image.startswith(b"\x89PNG"):
        suffix = ".png"
    elif not image.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=400, detail="Only JPEG or PNG photos are supported")
    with tempfile.NamedTemporaryFile(prefix="photo_", suffix=suffix, delete=False) as handle:
        handle.write(image)
        return handle.name
