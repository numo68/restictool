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
  forget:
    - --keep-daily
    - 7
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

    def test_run_mount(self):
        """Test docker mounts for run"""
        tool = ResticTool()
        tool.setup(["run"])
        mounts = tool.get_docker_mounts()
        self.assertEqual(
            mounts, {self.default_cache_dir: {"bind": "/cache", "mode": "rw"}}
        )

    def test_backup_mount_volume(self):
        """Test docker mounts for volume backup"""
        tool = ResticTool()
        tool.setup(["backup"])
        mounts = tool.get_docker_mounts(volume="my_volume")
        self.assertEqual(
            mounts,
            {
                self.default_cache_dir: {"bind": "/cache", "mode": "rw"},
                "my_volume": {"bind": "/volume/my_volume", "mode": "rw"},
            },
        )

    def test_backup_mount_localdir(self):
        """Test docker mounts for localdir backup"""
        tool = ResticTool()
        tool.setup(["backup"])
        mounts = tool.get_docker_mounts(localdir=("my_tag", "/path"))
        self.assertEqual(
            mounts,
            {
                self.default_cache_dir: {"bind": "/cache", "mode": "rw"},
                "/path": {"bind": "/localdir/my_tag", "mode": "rw"},
            },
        )

    def test_restore_mount(self):
        """Test docker mounts for restore"""
        tool = ResticTool()
        tool.setup(["restore", "-r", "/tmp/restore/target"])
        mounts = tool.get_docker_mounts()
        self.assertEqual(
            mounts,
            {
                self.default_cache_dir: {"bind": "/cache", "mode": "rw"},
                "/tmp/restore/target": {"bind": "/target", "mode": "rw"},
            },
        )

    def test_backup_options_volume(self):
        """Test docker options for volume backup"""
        tool = ResticTool()
        tool.setup(["-q", "backup", "-p"])
        options = tool.get_restic_arguments(volume="my_volume")
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "--quiet",
                "--host",
                "myhost",
                "--insecure-tls",
                "--volume-opt",
                "--exclude=\"/volume/my_volume/some_dir\"",
                "--exclude-caches",
                "backup",
                "/volume/my_volume",
            ]
        )

    def test_backup_options_localdir(self):
        """Test docker options for volume backup"""
        tool = ResticTool()
        tool.setup(["-q", "backup", "-p"])
        options = tool.get_restic_arguments(localdir="my_tag")
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "--quiet",
                "--host",
                "myhost",
                "--insecure-tls",
                "--localdir-opt1",
                "--localdir-opt2",
                "--exclude=\"/localdir/my_tag/some_dir\"",
                "backup",
                "/localdir/my_tag",
            ]
        )

    def test_backup_options_forget(self):
        """Test docker options for volume backup"""
        tool = ResticTool()
        tool.setup(["-q", "backup", "-p", "--my-arg1", "--my-arg2"])
        options = tool.get_restic_arguments(forget=True)
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "--quiet",
                "--host",
                "myhost",
                "--insecure-tls",
                "--keep-daily",
                "7",
                "--prune",
                "forget",
                "--my-arg1",
                "--my-arg2",
            ]
        )

    def test_restore_options(self):
        """Test docker options for restore"""
        tool = ResticTool()
        tool.setup(["restore", "-r", "/restore/to", "my_snapshot", "--my-arg1", "--my-arg2"])
        options = tool.get_restic_arguments(forget=True)
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "--insecure-tls",
                "--target",
                "/restore/to",
                "restore",
                "my_snapshot",
                "--my-arg1",
                "--my-arg2",
            ]
        )

    def test_run_options(self):
        """Test docker options for general run"""
        tool = ResticTool()
        tool.setup(["run", "snapshots", "--host", "myhost"])
        options = tool.get_restic_arguments(forget=True)
        self.assertEqual(
            options,
            [
                "--cache-dir",
                "/cache",
                "--insecure-tls",
                "snapshots",
                "--host",
                "myhost",
            ]
        )
