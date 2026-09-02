import gzip
import os
import platform
import subprocess
import sys
import requests
from tools.logger import Logger
from tqdm import tqdm
import hashlib
from typing import Iterable, Mapping, Optional


def get_download_dir():
    download_loc = ""
    if os.environ.get("XDG_CACHE_HOME", None) is None:
        download_loc = os.path.join('/', "home", os.environ.get(
            "SUDO_USER", os.environ["USER"]), ".cache", "waydroid-script", "downloads"
        )
    else:
        download_loc = os.path.join(
            os.environ["XDG_CACHE_HOME"], "waydroid-script", "downloads"
        )
    if not os.path.exists(download_loc):
        os.makedirs(download_loc)
    return download_loc

# not good
def get_data_dir():
    return os.path.join('/', "home", os.environ.get("SUDO_USER", os.environ["USER"]), ".local", "share", "waydroid", "data")

# execute on host
def run(args: list, env: Optional[Mapping[str, str]] = None,
        ok_codes: Iterable[int] = (0,)):
    """Run a command on the host and raise unless its exit code is allowed.

    Failure is decided by the exit code, never by whether the command wrote
    anything to stderr. Plenty of well behaved tools print a warning, a
    progress line or a version banner on stderr and still succeed; treating
    that as an error is what made this function raise the nonsensical
    "returned non-zero exit status 0" reported upstream in #202, #251, #271
    and #277.

    ``ok_codes`` is an allowlist of exit codes the caller considers success.
    It replaces the previous ``ignore`` regex, which matched the command's
    stderr text against a pattern pinned to a three component version number
    and therefore broke as soon as e2fsck reached 1.47.10. An exit code is a
    number; say so with a number.
    """
    result = subprocess.run(
        args=args,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if result.returncode not in ok_codes:
        error = result.stderr.decode("utf-8")
        if error:
            Logger.error(error)
        raise subprocess.CalledProcessError(
            returncode=result.returncode,
            cmd=result.args,
            stderr=result.stderr
        )
    return result

# execute on waydroid shell
def shell(arg: str, env: Optional[str] = None):
    a = subprocess.Popen(
        # No "sudo" prefix: check_root() guarantees this process is already
        # root, and images.py has always called mount/umount/mountpoint
        # without one. Dropping it keeps every child in the same environment
        # as the parent instead of sending three of them through sudo's
        # env_reset.
        args=["waydroid", "shell"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    subprocess.Popen(
        args=["echo", "export BOOTCLASSPATH=/apex/com.android.art/javalib/core-oj.jar:/apex/com.android.art/javalib/core-libart.jar:/apex/com.android.art/javalib/core-icu4j.jar:/apex/com.android.art/javalib/okhttp.jar:/apex/com.android.art/javalib/bouncycastle.jar:/apex/com.android.art/javalib/apache-xml.jar:/system/framework/framework.jar:/system/framework/ext.jar:/system/framework/telephony-common.jar:/system/framework/voip-common.jar:/system/framework/ims-common.jar:/system/framework/framework-atb-backward-compatibility.jar:/apex/com.android.conscrypt/javalib/conscrypt.jar:/apex/com.android.media/javalib/updatable-media.jar:/apex/com.android.mediaprovider/javalib/framework-mediaprovider.jar:/apex/com.android.os.statsd/javalib/framework-statsd.jar:/apex/com.android.permission/javalib/framework-permission.jar:/apex/com.android.sdkext/javalib/framework-sdkextensions.jar:/apex/com.android.wifi/javalib/framework-wifi.jar:/apex/com.android.tethering/javalib/framework-tethering.jar"],
        stdout=a.stdin,
        stdin=subprocess.PIPE
    ).communicate()

    if env:
        subprocess.Popen(
            args=["echo", env],
            stdout=a.stdin,
            stdin=subprocess.PIPE
        ).communicate()

    subprocess.Popen(
        args=["echo", arg],
        stdout=a.stdin,
        stdin=subprocess.PIPE
    ).communicate()

    # communicate() drains both pipes and waits, which fixes three bugs the
    # previous version had stacked on top of each other:
    #   1. it decided failure from stderr instead of the exit code, same as
    #      run() did;
    #   2. it called a.stderr.read() twice, so the message it logged was the
    #      second (always empty) read;
    #   3. it never waited, so a.returncode was None and the exception read
    #      "returned non-zero exit status None".
    out, err = a.communicate()
    if a.returncode != 0:
        if err:
            Logger.error(err.decode("utf-8"))
        raise subprocess.CalledProcessError(
            returncode=a.returncode,
            cmd=a.args,
            stderr=err
        )
    return out.decode("utf-8")

def download_file(url, f_name):
    md5 = ""
    response = requests.get(url, stream=True)
    total_size_in_bytes = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 Kibibyte
    progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
    with open(f_name, 'wb') as file:
        for data in response.iter_content(block_size):
            progress_bar.update(len(data))
            file.write(data)
    progress_bar.close()
    with open(f_name, "rb") as f:
        bytes = f.read()
        md5 = hashlib.md5(bytes).hexdigest()
    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
        raise ValueError("Something went wrong while downloading")
    return md5

def host():
    machine = platform.machine()

    mapping = {
        "i686": ("x86", 32),
        "x86_64": ("x86_64", 64),
        "aarch64": ("arm64-v8a", 64),
        "armv7l": ("armeabi-v7a", 32),
        "armv8l": ("armeabi-v7a", 32)
    }
    if machine in mapping:
        if mapping[machine] == "x86_64":
            with open("/proc/cpuinfo") as f:
                if "sse4_2" not in f.read():
                    Logger.warning("x86_64 CPU does not support SSE4.2, falling back to x86...")
                    return ("x86", 32)
        return mapping[machine]
    raise ValueError("platform.machine '" + machine + "'"
                     " architecture is not supported")


def env_binary(name: str) -> str:
    """Absolute path to a binary that must come from this interpreter's env.

    Only two binaries have to be the ones the lockfile pinned: lzip and tar.
    Everything else the script shells out to (mount, umount, mountpoint,
    e2fsck, resize2fs, waydroid, openssl) is a host tool and is resolved
    through PATH as before.

    Resolving by absolute path rather than by PATH is what lets this program
    keep running under a plain `sudo`. sudo's env_reset replaces PATH with
    secure_path, so anything found through PATH inside a sudo'd process comes
    from the host, not from the environment the lockfile describes. Forwarding
    PATH across that boundary would work, but it also strips /usr/sbin and
    /sbin on Debian and Ubuntu (where a regular user's PATH does not include
    them), breaking e2fsck. An absolute path cannot be defeated by PATH at
    all, and it leaves secure_path intact for every host tool.

    Falls back to the bare name when the binary is not in the env, so a
    checkout run outside pixi still behaves the way it did before.
    """
    candidate = os.path.join(sys.prefix, "bin", name)
    return candidate if os.path.isfile(candidate) else name


def tar_lzip_command(archive: str, dest: str) -> list:
    """argv that extracts a .tar.lz using the env's own tar and lzip.

    `tar --lzip` shells out to lzip through PATH, so pinning tar alone is not
    enough: under sudo it would find the host's lzip, or none at all. Verified
    on a machine with no host lzip:

        tar --lzip -xf a.tar.lz            -> tar (child): lzip: Cannot exec
        tar --use-compress-program=<abs>   -> extracts

    --use-compress-program is the only form that pins the compressor too.
    """
    return [env_binary("tar"),
            "--use-compress-program=" + env_binary("lzip"),
            "-xvf", archive, "-C", dest]


def check_root():
    if os.geteuid() != 0:
        Logger.error("This script must be run as root. Aborting.")
        sys.exit(1)

def backup(path):
    gz_filename = path+".gz"
    with gzip.open(gz_filename, 'wb') as f_gz:
        with open(path, "rb") as f:
            f_gz.write(f.read())

def restore(path):
    gz_filename = path+".gz"
    with gzip.GzipFile(gz_filename) as f_gz:
        with open(path, "wb") as f:
            f.writelines(f_gz)
