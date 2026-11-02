"""内存回收辅助。"""

from __future__ import annotations

import ctypes
import gc
import sys


def _trim_os_memory() -> None:
    """Ask the OS to release pages back to the system."""
    try:
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            handle = kernel32.GetCurrentProcess()
            if not psapi.EmptyWorkingSet(handle):
                kernel32.SetProcessWorkingSetSize(
                    handle, ctypes.c_size_t(-1), ctypes.c_size_t(-1)
                )
        elif sys.platform.startswith("linux"):
            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
    except Exception:
        return


def release_memory(*, trim_os: bool = False) -> None:
    """Best-effort cleanup between pipeline stages; never raises.

    ``trim_os`` is intentionally off for per-shot cleanup because forcing
    working-set trimming too often causes page faults. Use it at stage ends.
    """
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is not None:
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:
            pass
    if trim_os:
        _trim_os_memory()