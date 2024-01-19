"""Test docker interacing to restic"""

import os
import shutil
from pyfakefs import fake_filesystem_unittest

from restictool.argument_parser import Arguments
from restictool.restic_tool import ResticTool
from restictool.settings import Settings

# pylint: disable=protected-access


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
  forget:
    - --keep-daily
    - 7
  prune:
    - --max-unused
    - '200M'
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
    path: /path
    options:
      - '--exclude="/localdir/my_tag/some_dir"'
  - name: my_home
    path: '~'
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
        self.default_cache_dir = os.path.join(self.default_cache_base, "restic")

        self.setUpPyfakefs()
        os.makedirs(self.default_configuration_dir)

        with open(self.default_configuration_file, "w", encoding="utf8") as file:
            file.write(self.config_yaml)

    def prepare_tool(self, args: list) -> Settings:
        """Prepare the settings from argv"""
        arguments = Arguments()
        arguments.parse(args)
        settings = arguments.to_settings()
        tool = ResticTool(settings)
        tool.setup()
        return tool

    def test_own_host(self):
        """Test docker network address determination"""
        tool = self.prepare_tool(["run"])
        tool._find_own_network()
        self.assertEqual(tool.own_ip_address, self.OWN_IP_ADDRESS)

    def test_create_cache_directory(self):
        """Test creation of cache directory"""
        if os.path.exists(self.default_cache_base):
            shutil.rmtree(self.default_cache_base)
        self.assertFalse(os.path.exists(self.default_cache_dir))
        tool = self.prepare_tool(["run"])
        tool._create_directories()
        self.assertTrue(os.path.exists(self.default_cache_dir))

    def test_create_restore_directory(self):
        """Test creation of cache directory"""
        restore_base = os.path.join(os.sep, "tmp", "r1")
        restore_dir = os.path.join(restore_base, "r2", "r3")
        if os.path.exists(restore_base):
            shutil.rmtree(restore_base)
        tool = self.prepare_tool(["restore", "-r", restore_dir])
        tool._create_directories()
        self.assertTrue(os.path.exists(restore_dir))

    def test_run_mount(self):
        """Test docker mounts for run"""
        tool = self.prepare_tool(["run"])
        mounts = tool._get_docker_mounts()
        self.assertEqual(
            mounts, {self.default_cache_dir: {"bind": "/cache", "mode": "rw"}}
        )

    def test_backup_mount_volume(self):
        """Test docker mounts for volume backup"""
        tool = self.prepare_tool(["backup"])
        mounts = tool._get_docker_mounts(volume="my_volume")
        self.assertEqual(
            mounts,
            {
                self.default_cache_dir: {"bind": "/cache", "mode": "rw"},
                "my_volume": {"bind": "/volume/my_volume", "mode": "rw"},
            },
        )

    def test_backup_mount_localdir(self):
        """Test docker mounts for localdir backup"""
        tool = self.prepare_tool(["backup"])
        mounts = tool._get_docker_mounts(localdir=("my_tag", "/path"))
        self.assertEqual(
            mounts,
            {
                self.default_cache_dir: {"bind": "/cache", "mode": "rw"},
                "/path": {"bind": "/localdir/my_tag", "mode": "rw"},
            },
        )

    def test_restore_mount(self):
        """Test docker mounts for restore"""
        tool = self.prepare_tool(["restore", "-r", "/tmp/restore/target"])
        mounts = tool._get_docker_mounts()
        self.assertEqual(
            mounts,
            {
                self.default_cache_dir: {"bind": "/cache", "mode": "rw"},
                "/tmp/restore/target": {"bind": "/target", "mode": "rw"},
            },
        )

    def test_backup_options_volume(self):
        """Test docker options for volume backup"""
        tool = self.prepare_tool(["backup", "-q"])
        options = tool._get_restic_arguments(volume="my_volume")
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "backup",
                "/volume/my_volume",
                "--insecure-tls",
                "--volume-opt",
                '--exclude="/volume/my_volume/some_dir"',
                "--exclude-caches",
                "--host",
                "myhost",
                "-q",
            ],
        )

    def test_backup_options_localdir(self):
        """Test docker options for volume backup"""
        tool = self.prepare_tool(["backup"])
        options = tool._get_restic_arguments(localdir_name="my_tag")
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "backup",
                "/localdir/my_tag",
                "--insecure-tls",
                "--localdir-opt1",
                "--localdir-opt2",
                '--exclude="/localdir/my_tag/some_dir"',
                "--host",
                "myhost",
            ],
        )

    def test_backup_options_forget(self):
        """Test docker options for forget"""
        tool = self.prepare_tool(["backup", "--my-arg1", "--my-arg2"])
        options = tool._get_restic_arguments(forget=True)
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "forget",
                "--insecure-tls",
                "--keep-daily",
                "7",
                "--host",
                "myhost",
                "--my-arg1",
                "--my-arg2",
            ],
        )

    def test_backup_options_prune(self):
        """Test docker options for prune"""
        tool = self.prepare_tool(["backup", "--my-arg1", "--my-arg2"])
        options = tool._get_restic_arguments(prune=True)
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "prune",
                "--insecure-tls",
                "--max-unused",
                "200M",
                "--my-arg1",
                "--my-arg2",
            ],
        )

    def test_restore_options(self):
        """Test docker options for restore"""
        tool = self.prepare_tool(
            ["restore", "-r", "/restore/to", "my_snapshot", "--my-arg1", "--my-arg2"]
        )
        options = tool._get_restic_arguments(forget=True)
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "restore",
                "my_snapshot",
                "--target",
                "/target",
                "--insecure-tls",
                "--my-arg1",
                "--my-arg2",
            ],
        )

    def test_run_options(self):
        """Test docker options for general run"""
        tool = self.prepare_tool(["run", "snapshots", "--host", "myhost"])
        options = tool._get_restic_arguments(forget=True)
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "--insecure-tls",
                "snapshots",
                "--host",
                "myhost",
            ],
        )
