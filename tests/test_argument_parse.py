"""Test argument parsing"""

import os
import pytest
from pyfakefs import fake_filesystem_unittest
from restictool.argument_parser import Arguments


class TestArgumentParser(fake_filesystem_unittest.TestCase):
    """Test argument parsing"""

    def setUp(self):
        self.default_configuration_dir = os.path.join(
            os.environ["HOME"],
            ".config",
            "restictool",
        )
        self.default_configuration_file = os.path.join(
            self.default_configuration_dir, "restictool.yml"
        )
        self.default_cache_dir = os.path.join(os.environ["HOME"], ".cache", "restic")
        self.default_image = "restic/restic"

        self.parser = Arguments()

        self.setUpPyfakefs()
        os.makedirs(self.default_configuration_dir)

        with open(self.default_configuration_file, "w", encoding="utf8") as file:
            file.write("# Comment")

    def test_class_defaults(self):
        """Test default parameters"""
        self.assertEqual(
            Arguments.DEFAULT_CONFIGURATION_FILE, self.default_configuration_file
        )
        self.assertEqual(Arguments.DEFAULT_CACHE_DIR, self.default_cache_dir)
        self.assertEqual(Arguments.DEFAULT_IMAGE, self.default_image)

    def test_defaults(self):
        """Test default arguments"""
        self.parser.parse(["run"])
        self.assertEqual(
            self.parser.tool_arguments["config"].name, self.default_configuration_file
        )
        self.assertEqual(self.parser.tool_arguments["cache"], self.default_cache_dir)
        self.assertEqual(self.parser.tool_arguments["image"], self.default_image)
        self.assertFalse(self.parser.tool_arguments["force_pull"])
        self.assertEqual(self.parser.tool_arguments["subcommand"], "run")
        self.assertEqual(len(self.parser.restic_arguments), 0)

    def test_common(self):
        """Test setting of common arguments"""
        alt_config = "/tmp/config.yml"
        alt_cache = "/tmp/cache"
        alt_image = "my/restic"
        with open(alt_config, "w", encoding="utf8") as file:
            file.write("# Comment")

        self.parser.parse(
            [
                "-c",
                alt_config,
                "--cache",
                alt_cache,
                "--image",
                alt_image,
                "--force-pull",
                "run",
            ]
        )
        self.assertEqual(self.parser.tool_arguments["config"].name, alt_config)
        self.assertEqual(self.parser.tool_arguments["cache"], alt_cache)
        self.assertEqual(self.parser.tool_arguments["image"], alt_image)
        self.assertTrue(self.parser.tool_arguments["force_pull"])
        self.assertEqual(self.parser.tool_arguments["log_level"], "warning")
        self.assertFalse(self.parser.tool_arguments["quiet"])

        self.parser.parse(
            [
                "--config",
                alt_config,
                "--log-level",
                "error",
                "-q",
                "run",
            ]
        )
        self.assertEqual(self.parser.tool_arguments["config"].name, alt_config)
        self.assertEqual(self.parser.tool_arguments["log_level"], "error")
        self.assertTrue(self.parser.tool_arguments["quiet"])

        self.parser.parse(
            [
                "--config",
                alt_config,
                "check",
            ]
        )
        self.assertEqual(self.parser.tool_arguments["config"].name, alt_config)

    def test_extra(self):
        """Test extra arguments"""
        self.parser.parse(
            [
                "run",
                "--arg-1",
                "--arg2",
            ]
        )
        self.assertEqual(self.parser.tool_arguments["subcommand"], "run")
        self.assertEqual(self.parser.restic_arguments, ["--arg-1", "--arg2"])

        self.parser.parse(
            [
                "restore",
                "-r",
                "foo",
                "-r",
                "bar",
            ]
        )
        self.assertEqual(self.parser.tool_arguments["subcommand"], "restore")
        self.assertEqual(self.parser.tool_arguments["restore"], "bar")
        self.assertEqual(self.parser.restic_arguments, [])

        self.parser.parse(
            [
                "restore",
                "-r",
                "foo",
                "--",
                "-r",
                "bar",
            ]
        )
        self.assertEqual(self.parser.tool_arguments["subcommand"], "restore")
        self.assertEqual(self.parser.tool_arguments["restore"], "foo")
        self.assertEqual(self.parser.restic_arguments, ["-r", "bar"])

    def test_exceptions(self):
        """Test invalid arguments"""

        with pytest.raises(SystemExit):
            self.parser.parse(["-c", "/tmp/nonexistent", "run"])

        with pytest.raises(SystemExit):
            self.parser.parse(["--image", "-v", "run"])

        with pytest.raises(SystemExit):
            self.parser.parse(["restore"])
