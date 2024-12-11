"""
Transform the restic metrics from the json snapshot output to prometheus metrics

Only works for restic >= 0.17.0
"""

import os
from datetime import datetime
from dateutil import parser
from .configuration_parser import Configuration


class Metrics:
    """
    Transforms the snapshot summary to the prometheus text format
    """

    def __init__(self, configuration: Configuration):
        """_summary_

        Args:
            configuration (Configuration): Restictool configuration
        """
        self.configuration = configuration
        self.clear()

    def clear(self):
        self.repository = None
        self.hostname = None
        self.path = None
        self.timestamp = None
        self.duration = None
        self.files = None
        self.size = None

    @staticmethod
    def header() -> str:
        """Returns the header of the metrics text format"""

        return """# HELP restictool_backup_timestamp_seconds Time the backup was started.
# TYPE restictool_backup_timestamp_seconds counter

# HELP restictool_backup_duration_seconds Duration of the backup.
# TYPE restictool_backup_duration_seconds gauge

# HELP restictool_backup_files Number of files in the snapshot.
# TYPE restictool_backup_files gauge

# HELP restictool_backup_size_bytes Total size of the files in the snapshot.
# TYPE restictool_backup_size_bytes gauge

"""

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

    @staticmethod
    def escape_label_value(s: str) -> str:
        """Escape label value

        Args:
            s (str): raw value

        Returns:
            str: Value escaped according to prometheus text exposition rules
        """
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", r"\n")


    def set(self, snapshot: dict):
        """Set the metrics from a snapshot JSON

        Args:
            snapshot (dict): A snapshot item from the restic snapshots --json command
        """

        self.clear()

        self.repository = self.configuration.configuration["repository"]["location"]

        self.hostname = snapshot["hostname"]
        self.path = snapshot["paths"][0]
        self.timestamp = int(self.time_string_to_time_stamp(snapshot["time"]))

        try:
            summary = snapshot["summary"]  # Raises KeyError if not found
            self.duration = round(
                self.time_string_to_time_stamp(summary["backup_end"])
                - self.time_string_to_time_stamp(summary["backup_start"]),
                1,
            )
            self.files = int(summary["total_files_processed"])
            self.size = int(summary["total_bytes_processed"])
        except KeyError:
            pass

    def labels(self) -> str:
        """Generate the metric labels

        Returns:
            str: Labels of the metric
        """
        return f'{{hostname="{self.escape_label_value(self.hostname)}",repository="{self.escape_label_value(self.repository)}",path="{self.escape_label_value(self.path)}"}}'

    def metric_lines(self) -> str:
        """Returns the metrics for the snapshot

        Returns:
            str: A set of the lines in the prometheus text format
        """

        ret = f"restictool_backup_timestamp_seconds{self.labels()} {self.timestamp}\n"
        if self.duration and self.files and self.size:
            ret += (
                f"restictool_backup_duration_seconds{self.labels()} {self.duration}\n"
                + f"restictool_backup_files{self.labels()} {self.files}\n"
                + f"restictool_backup_size_bytes{self.labels()} {self.size}\n"
            )

        ret += "\n"

        return ret


    @classmethod
    def write_to_file(cls, configuration: Configuration, snapshots: list):
        """Atomically write the metrics to the file

        Args:
            configuration (Configuration): Restictool configuration
            snapshots (list): a list of snapshots
            path (str): path of the destination file
        """

        out_str = Metrics.header()

        for snapshot in snapshots:
            metric = cls(configuration)
            metric.set(snapshot)
            out_str += metric.metric_lines()

        tmp_file_path = configuration.metrics_path + ".new"

        with open(tmp_file_path, "w") as f:
            f.write(out_str)
        
        os.rename(tmp_file_path, configuration.metrics_path)
