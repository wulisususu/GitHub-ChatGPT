#!/usr/bin/env python3
"""Register a Linux server as a repository-scoped GitHub Actions runner."""

import argparse
import hashlib
import json
import os
import pathlib
import re
import shlex
import sys
import tempfile
import urllib.request
from dataclasses import dataclass


RUNNER_RELEASE_URL = "https://api.github.com/repos/actions/runner/releases/latest"
GITHUB_API_VERSION = "2022-11-28"


@dataclass(frozen=True)
class RunnerAsset:
    version: str
    filename: str
    url: str
    sha256: str


def parse_repository_url(repository_url):
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([^/\s]+)/([^/\s#]+?)(?:\.git)?/?",
        repository_url.strip(),
    )
    if not match:
        raise ValueError("repository must be a GitHub HTTPS or SSH repository URL")
    return match.group(1), match.group(2)


def runner_architecture(machine):
    normalized = machine.strip().lower()
    mapping = {"aarch64": "arm64", "arm64": "arm64", "x86_64": "x64", "amd64": "x64"}
    if normalized not in mapping:
        raise ValueError(f"unsupported Linux architecture: {machine.strip()}")
    return mapping[normalized]


def select_runner_asset(release, architecture):
    version = release["tag_name"].removeprefix("v")
    filename = f"actions-runner-linux-{architecture}-{version}.tar.gz"
    asset = next((item for item in release.get("assets", []) if item["name"] == filename), None)
    if not asset:
        raise ValueError(f"GitHub release does not contain {filename}")
    digest = asset.get("digest", "")
    if not digest.startswith("sha256:"):
        raise ValueError(f"GitHub release does not provide a SHA-256 digest for {filename}")
    return RunnerAsset(version, filename, asset["browser_download_url"], digest.removeprefix("sha256:"))


def github_request(url, token, proxy, method="GET"):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "GitHub-ChatGPT-runner-bootstrap",
    }
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    )
    request = urllib.request.Request(url, headers=headers, method=method)
    with opener.open(request, timeout=60) as response:
        return json.load(response)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as input_file:
        while chunk := input_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified_asset(asset, proxy, destination):
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    )
    request = urllib.request.Request(asset.url, headers={"User-Agent": "GitHub-ChatGPT-runner-bootstrap"})
    with opener.open(request, timeout=120) as response, open(destination, "wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)

    actual_sha256 = sha256_file(destination)
    if actual_sha256.lower() != asset.sha256.lower():
        pathlib.Path(destination).unlink(missing_ok=True)
        raise ValueError(f"SHA-256 mismatch for {asset.filename}")


def ssh_run(client, command, stdin_data=None, check=True):
    stdin, stdout, stderr = client.exec_command(command)
    if stdin_data is not None:
        stdin.write(stdin_data)
        stdin.channel.shutdown_write()
    output = stdout.read().decode(errors="replace")
    error = stderr.read().decode(errors="replace")
    status = stdout.channel.recv_exit_status()
    if check and status:
        raise RuntimeError(error.strip() or output.strip() or f"remote command failed ({status})")
    return status, output, error


def remote_runner_path(owner, repository):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", f"{owner}-{repository}")
    return f".github-actions-runners/{safe_name}"


def build_remote_install_script(
    archive_name,
    owner,
    repository,
    runner_name,
    labels,
    registration_token,
    user,
    sudo_password,
):
    relative_runner_path = remote_runner_path(owner, repository)
    labels_text = ",".join(labels)
    sudo_prefix = "sudo -n"
    if sudo_password:
        sudo_prefix = f"printf '%s\\n' {shlex.quote(sudo_password)} | sudo -S -p ''"

    def sudo(command):
        return f"{sudo_prefix} {command}"

    return f"""set -euo pipefail
archive=/tmp/{shlex.quote(archive_name)}
runner_dir=\"$HOME/{relative_runner_path}\"
trap 'rm -f \"$archive\"' EXIT
if [ -f \"$runner_dir/.runner\" ]; then
    echo 'Runner is already registered; archive removed without changes.'
    exit 0
fi
mkdir -p \"$runner_dir\"
tar xzf \"$archive\" -C \"$runner_dir\"
cd \"$runner_dir\"
{sudo('./bin/installdependencies.sh')}
./config.sh --unattended --url {shlex.quote(f'https://github.com/{owner}/{repository}')} --token {shlex.quote(registration_token)} --name {shlex.quote(runner_name)} --labels {shlex.quote(labels_text)} --work _work
{sudo(f'./svc.sh install {shlex.quote(user)}')}
{sudo('./svc.sh start')}
{sudo('./svc.sh status')}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="GitHub repository URL to host")
    parser.add_argument("--host", required=True, help="Server address")
    parser.add_argument("--user", required=True, help="SSH user")
    parser.add_argument("--password", help="SSH password; omit to use SSH keys or agent")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument("--github-token", default=os.getenv("GITHUB_TOKEN"), help="PAT; prefer GITHUB_TOKEN environment variable")
    parser.add_argument("--proxy", default="http://127.0.0.1:7897", help="Local HTTP proxy; use an empty string to disable")
    parser.add_argument("--runner-name", help="Runner name shown in GitHub")
    parser.add_argument("--label", action="append", default=[], help="Extra runner label; may be repeated")
    parser.add_argument("--sudo-password", help="Sudo password; defaults to --password when supplied")
    args = parser.parse_args()

    if not args.github_token:
        parser.error("set GITHUB_TOKEN or pass --github-token")

    try:
        import paramiko
    except ImportError as error:
        raise SystemExit("Install Paramiko first: python -m pip install paramiko") from error

    owner, repository = parse_repository_url(args.repository)
    runner_root = remote_runner_path(owner, repository)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        port=args.port,
        username=args.user,
        password=args.password,
        look_for_keys=args.password is None,
        allow_agent=args.password is None,
        timeout=30,
    )
    try:
        existing_check = f'test -f "$HOME/{runner_root}/.runner"'
        if ssh_run(client, existing_check, check=False)[0] == 0:
            print("Runner already registered; no download or server changes were needed.")
            return

        machine = ssh_run(client, "uname -m")[1]
        architecture = runner_architecture(machine)
        print(f"Remote architecture: {architecture}")
        release = github_request(RUNNER_RELEASE_URL, args.github_token, args.proxy)
        asset = select_runner_asset(release, architecture)
        registration = github_request(
            f"https://api.github.com/repos/{owner}/{repository}/actions/runners/registration-token",
            args.github_token,
            args.proxy,
            method="POST",
        )
        registration_token = registration["token"]
        runner_name = args.runner_name or re.sub(
            r"[^A-Za-z0-9_.-]", "-", f"{repository}-{architecture}-{args.host}"
        )
        labels = ["managed-by-github-chatgpt", *args.label]

        with tempfile.TemporaryDirectory(prefix="github-actions-runner-") as temporary_directory:
            local_archive = pathlib.Path(temporary_directory) / asset.filename
            print(f"Downloading {asset.filename} locally through the configured proxy...")
            download_verified_asset(asset, args.proxy, local_archive)
            print("SHA-256 verified. Uploading to the server...")
            sftp = client.open_sftp()
            try:
                sftp.put(str(local_archive), f"/tmp/{asset.filename}")
            finally:
                sftp.close()

        script = build_remote_install_script(
            asset.filename,
            owner,
            repository,
            runner_name,
            labels,
            registration_token,
            args.user,
            args.sudo_password if args.sudo_password is not None else args.password,
        )
        _, output, error = ssh_run(client, "bash -s", stdin_data=script)
        if output:
            print(output, end="")
        if error:
            print(error, end="", file=sys.stderr)
        print("Runner installed, enabled, and started.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
