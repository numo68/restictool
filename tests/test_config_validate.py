"""Test configuration validation"""

import unittest
import pytest
import yaml

from schema import SchemaError
from restictool.configuration_validator import validate


class TestConfigValidator(unittest.TestCase):
    """Test configuration validation"""

    def test_validate_complete(self):
        """Validate a valid config"""
        config = validate(
            yaml.safe_load(
                """
repository:
  location: "s3:https://somewhere:8010/restic-backups"
  password: "MySecretPassword"
  host: myhost
  network_from: myvpncontainer
  authentication:
    AWS_ACCESS_KEY_ID: "S3:SomeKeyId"
    AWS_SECRET_ACCESS_KEY: "someSecret"
  extra:
    RESTIC_PACK_SIZE: "64"
metrics:
  directory: "/foo"
  suffix: "s3"
options:
  common:
    - --insecure-tls
  forget:
    - --keep-daily
    - 7
    - --keep-weekly
    - 5
    - --keep-monthly
    - 12
  prune:
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
  - name: '*'
    exclude:
      - this_one
      - that_one
localdirs:
  - name: my_tag
    path: path
    options:
      - '--exclude="/localdir/my_tag/some_dir"'
"""
            )
        )

        self.assertEqual(
            config["repository"]["location"],
            "s3:https://somewhere:8010/restic-backups",
        )
        self.assertEqual(
            config["repository"]["password"],
            "MySecretPassword",
        )
        self.assertEqual(
            config["repository"]["host"],
            "myhost",
        )
        self.assertEqual(
            config["repository"]["network_from"],
            "myvpncontainer",
        )
        self.assertEqual(
            config["repository"]["authentication"]["AWS_ACCESS_KEY_ID"],
            "S3:SomeKeyId",
        )
        self.assertEqual(
            config["metrics"]["directory"],
            "/foo",
        )
        self.assertEqual(
            config["metrics"]["suffix"],
            "s3",
        )
        self.assertEqual(
            config["options"]["common"][0],
            "--insecure-tls",
        )
        self.assertEqual(
            config["options"]["forget"][0],
            "--keep-daily",
        )
        self.assertEqual(
            config["options"]["prune"],
            None,
        )
        self.assertEqual(
            config["options"]["volume"][0],
            "--volume-opt",
        )
        self.assertEqual(
            config["options"]["localdir"][1],
            "--localdir-opt2",
        )
        self.assertEqual(
            config["volumes"][0]["name"],
            "my_volume",
        )
        self.assertEqual(
            config["volumes"][0]["options"][0],
            '--exclude="/volume/my_volume/some_dir"',
        )
        self.assertEqual(
            config["volumes"][0]["options"][1],
            "--exclude-caches",
        )
        self.assertEqual(
            config["localdirs"][0]["name"],
            "my_tag",
        )
        self.assertEqual(
            config["localdirs"][0]["path"],
            "path",
        )
        self.assertEqual(
            config["localdirs"][0]["options"][0],
            '--exclude="/localdir/my_tag/some_dir"',
        )

    def test_validate_repository(self):
        """Validate repository part more thoroughly"""
        validate(
            yaml.safe_load(
                """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
"""
            )
        )

        with pytest.raises(SchemaError, match="spurious"):
            validate(
                yaml.safe_load(
                    """
    repository:
        location: "s3:https://somewhere:8010/restic-backups"
        password: "MySecretPassword"
    spurious:
        - ''
    """
                )
            )

        with pytest.raises(SchemaError, match="repository"):
            validate(yaml.safe_load("foo:\n"))

        with pytest.raises(SchemaError, match="repository"):
            validate(yaml.safe_load("repository:\n"))

        with pytest.raises(SchemaError, match="location"):
            validate(yaml.safe_load("repository:\n  location:\n"))

        with pytest.raises(SchemaError, match="location"):
            validate(yaml.safe_load("repository:\n  location: [1,2]\n"))

        with pytest.raises(SchemaError, match="location"):
            validate(yaml.safe_load('repository:\n  location: ""\n'))

        with pytest.raises(SchemaError, match="password"):
            validate(yaml.safe_load("repository:\n  location: foo\n"))

        with pytest.raises(SchemaError, match="password"):
            validate(yaml.safe_load("repository:\n  location: foo\n  password: ''"))

        with pytest.raises(SchemaError):
            validate(yaml.safe_load('repository:\n  location: "aa"\n'))

        with pytest.raises(SchemaError, match="host"):
            validate(
                yaml.safe_load(
                    "repository:\n  location: foo\n  password: pass\n  host:"
                )
            )

        with pytest.raises(SchemaError, match="host"):
            validate(
                yaml.safe_load(
                    "repository:\n  location: foo\n  password: pass\n  host: ''"
                )
            )

    def test_validate_options(self):
        """Validate repository part more thoroughly"""

        with pytest.raises(SchemaError, match="options"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
options:
"""
                )
            )

        with pytest.raises(SchemaError, match="common"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
options:
    common:
"""
                )
            )

        with pytest.raises(SchemaError, match="common"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
options:
    common:
        - ''
"""
                )
            )

        with pytest.raises(SchemaError, match="volume"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
options:
    volume:
        - ''
"""
                )
            )

        with pytest.raises(SchemaError, match="localdir"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
options:
    localdir:
        - ''
"""
                )
            )

    def test_validate_volumes(self):
        """Validate volumes part more thoroughly"""

        with pytest.raises(SchemaError, match="volumes"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
volumes:
"""
                )
            )

        with pytest.raises(SchemaError, match="volumes"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
volumes:
    - foo
"""
                )
            )

        with pytest.raises(SchemaError, match="volumes"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
volumes:
    - name: ''
"""
                )
            )

        validate(
            yaml.safe_load(
                """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
volumes:
    - name: '*'
"""
            )
        )

        with pytest.raises(SchemaError, match="volumes"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
volumes:
    - name: vol
      options:
"""
                )
            )

        with pytest.raises(SchemaError, match="path"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
volumes:
    - name: vol
      path:
"""
                )
            )

        with pytest.raises(SchemaError, match="name"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
volumes:
    - options:
        - opt1
"""
                )
            )

    def test_validate_localdirs(self):
        """Validate localdirs part more thoroughly"""

        with pytest.raises(SchemaError, match="localdirs"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
localdirs:
"""
                )
            )

        with pytest.raises(SchemaError, match="localdirs"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
localdirs:
    - foo
"""
                )
            )

        with pytest.raises(SchemaError, match="localdirs"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
localdirs:
    - name: ''
      path: path
"""
                )
            )

        with pytest.raises(SchemaError, match="localdirs"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
localdirs:
    - name: tag
      path: ''
"""
                )
            )

        validate(
            yaml.safe_load(
                """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
localdirs:
    - name: tag
      path: mypath
"""
            )
        )

        with pytest.raises(SchemaError, match="localdirs"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
localdirs:
    - name: tag
      path: mypath
      options:
"""
                )
            )

    def test_validate_metrics(self):
        """Validate metrics part more thoroughly"""

        with pytest.raises(SchemaError, match="metrics"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
metrics:
"""
                )
            )

        with pytest.raises(SchemaError, match="metrics"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
metrics:
    suffix: "s3"
"""
                )
            )

        self.assertTrue(
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
metrics:
    directory: "/foo"
"""
                )
            )
        )

        with pytest.raises(SchemaError, match="metrics"):
            validate(
                yaml.safe_load(
                    """
repository:
    location: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
metrics:
    directory: 1
"""
                )
            )
