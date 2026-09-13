from __future__ import annotations

import gzip
import io
import zlib
from typing import Any


def decimal_payload_to_bytes(
    payload: str,
) -> bytes:
    """
    Convert Aadhaar QR decimal payload into
    its big-endian byte representation.

    The actual payload is NEVER printed.
    """

    if not payload:
        raise ValueError(
            "QR payload is empty"
        )

    payload = payload.strip()

    if not payload.isdigit():
        raise ValueError(
            "Payload is not numeric"
        )

    number = int(payload)

    if number == 0:
        return b"\x00"

    byte_length = (
        (number.bit_length() + 7)
        // 8
    )

    return number.to_bytes(
        byte_length,
        byteorder="big",
    )


def inspect_binary_payload(
    data: bytes,
) -> dict[str, Any]:

    result = {
        "success": False,
        "byte_length": len(data),
        "first_16_bytes_hex": (
            data[:16].hex()
        ),
        "last_16_bytes_hex": (
            data[-16:].hex()
        ),
        "gzip": False,
        "zlib": False,
        "jpeg2000": False,
        "ascii_prefix": None,
        "decompressed_length": None,
        "decompression": None,
        "error": None,
    }

    try:

        # ---------------------------------------------
        # GZIP
        # ---------------------------------------------

        if data.startswith(b"\x1f\x8b"):

            result["gzip"] = True

            try:

                decompressed = gzip.decompress(
                    data
                )

                result[
                    "decompressed_length"
                ] = len(decompressed)

                result[
                    "decompression"
                ] = "gzip"

            except Exception:
                result[
                    "decompression"
                ] = "gzip_failed"

        # ---------------------------------------------
        # ZLIB
        # ---------------------------------------------

        try:

            decompressed = zlib.decompress(
                data
            )

            result["zlib"] = True

            result[
                "decompressed_length"
            ] = len(decompressed)

            result[
                "decompression"
            ] = "zlib"

        except Exception:
            pass

        # ---------------------------------------------
        # JPEG 2000 detection
        #
        # JP2 file signature:
        # 00 00 00 0C 6A 50 20 20
        #
        # Raw JPEG2000 codestream:
        # FF 4F FF 51
        # ---------------------------------------------

        if (
            data.startswith(
                b"\x00\x00\x00\x0cjP  "
            )
            or data.startswith(
                b"\xff\x4f\xff\x51"
            )
        ):

            result[
                "jpeg2000"
            ] = True

        # ---------------------------------------------
        # Safe ASCII preview
        #
        # Only structural characters are returned.
        # No full payload is exposed.
        # ---------------------------------------------

        prefix = data[:32]

        safe_chars = []

        for byte in prefix:

            if 32 <= byte <= 126:

                safe_chars.append(
                    chr(byte)
                )

            else:

                safe_chars.append(".")

        result[
            "ascii_prefix"
        ] = "".join(safe_chars)

        result["success"] = True

        return result

    except Exception as exc:

        result["error"] = str(exc)

        return result


def decode_decimal_payload(
    payload: str,
) -> dict[str, Any]:

    result = {
        "success": False,
        "byte_length": 0,
        "binary": None,
        "inspection": None,
        "error": None,
    }

    try:

        binary = (
            decimal_payload_to_bytes(
                payload
            )
        )

        inspection = (
            inspect_binary_payload(
                binary
            )
        )

        result[
            "success"
        ] = inspection["success"]

        result[
            "byte_length"
        ] = len(binary)

        # IMPORTANT:
        # Keep binary internal.
        # Do not return it through the API.
        result[
            "binary"
        ] = binary

        result[
            "inspection"
        ] = inspection

        return result

    except Exception as exc:

        result["error"] = str(exc)

        return result