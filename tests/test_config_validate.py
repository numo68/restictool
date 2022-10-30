"""Test configuration validation"""

import unittest
import pytest
import yaml

from schema import SchemaError
from restictool.configuration_validator import validate


class TestArgumentParser(unittest.TestCase):
    """Test configuration validation"""

    def test_validate_complete(self):
        """Validate a valid config"""
        config = validate(
            yaml.safe_load(
                """
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
            )
        )

        self.assertEqual(
            config["repository"]["name"],
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
            config["repository"]["authentication"]["AWS_ACCESS_KEY_ID"],
            "S3:SomeKeyId",
        )
        self.assertEqual(
            config["options"]["common"][0],
            "--insecure-tls",
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
    name: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
"""
            )
        )

    with pytest.raises(SchemaError, match="spurious"):
        validate(
            yaml.safe_load(
                """
repository:
    name: "s3:https://somewhere:8010/restic-backups"
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

        with pytest.raises(SchemaError, match="name"):
            validate(yaml.safe_load("repository:\n  name:\n"))

        with pytest.raises(SchemaError, match="name"):
            validate(yaml.safe_load("repository:\n  name: [1,2]\n"))

        with pytest.raises(SchemaError, match="name"):
            validate(yaml.safe_load('repository:\n  name: ""\n'))

        with pytest.raises(SchemaError, match="password"):
            validate(yaml.safe_load("repository:\n  name: foo\n"))

        with pytest.raises(SchemaError, match="password"):
            validate(yaml.safe_load("repository:\n  name: foo\n  password: ''"))

        with pytest.raises(SchemaError):
            validate(yaml.safe_load('repository:\n  name: "aa"\n'))

        with pytest.raises(SchemaError, match="host"):
            validate(
                yaml.safe_load("repository:\n  name: foo\n  password: pass\n  host:")
            )

        with pytest.raises(SchemaError, match="host"):
            validate(
                yaml.safe_load("repository:\n  name: foo\n  password: pass\n  host: ''")
            )

    def test_validate_options(self):
        """Validate repository part more thoroughly"""

        with pytest.raises(SchemaError, match="options"):
            validate(
                yaml.safe_load(
                    """
repository:
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
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
    name: "s3:https://somewhere:8010/restic-backups"
    password: "MySecretPassword"
localdirs:
    - name: tag
      path: mypath
      options:
"""
                )
            )
