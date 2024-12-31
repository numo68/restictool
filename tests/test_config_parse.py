"""Test configuration parsing"""

import io
import os
import unittest
import platform
import pytest

from restictool.configuration_parser import Configuration


class TestConfigParser(unittest.TestCase):
    """Test argument parsing"""

    def setUp(self):
        self.config_yaml = """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
  host: myhost
  authentication:
    AWS_ACCESS_KEY_ID: "S3:SomeKeyId"
    AWS_SECRET_ACCESS_KEY: "someSecret"
  extra:
    RESTIC_PACK_SIZE: "64"
metrics:
  directory: "/tmp/foo"
  suffix: "bar"
options:
  common:
    - --insecure-tls
  forget:
    - --keep-daily
    - 7
    - --keep-weekly
    - 5
  volume:
    - --volume-opt
  localdir:
    - --localdir-opt1
    - --localdir-opt2
volumes:
  - name: my_volume
    options:
      - '--exclude="/volume/my_volume/some_dir"'
      - "--exclude-caches"
localdirs:
  - name: my_tag
    path: path
    options:
      - '--exclude="/localdir/my_tag/some_dir"'
"""
        self.config = Configuration()

    def test_load(self):
        """Test load with close"""
        config_stream = io.StringIO(self.config_yaml)
        config_stream.seek(0, io.SEEK_SET)

        self.config.load(config_stream)
        self.assertTrue(config_stream.closed)

    def test_load_keep_open(self):
        """Test load without close"""
        config_stream = io.StringIO(self.config_yaml)
        config_stream.seek(0, io.SEEK_SET)

        self.config.load(self.config_yaml, False)
        self.assertFalse(config_stream.closed)
        config_stream.close()

    def test_validate(self):
        """Test the validator"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
"""
        )
        with pytest.raises(ValueError, match="repository"):
            self.config.load("foo:\n")

        with pytest.raises(ValueError, match="repository"):
            self.config.load("repository:\n")

        with pytest.raises(ValueError, match="location"):
            self.config.load("repository:\n  location:\n")

    def test_env_vars(self):
        """Test environment variables parsing"""
        self.config.load(self.config_yaml)
        self.assertEqual(
            self.config.environment_vars["AWS_ACCESS_KEY_ID"], "S3:SomeKeyId"
        )
        self.assertEqual(
            self.config.environment_vars["AWS_SECRET_ACCESS_KEY"], "someSecret"
        )
        self.assertEqual(self.config.environment_vars["RESTIC_PACK_SIZE"], "64")
        self.assertEqual(
            self.config.environment_vars["RESTIC_REPOSITORY"],
            "s3:https://somewhere:8010/restic-backups",
        )
        self.assertEqual(
            self.config.environment_vars["RESTIC_PASSWORD"], "MySecretPassword"
        )

    def test_forbidden_env_vars(self):
        """Test environment variables parsing"""
        with pytest.raises(ValueError, match=r"RESTIC_REPOSITORY.*forbidden"):
            self.config.load(
                """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
  authentication:
    RESTIC_REPOSITORY: somename
"""
            )

    def test_hostname(self):
        """Test hostname setting parsing"""
        self.config.load(self.config_yaml)
        self.assertEqual(self.config.hostname, "myhost")

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
"""
        )
        self.assertEqual(self.config.hostname, platform.node().lower())

    def test_options_common(self):
        """Test parsing of the common options"""
        self.config.load(self.config_yaml)
        self.assertEqual(self.config.get_options(), ["--insecure-tls"])

    def test_options_forget(self):
        """Test parsing of the forget options"""
        self.config.load(self.config_yaml)
        self.assertEqual(
            self.config.get_options(forget=True),
            ["--insecure-tls", "--keep-daily", "7", "--keep-weekly", "5"],
        )

    def test_options_forget_default(self):
        """Test parsing of the forget default options"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
options:
  forget:
    - DEFAULT
    - --add-opt
"""
        )
        self.assertEqual(
            self.config.get_options(forget=True),
            [
                "--keep-daily",
                "7",
                "--keep-weekly",
                "5",
                "--keep-monthly",
                "12",
                "--add-opt",
            ],
        )

    def test_options_prune(self):
        """Test parsing of the prune options"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
options:
  prune:
"""
        )
        self.assertEqual(
            self.config.get_options(prune=True),
            [
            ],
        )

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
options:
  prune:
    - foo
    - bar
"""
        )
        self.assertEqual(
            self.config.get_options(prune=True),
            [
                "foo",
                "bar",
            ],
        )

    def test_options_volume(self):
        """Test parsing of the volume options"""
        self.config.load(self.config_yaml)
        self.assertEqual(
            self.config.get_options(volume="my_volume"),
            [
                "--insecure-tls",
                "--volume-opt",
                '--exclude="/volume/my_volume/some_dir"',
                "--exclude-caches",
            ],
        )
        self.assertEqual(
            self.config.get_options(volume="another_volume"),
            [
                "--insecure-tls",
                "--volume-opt",
            ],
        )

    def test_options_volume_wildcard(self):
        """Test parsing of the volume wildcard matching"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
volumes:
  - name: '*'
    options:
      - "--exclude-caches"
"""
        )
        self.assertEqual(
            self.config.get_options(volume="my_volume"),
            [
                "--exclude-caches",
            ],
        )

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
volumes:
  - name: '*'
    options:
      - "--opt-wildcard"
  - name: 'my_volume'
    options:
      - "--opt-specific"
"""
        )
        self.assertEqual(
            self.config.get_options(volume="my_volume"),
            [
                "--opt-specific",
            ],
        )
        self.assertEqual(
            self.config.get_options(volume="other_volume"),
            [
                "--opt-wildcard",
            ],
        )

    def test_options_localdir(self):
        """Test parsing of the localdir options"""
        self.config.load(self.config_yaml)
        self.assertEqual(
            self.config.get_options(localdir="my_tag"),
            [
                "--insecure-tls",
                "--localdir-opt1",
                "--localdir-opt2",
                '--exclude="/localdir/my_tag/some_dir"',
            ],
        )
        self.assertEqual(
            self.config.get_options(localdir="another_tag"),
            [
                "--insecure-tls",
                "--localdir-opt1",
                "--localdir-opt2",
            ],
        )

    def test_volumes_to_backup(self):
        """Test getting the list of volumes to backup"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
"""
        )
        self.assertEqual(
            self.config.volumes_to_backup,
            [],
        )
        self.assertFalse(self.config.backup_all_volumes)

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
volumes:
    - name: vol1
    - name: vol2
"""
        )
        self.assertEqual(self.config.volumes_to_backup, ["vol1", "vol2"])
        self.assertFalse(self.config.backup_all_volumes)

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
volumes:
    - name: vol1
    - name: '*'
"""
        )
        self.assertEqual(self.config.volumes_to_backup, [])
        self.assertTrue(self.config.backup_all_volumes)

    def test_is_volume_backed(self):
        """Test getting the list of volumes to backup"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
volumes:
    - name: vol1
    - name: vol2
"""
        )
        self.assertTrue(self.config.is_volume_backed_up("vol2"))
        self.assertFalse(self.config.is_volume_backed_up("volx"))

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
volumes:
    - name: '*'
    - name: vol2
"""
        )
        self.assertTrue(self.config.is_volume_backed_up("volx"))
        self.assertTrue(self.config.is_volume_backed_up("vol2"))
        self.assertTrue(self.config.is_volume_backed_up("0123456789abcdef"))
        self.assertFalse(
            self.config.is_volume_backed_up(
                "0123456789abcdef0123456789abcdef0123456789abcdef"
            )
        )
        self.assertTrue(
            self.config.is_volume_backed_up(
                "0123456789abcdef0123456789abcdef0123456789abcdefxxx"
            )
        )

    def test_volume_exclude(self):
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
volumes:
    - name: '*'
      exclude:
        - vol2
        - vol3
"""
        )
        self.assertEqual(self.config.volumes_to_exclude, ["vol2", "vol3"])
        self.assertTrue(self.config.is_volume_backed_up("volx"))
        self.assertFalse(self.config.is_volume_backed_up("vol2"))
        self.assertFalse(self.config.is_volume_backed_up("vol3"))
        self.assertFalse(
            self.config.is_volume_backed_up(
                "0123456789abcdef0123456789abcdef0123456789abcdef"
            )
        )

    def test_volume_exclude_wildcard_only(self):
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
volumes:
    - name: vol2
      exclude:
        - vol2
"""
        )
        self.assertTrue(self.config.is_volume_backed_up("vol2"))
        self.assertEqual(self.config.volumes_to_exclude, [])

    def test_localdirs_to_backup(self):
        """Test getting the list of local directories to backup"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
"""
        )
        self.assertEqual(
            self.config.localdirs_to_backup,
            [],
        )

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
localdirs:
    - name: dir1
      path: /path1
    - name: dir2
      path: /path2
"""
        )
        self.assertEqual(
            self.config.localdirs_to_backup, [("dir1", "/path1"), ("dir2", "/path2")]
        )

    def test_is_forget_specified(self):
        """Test whether to run the forget pass"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
"""
        )
        self.assertFalse(self.config.is_forget_specified())

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
options:
  common:
    - --foo
"""
        )
        self.assertFalse(self.config.is_forget_specified())

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
options:
  forget:
    - --foo
"""
        )
        self.assertTrue(self.config.is_forget_specified())

    def test_is_prune_specified(self):
        """Test whether to run the prune pass"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
"""
        )
        self.assertFalse(self.config.is_prune_specified())

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
options:
  common:
    - --foo
"""
        )
        self.assertFalse(self.config.is_prune_specified())

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
options:
  prune:
"""
        )
        self.assertTrue(self.config.is_prune_specified())
        self.assertEqual(self.config.configuration["options"]["prune"], [])

        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
options:
  prune:
    - foo
    - bar
"""
        )
        self.assertTrue(self.config.is_prune_specified())
        self.assertEqual(self.config.configuration["options"]["prune"], ["foo", "bar"])

    def test_localdirs_tilde_expansion(self):
        """Test getting the list of local directories to backup"""
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
localdirs:
  - name: tag1
    path: foo
  - name: tag2
    path: ~/foo
"""
        )
        self.assertEqual(
            self.config.localdirs_to_backup,
            [("tag1", "foo"), ("tag2", os.path.join(os.environ["HOME"], "foo"))],
        )

    def test_metrics(self):
        self.config.load(self.config_yaml)
        self.assertEqual(self.config.metrics_path, "/tmp/foo/restictool-bar.prom")

    def test_metrics_no_suffix(self):
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
metrics:
  directory: "/tmp/foo"
"""
        )
        self.assertEqual(self.config.metrics_path, "/tmp/foo/restictool.prom")

    def test_no_metrics(self):
        self.config.load(
            """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
"""
        )
        self.assertIsNone(self.config.metrics_path)