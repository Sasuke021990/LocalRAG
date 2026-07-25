import logging
import os

import torch

logger = logging.getLogger(__name__)


def get_best_device():
    """
    Pick the PyTorch device for the embedding / re-ranking models.

    Defaults to CPU, which is the only universally-safe choice: this ships in
    a container that may or may not have been started with GPU passthrough,
    and picking an unavailable device would break model loading at startup.
    Set ``TORCH_DEVICE`` to override:

        TORCH_DEVICE=auto   cuda -> mps -> cpu, whichever is available first
        TORCH_DEVICE=cuda   force CUDA (falls back to CPU with a warning)
        TORCH_DEVICE=mps    force Apple Metal (falls back to CPU with a warning)
        TORCH_DEVICE=cpu    force CPU (default)

    Embedding on a GPU is roughly an order of magnitude faster than on CPU,
    and embedding dominates ingestion time for large documents. Using one
    needs both a CUDA-capable torch build and a container started with GPU
    access (compose ``deploy.resources.reservations.devices``); every mode
    above degrades to CPU rather than failing when that isn't in place.
    """
    requested = os.getenv("TORCH_DEVICE", "cpu").strip().lower()

    def _cuda_ok() -> bool:
        try:
            return torch.cuda.is_available()
        except Exception:
            return False

    def _mps_ok() -> bool:
        try:
            return torch.backends.mps.is_available()
        except Exception:
            return False

    if requested == "auto":
        chosen = "cuda" if _cuda_ok() else ("mps" if _mps_ok() else "cpu")
    elif requested == "cuda":
        chosen = "cuda" if _cuda_ok() else "cpu"
        if chosen == "cpu":
            logger.warning("TORCH_DEVICE=cuda requested but CUDA is unavailable — falling back to CPU")
    elif requested == "mps":
        chosen = "mps" if _mps_ok() else "cpu"
        if chosen == "cpu":
            logger.warning("TORCH_DEVICE=mps requested but MPS is unavailable — falling back to CPU")
    else:
        if requested != "cpu":
            logger.warning(f"Unrecognized TORCH_DEVICE='{requested}' — using CPU")
        chosen = "cpu"

    logger.info(f"Hardware detected: {chosen.upper()}")
    return torch.device(chosen)
