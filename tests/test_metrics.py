"""Test configuration parsing"""

import io
import unittest
import json
import os
from pyfakefs import fake_filesystem_unittest

from restictool.configuration_parser import Configuration
from restictool.metrics import Metrics


class TestMetrics(fake_filesystem_unittest.TestCase):
    """Test argument parsing"""

    def setUp(self):
        self.config_yaml = """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  host: myhost
  password: "MySecretPassword"
metrics:
  directory: "/var/local/lib/metrics"
"""
        self.config = Configuration()
        config_stream = io.StringIO(self.config_yaml)
        config_stream.seek(0, io.SEEK_SET)

        self.config.load(config_stream)
        self.snapshots = json.loads(
            """
[
  {
    "time": "2024-12-10T12:11:40.914326222Z",
    "tree": "fc8127bd1dc17099816993dd34c997b1c9b69120a2c83277f135bf56af58addd",
    "paths": [
      "/volume/vs\\"co\\nde"
    ],
    "hostname": "mbair",
    "username": "root",
    "program_version": "restic 0.16.3",
    "id": "5b854a961f398fc11a25fb94c66ee64fbc60b74b80c528929901e2abb959025f",
    "short_id": "5b854a96"
  },
  {
    "time": "2024-12-10T12:12:48.263973669Z",
    "parent": "5b854a961f398fc11a25fb94c66ee64fbc60b74b80c528929901e2abb959025f",
    "tree": "9b1c8d584374df0e769ab025b7ff1ba6e074b480ded05aa16ca79256ed3d7d53",
    "paths": [
      "/volume/vscode"
    ],
    "hostname": "mbair",
    "username": "root",
    "program_version": "restic 0.17.3",
    "summary": {
      "backup_start": "2024-12-10T12:12:48.263973669Z",
      "backup_end": "2024-12-10T12:12:49.419041586Z",
      "files_new": 0,
      "files_changed": 0,
      "files_unmodified": 1131,
      "dirs_new": 0,
      "dirs_changed": 1,
      "dirs_unmodified": 412,
      "data_blobs": 0,
      "tree_blobs": 1,
      "data_added": 352,
      "data_added_packed": 291,
      "total_files_processed": 1131,
      "total_bytes_processed": 369787002
    },
    "id": "e61d0293e60dc5b97b7c982c815e180d733a84405247a48dd1ed5d5bb38753a3",
    "short_id": "e61d0293"
  }
]
"""
        )

        self.setUpPyfakefs()
        os.makedirs(self.config.configuration["metrics"]["directory"])

    def test_time_parse(self):
        self.assertAlmostEqual(
            Metrics.time_string_to_time_stamp("2024-12-10T19:43:56.123456789Z"),
            1733859836.123456,
            places=6,
        )
        self.assertAlmostEqual(
            Metrics.time_string_to_time_stamp("2024-12-10T19:43:56Z"), 1733859836.0
        )

    def test_file_write(self):
        self.assertTrue(self.config.metrics_dir_exists())

        metrics = Metrics(self.config)
        metrics.set_snapshots(self.snapshots)

        metrics.write_to_file()

        with open(self.config.metrics_path, "r") as f:
            lines = f.read().splitlines()

        self.assertEqual(len(lines), 13)

        self.assertEqual(
            lines[0],
            '# HELP restictool_backup_timestamp_seconds Time the backup was started.',
        )
        self.assertEqual(
            lines[1],
            '# TYPE restictool_backup_timestamp_seconds gauge',
        )

        self.assertEqual(
            lines[2],
            'restictool_backup_timestamp_seconds{hostname="mbair",path="/volume/vs\\"co\\nde",repository="s3:https://somewhere:8010/restic-backups"} 1.733832700914326e+09',
        )

        self.assertEqual(
            lines[3],
            'restictool_backup_timestamp_seconds{hostname="mbair",path="/volume/vscode",repository="s3:https://somewhere:8010/restic-backups"} 1.733832768263973e+09',
        )
        self.assertEqual(
            lines[6],
            'restictool_backup_duration_seconds{hostname="mbair",path="/volume/vscode",repository="s3:https://somewhere:8010/restic-backups"} 1.16',
        )
        self.assertEqual(
            lines[9],
            'restictool_backup_files{hostname="mbair",path="/volume/vscode",repository="s3:https://somewhere:8010/restic-backups"} 1131.0',
        )
        self.assertEqual(
            lines[12],
            'restictool_backup_size_bytes{hostname="mbair",path="/volume/vscode",repository="s3:https://somewhere:8010/restic-backups"} 3.69787002e+08',
        )
