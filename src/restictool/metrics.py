"""
Transform the restic metrics from the json snapshot output to prometheus metrics

Only works for restic >= 0.17.0
"""

import os
from dateutil import parser
from prometheus_client import Gauge, CollectorRegistry, write_to_textfile

from .configuration_parser import Configuration


class Metrics:
    """
    Transforms the snapshot summary to the prometheus text format
    """

    def __init__(self, configuration: Configuration):
        """Initialize metrics collector

        Args:
            configuration (Configuration): Restictool configuration
        """
        self.configuration = configuration
        self.registry = CollectorRegistry()
        labels = ["hostname", "repository", "path"]
        self.backup_time = Gauge(
            "restictool_backup_timestamp_seconds",
            "Time the backup was started.",
            labels,
            registry=self.registry,
        )
        self.backup_duration = Gauge(
            "restictool_backup_duration_seconds",
            "Duration of the backup.",
            labels,
            registry=self.registry,
        )
        self.backup_files = Gauge(
            "restictool_backup_files",
            "Number of files in the snapshot.",
            labels,
            registry=self.registry,
        )
        self.backup_size = Gauge(
            "restictool_backup_size_bytes",
            "Total size of the files in the snapshot.",
            labels,
            registry=self.registry,
        )

    @staticmethod
    def time_string_to_time_stamp(time: str) -> float:
        """Convert the ISO date to seconds from epoch

        Unfortunately the dateutil.fromisoformat() cannot handle nanoseconds
        nor the 'Z' suffix until 3.11, while the Debian bookworm has 3.10.

        Dateutil is able to do that.

        Returns:
            int: Time in seconds from epoch
        """
        # return int(datetime.fromisoformat(time.split('.')[0].split('Z')[0] + "+00:00").timestamp())
        return parser.isoparse(time).timestamp()

    def set_snapshot(self, snapshot: dict):
        """Set the metrics from a snapshot JSON

        Args:
            snapshot (dict): A snapshot item from the restic snapshots --json command
        """

        hostname = snapshot["hostname"]
        repository = self.configuration.configuration["repository"]["location"]
        path = snapshot["paths"][0]

        self.backup_time.labels(hostname, repository, path).set(
            Metrics.time_string_to_time_stamp(snapshot["time"])
        )

        try:
            summary = snapshot["summary"]  # Raises KeyError if not found
            duration = round(
                self.time_string_to_time_stamp(summary["backup_end"])
                - self.time_string_to_time_stamp(summary["backup_start"]),
                2,
            )
            files = int(summary["total_files_processed"])
            size = int(summary["total_bytes_processed"])
            self.backup_duration.labels(hostname, repository, path).set(duration)
            self.backup_files.labels(hostname, repository, path).set(files)
            self.backup_size.labels(hostname, repository, path).set(size)
        except KeyError:
            pass

    def set_snapshots(self, snapshots: list):
        """Set the metrics from a list of snapshot

        Args:
            snapshots (list): _description_
        """
        for snapshot in snapshots:
            self.set_snapshot(snapshot)

    def write_to_file(self):
        """Atomically write the metrics to the file

        Args:
            configuration (Configuration): Restictool configuration
            snapshots (list): a list of snapshots
            path (str): path of the destination file
        """

        write_to_textfile(self.configuration.metrics_path, self.registry)
