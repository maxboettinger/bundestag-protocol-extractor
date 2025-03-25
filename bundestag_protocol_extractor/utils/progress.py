"""
Progress tracking utilities for the Bundestag Protocol Extractor.

This module provides progress tracking functionality for long-running extraction tasks,
including saving and resuming progress state, real-time progress reporting,
and time estimation.
"""

import json
import logging
import os
import pickle
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from tqdm import tqdm

from bundestag_protocol_extractor.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionProgress:
    """
    Data class for tracking extraction progress.

    This class stores information about the current state of an extraction job,
    including completed protocol IDs, failures, and timing information.
    """

    # Core tracking
    wahlperiode: int
    total_protocols: int = 0
    completed_protocol_ids: Set[int] = field(default_factory=set)
    failed_protocol_ids: Dict[int, str] = field(default_factory=dict)
    current_protocol_id: Optional[int] = None

    # Status information
    start_time: datetime = field(default_factory=datetime.now)
    last_update_time: datetime = field(default_factory=datetime.now)
    status: str = "initializing"  # initializing, running, paused, completed, failed

    # Job specification
    job_id: str = field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    job_params: Dict[str, Any] = field(default_factory=dict)
    output_paths: List[Path] = field(default_factory=list)

    # Usage statistics
    api_calls: int = 0
    rate_limit_hits: int = 0
    retry_count: int = 0

    def __post_init__(self):
        """Convert string paths to Path objects if needed."""
        if self.output_paths and isinstance(self.output_paths[0], str):
            self.output_paths = [
                Path(p) if isinstance(p, str) else p for p in self.output_paths
            ]

    @property
    def completed_count(self) -> int:
        """Get the number of completed protocols."""
        return len(self.completed_protocol_ids)

    @property
    def failed_count(self) -> int:
        """Get the number of failed protocols."""
        return len(self.failed_protocol_ids)

    @property
    def success_rate(self) -> float:
        """Get the success rate as a percentage."""
        if self.completed_count + self.failed_count == 0:
            return 0.0
        return 100.0 * self.completed_count / (self.completed_count + self.failed_count)

    @property
    def elapsed_time(self) -> timedelta:
        """Get the elapsed time since job start."""
        return datetime.now() - self.start_time

    @property
    def estimated_remaining_time(self) -> Optional[timedelta]:
        """
        Estimate remaining time based on progress and elapsed time.

        Returns:
            Estimated remaining time as timedelta or None if cannot estimate
        """
        processed = self.completed_count + self.failed_count
        if processed == 0 or self.total_protocols == 0:
            return None

        # Calculate time per item and estimate remaining time
        elapsed_seconds = self.elapsed_time.total_seconds()
        seconds_per_item = elapsed_seconds / processed
        remaining_items = self.total_protocols - processed

        remaining_seconds = seconds_per_item * remaining_items
        return timedelta(seconds=remaining_seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert progress object to dictionary for serialization."""
        data = asdict(self)
        # Convert sets to lists for JSON serialization
        data["completed_protocol_ids"] = list(self.completed_protocol_ids)
        # Convert datetime objects to strings
        data["start_time"] = self.start_time.isoformat()
        data["last_update_time"] = self.last_update_time.isoformat()
        # Convert Path objects to strings
        data["output_paths"] = [str(p) for p in self.output_paths]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionProgress":
        """Create progress object from dictionary."""
        # Convert list back to set
        data["completed_protocol_ids"] = set(data["completed_protocol_ids"])
        # Convert string dates back to datetime
        data["start_time"] = datetime.fromisoformat(data["start_time"])
        data["last_update_time"] = datetime.fromisoformat(data["last_update_time"])
        # Convert string paths back to Path objects
        data["output_paths"] = [Path(p) for p in data["output_paths"]]
        return cls(**data)

    def mark_completed(self, protocol_id: int) -> None:
        """Mark a protocol as successfully completed."""
        self.completed_protocol_ids.add(protocol_id)
        self.current_protocol_id = None
        self.last_update_time = datetime.now()

    def mark_failed(self, protocol_id: int, error_message: str) -> None:
        """Mark a protocol as failed with error message."""
        self.failed_protocol_ids[protocol_id] = error_message
        self.current_protocol_id = None
        self.last_update_time = datetime.now()

    def mark_started(self, protocol_id: int) -> None:
        """Mark a protocol as started processing."""
        self.current_protocol_id = protocol_id
        self.last_update_time = datetime.now()


class ProgressTracker:
    """
    Tracks progress for long-running extraction jobs.

    This class manages the state of extraction jobs, including saving and
    loading progress information, and provides real-time progress updates.
    """

    def __init__(
        self,
        wahlperiode: int,
        output_dir: Union[str, Path],
        job_params: Optional[Dict[str, Any]] = None,
        auto_save_interval: int = 60,  # seconds
        resume_from: Optional[Union[str, Path]] = None,
    ):
        """
        Initialize the progress tracker.

        Args:
            wahlperiode: Legislative period being processed
            output_dir: Directory for saving progress files
            job_params: Optional parameters describing the job
            auto_save_interval: How often to auto-save progress in seconds
            resume_from: Optional path to a progress file to resume from
        """
        self.output_dir = Path(output_dir)
        self.progress_dir = self.output_dir / "progress"
        self.progress_dir.mkdir(exist_ok=True, parents=True)

        self.auto_save_interval = auto_save_interval
        self.last_save_time = time.time()

        # Set up progress data
        if resume_from:
            # Resume from saved progress
            self.progress = self._load_progress(resume_from)
            logger.info(
                f"Resumed extraction job {self.progress.job_id} from {resume_from}"
            )
            # Update status to running
            self.progress.status = "running"
        else:
            # Start a new job
            self.progress = ExtractionProgress(
                wahlperiode=wahlperiode, job_params=job_params or {}
            )
            logger.info(f"Started new extraction job {self.progress.job_id}")

        # Initialize TQDM progress bar
        self.pbar = None

    def init_total(self, total_protocols: int) -> None:
        """
        Initialize the total number of protocols to track.

        Args:
            total_protocols: Total number of protocols to process
        """
        self.progress.total_protocols = total_protocols
        self.progress.status = "running"

        # Initialize progress bar
        self.pbar = tqdm(
            total=total_protocols,
            initial=self.progress.completed_count,
            desc=f"WP{self.progress.wahlperiode}",
            unit="protocol",
        )

        # Save initial state
        self.save_progress()

        logger.info(
            f"Initialized progress tracker with {total_protocols} total protocols"
        )
        logger.info(
            f"Already completed: {self.progress.completed_count}, "
            f"failed: {self.progress.failed_count}"
        )

    def update_api_stats(
        self, api_call: bool = False, rate_limit: bool = False, retry: bool = False
    ) -> None:
        """
        Update API usage statistics.

        Args:
            api_call: Whether an API call was made
            rate_limit: Whether a rate limit was hit
            retry: Whether a retry was performed
        """
        if api_call:
            self.progress.api_calls += 1
        if rate_limit:
            self.progress.rate_limit_hits += 1
        if retry:
            self.progress.retry_count += 1

    def start_protocol(self, protocol_id: int) -> None:
        """
        Mark the start of processing a specific protocol.

        Args:
            protocol_id: ID of the protocol being processed
        """
        self.progress.mark_started(protocol_id)
        self._check_auto_save()

    def complete_protocol(self, protocol_id: int) -> None:
        """
        Mark a protocol as successfully completed.

        Args:
            protocol_id: ID of the completed protocol
        """
        # Skip if already completed
        if protocol_id in self.progress.completed_protocol_ids:
            return

        self.progress.mark_completed(protocol_id)

        # Update progress bar
        if self.pbar:
            self.pbar.update(1)
            # Add completion percentage to progress bar description
            completion_pct = (
                100.0 * self.progress.completed_count / self.progress.total_protocols
            )
            self.pbar.set_description(
                f"WP{self.progress.wahlperiode} [{completion_pct:.1f}%]"
            )

            # Add ETA to postfix
            if self.progress.estimated_remaining_time:
                eta_str = str(self.progress.estimated_remaining_time).split(".")[
                    0
                ]  # remove microseconds
                self.pbar.set_postfix(ETA=eta_str, refresh=True)

        # Log every 10 protocols
        if self.progress.completed_count % 10 == 0:
            logger.info(
                f"Completed {self.progress.completed_count}/{self.progress.total_protocols} "
                f"protocols ({self.progress.success_rate:.1f}% success rate)"
            )

        self._check_auto_save()

    def fail_protocol(self, protocol_id: int, error_message: str) -> None:
        """
        Mark a protocol as failed.

        Args:
            protocol_id: ID of the failed protocol
            error_message: Description of the error
        """
        self.progress.mark_failed(protocol_id, error_message)

        # Log the failure
        logger.warning(f"Failed to process protocol {protocol_id}: {error_message}")

        self._check_auto_save()

    def get_resume_point(self) -> Dict[str, Any]:
        """
        Get information needed to resume the job.

        Returns:
            Dictionary with resume information (completed_ids, next_index, etc.)
        """
        return {
            "completed_protocol_ids": list(self.progress.completed_protocol_ids),
            "failed_protocol_ids": list(self.progress.failed_protocol_ids.keys()),
            "last_protocol_id": self.progress.current_protocol_id,
            "job_id": self.progress.job_id,
        }

    def save_progress(self) -> Path:
        """
        Save current progress to file.

        Returns:
            Path to the saved progress file
        """
        # Update timestamp
        self.progress.last_update_time = datetime.now()

        # Generate filename based on job ID
        filepath = self.progress_dir / f"progress_{self.progress.job_id}.json"

        # Save as JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.progress.to_dict(), f, indent=2)

        # Update last save time
        self.last_save_time = time.time()

        return filepath

    def _load_progress(self, progress_path: Union[str, Path]) -> ExtractionProgress:
        """
        Load progress from a saved file.

        Args:
            progress_path: Path to the progress file

        Returns:
            Loaded progress object
        """
        progress_path = Path(progress_path)

        with open(progress_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ExtractionProgress.from_dict(data)

    def _check_auto_save(self) -> None:
        """Check if it's time to auto-save and save if needed."""
        current_time = time.time()
        if current_time - self.last_save_time >= self.auto_save_interval:
            saved_path = self.save_progress()
            logger.debug(f"Auto-saved progress to {saved_path}")

    def complete(self) -> Dict[str, Any]:
        """
        Mark the job as completed and return summary statistics.

        Returns:
            Dictionary with job statistics
        """
        self.progress.status = "completed"

        # Close progress bar
        if self.pbar:
            self.pbar.close()

        # Get final stats
        elapsed_time = self.progress.elapsed_time
        hours, remainder = divmod(elapsed_time.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)

        stats = {
            "job_id": self.progress.job_id,
            "wahlperiode": self.progress.wahlperiode,
            "total_protocols": self.progress.total_protocols,
            "completed_protocols": self.progress.completed_count,
            "failed_protocols": self.progress.failed_count,
            "success_rate": self.progress.success_rate,
            "elapsed_time": f"{int(hours)}h {int(minutes)}m {int(seconds)}s",
            "elapsed_seconds": elapsed_time.total_seconds(),
            "api_calls": self.progress.api_calls,
            "rate_limit_hits": self.progress.rate_limit_hits,
            "retry_count": self.progress.retry_count,
        }

        # Save final progress
        self.save_progress()

        # Log completion
        logger.info(f"Extraction job {self.progress.job_id} completed:")
        logger.info(
            f"  Processed {self.progress.total_protocols} protocols "
            f"({self.progress.completed_count} successful, {self.progress.failed_count} failed)"
        )
        logger.info(f"  Success rate: {self.progress.success_rate:.1f}%")
        logger.info(f"  Total time: {stats['elapsed_time']}")
        logger.info(
            f"  API calls: {self.progress.api_calls} "
            f"({self.progress.rate_limit_hits} rate limits, {self.progress.retry_count} retries)"
        )

        return stats

    def list_available_progress_files(self) -> List[Dict[str, Any]]:
        """
        List available progress files with basic information.

        Returns:
            List of dictionaries with progress file information
        """
        results = []

        for file_path in self.progress_dir.glob("progress_*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extract basic information
                results.append(
                    {
                        "file_path": str(file_path),
                        "job_id": data.get("job_id", "unknown"),
                        "wahlperiode": data.get("wahlperiode", "unknown"),
                        "status": data.get("status", "unknown"),
                        "completed_count": len(data.get("completed_protocol_ids", [])),
                        "total_protocols": data.get("total_protocols", 0),
                        "last_update": data.get("last_update_time", "unknown"),
                    }
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error parsing progress file {file_path}: {e}")

        # Sort by last update time (newest first)
        results.sort(key=lambda x: x["last_update"], reverse=True)
        return results
