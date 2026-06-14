import logging
import torch

logger = logging.getLogger(__name__)

def get_best_device():
    """
    Returns the best available PyTorch device.
    Currently locked to CPU-only.
    """
    logger.info("Hardware detected: CPU")
    return torch.device("cpu")
