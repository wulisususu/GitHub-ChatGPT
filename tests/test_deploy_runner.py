import importlib.util
import pathlib
import tempfile
import unittest


SCRIPT_PATH = pathlib.Path(__file__).parents[1] / "deploy_runner.py"


def load_deploy_runner(test_case):
    if not SCRIPT_PATH.exists():
        test_case.fail(f"Expected deployment script at {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("deploy_runner", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryUrlTests(unittest.TestCase):
    def test_parses_https_repository_url(self):
        deploy_runner = load_deploy_runner(self)
        self.assertEqual(
            ("wulisususu", "Android-Suspect-Interrogation"),
            deploy_runner.parse_repository_url(
                "https://github.com/wulisususu/Android-Suspect-Interrogation.git"
            ),
        )


class RunnerAssetTests(unittest.TestCase):
    def test_selects_arm64_archive_and_sha256(self):
        deploy_runner = load_deploy_runner(self)
        release = {
            "tag_name": "v2.336.0",
            "assets": [
                {
                    "name": "actions-runner-linux-arm64-2.336.0.tar.gz",
                    "browser_download_url": "https://example.invalid/runner.tar.gz",
                    "digest": "sha256:58b758e420b87093fbd4bfddd368074960053e2f1388f01848c82624b90f27d1",
                }
            ],
        }

        asset = deploy_runner.select_runner_asset(release, "arm64")

        self.assertEqual("2.336.0", asset.version)
        self.assertEqual("actions-runner-linux-arm64-2.336.0.tar.gz", asset.filename)
        self.assertEqual(
            "58b758e420b87093fbd4bfddd368074960053e2f1388f01848c82624b90f27d1",
            asset.sha256,
        )


class ArchitectureTests(unittest.TestCase):
    def test_maps_linux_machine_names(self):
        deploy_runner = load_deploy_runner(self)
        self.assertEqual("arm64", deploy_runner.runner_architecture("aarch64"))
        self.assertEqual("x64", deploy_runner.runner_architecture("x86_64"))


class FileHashTests(unittest.TestCase):
    def test_hashes_file_without_reading_it_as_text(self):
        deploy_runner = load_deploy_runner(self)
        with tempfile.TemporaryDirectory() as directory:
            file_path = pathlib.Path(directory) / "archive"
            file_path.write_bytes(b"runner archive")
            self.assertEqual(
                "39f97c48c8cfd8f6ae055e71c4e740afa617e7fea4f721d19e058884bf96a3fc",
                deploy_runner.sha256_file(file_path),
            )


if __name__ == "__main__":
    unittest.main()
