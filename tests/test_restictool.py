"""Test docker interacing to restic"""

import io
import os
import unittest
import pytest
from pyfakefs import fake_filesystem_unittest

from restictool.restictool import ResticTool


class TestResticTool(fake_filesystem_unittest.TestCase):
    """Test the tool helper methods"""

    OWN_IP_ADDRESS = "172.17.0.1"

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
        self.default_configuration_dir = os.path.join(
            os.environ["HOME"],
            ".config",
            "restictool",
        )
        self.default_configuration_file = os.path.join(
            self.default_configuration_dir, "restictool.yml"
        )
        self.default_cache_dir = os.path.join(os.environ["HOME"], ".cache", ".restic")

        self.setUpPyfakefs()
        os.makedirs(self.default_configuration_dir)

        with open(self.default_configuration_file, "w", encoding="utf8") as file:
            file.write(self.config_yaml)

    def test_own_host(self):
        tool = ResticTool()
        tool.setup(["run"])
        self.assertEqual(tool.own_ip_address, self.OWN_IP_ADDRESS)
