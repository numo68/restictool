"""Test docker interacing to restic"""

import os
import shutil
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
        self.default_cache_base = os.path.join(os.environ["HOME"], ".cache")
        self.default_cache_dir = os.path.join(self.default_cache_base, ".restic")

        self.setUpPyfakefs()
        os.makedirs(self.default_configuration_dir)

        with open(self.default_configuration_file, "w", encoding="utf8") as file:
            file.write(self.config_yaml)

    def test_own_host(self):
        """Test docker network address determination"""
        tool = ResticTool()
        tool.setup(["run"])
        tool.find_own_network()
        self.assertEqual(tool.own_ip_address, self.OWN_IP_ADDRESS)

    def test_create_cache_directory(self):
        """Test creation of cache directory"""
        if os.path.exists(self.default_cache_base):
            shutil.rmtree(self.default_cache_base)
        self.assertFalse(os.path.exists(self.default_cache_dir))
        tool = ResticTool()
        tool.setup(["run"])
        tool.create_directories()
        self.assertTrue(os.path.exists(self.default_cache_dir))

    def test_create_restore_directory(self):
        """Test creation of cache directory"""
        restore_base = os.path.join(os.sep, "tmp", "r1")
        restore_dir = os.path.join(restore_base, "r2", "r3")
        if os.path.exists(restore_base):
            shutil.rmtree(restore_base)
        tool = ResticTool()
        tool.setup(["restore", "-r", restore_dir])
        tool.create_directories()
        self.assertTrue(os.path.exists(restore_dir))
