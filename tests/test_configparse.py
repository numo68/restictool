"""Test argument parsing"""

import io
import pytest
import unittest

from restictool.configuration_parser import Configuration


class TestArgumentParser(unittest.TestCase):
    """Test argument parsing"""

    def setUp(self):
        self.config_yaml = """
repository:
  name: "s3:https://somewhere:8010/restic-backups"
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

        self.assertEqual(
            self.config.configuration["repository"]["name"],
            "s3:https://somewhere:8010/restic-backups",
        )
        self.assertEqual(
            self.config.configuration["repository"]["password"],
            "MySecretPassword",
        )
        self.assertEqual(
            self.config.configuration["repository"]["host"],
            "myhost",
        )
        self.assertEqual(
            self.config.configuration["repository"]["authentication"][
                "AWS_ACCESS_KEY_ID"
            ],
            "S3:SomeKeyId",
        )
        self.assertEqual(
            self.config.configuration["options"]["common"][0],
            "--insecure-tls",
        )
        self.assertEqual(
            self.config.configuration["options"]["volume"][0],
            "--volume-opt",
        )
        self.assertEqual(
            self.config.configuration["options"]["localdir"][1],
            "--localdir-opt2",
        )
        self.assertEqual(
            self.config.configuration["volumes"][0]["name"],
            "my_volume",
        )
        self.assertEqual(
            self.config.configuration["volumes"][0]["options"][0],
            '--exclude="/volume/my_volume/some_dir"',
        )
        self.assertEqual(
            self.config.configuration["volumes"][0]["options"][1],
            "--exclude-caches",
        )
        self.assertEqual(
            self.config.configuration["localdirs"][0]["name"],
            "my_tag",
        )
        self.assertEqual(
            self.config.configuration["localdirs"][0]["path"],
            "path",
        )
        self.assertEqual(
            self.config.configuration["localdirs"][0]["options"][0],
            '--exclude="/localdir/my_tag/some_dir"',
        )

    def test_load_keep_open(self):
        """Test load without close"""
        config_stream = io.StringIO(self.config_yaml)
        config_stream.seek(0, io.SEEK_SET)

        self.config.load(self.config_yaml, False)
        self.assertFalse(config_stream.closed)
        config_stream.close()

    def test_validate(self):
        self.config.load("""
repository:
  name: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
""")
        with pytest.raises(SystemExit, match="'repository' entry is missing"):
            self.config.load("foo:\n")

        with pytest.raises(SystemExit, match="'repository' entry is missing"):
            self.config.load("repository:\n")

        with pytest.raises(SystemExit, match="'repository.name' entry is missing"):
            self.config.load("repository:\n  name:\n")
        with pytest.raises(SystemExit, match="'repository.name' entry is missing"):
            self.config.load("repository:\n  name: [1,2]\n")
        with pytest.raises(SystemExit, match="'repository.name' entry is missing"):
            self.config.load("repository:\n  name: \"\"\n")
        with pytest.raises(SystemExit, match="'repository.password' entry is missing"):
            self.config.load("repository:\n  name: foo\n")
        with pytest.raises(SystemExit, match="'repository.password' entry is missing"):
            self.config.load("repository:\n  name: foo\n  password: ''")
