"""Pre-release privacy and metadata checks for neurodata."""

__version__ = "0.1.0.dev0"

from .scanner import ScanPolicy, scan_dataset

__all__ = ["ScanPolicy", "scan_dataset"]
