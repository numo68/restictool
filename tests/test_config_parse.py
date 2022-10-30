"""Test configuration parsing"""

import io
import unittest
import pytest

from restictool.configuration_parser import Configuration


class TestArgumentParser(unittest.TestCase):
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
options:
  common:
    - --insecure-tls
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
