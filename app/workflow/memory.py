from __future__ import annotations

import gc
import sys


def release_memory() -> None:
    """Best-effort cleanup between pipeline stages; never raises."""
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is None:
        return
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        return
