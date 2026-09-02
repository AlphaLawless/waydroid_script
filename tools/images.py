import configparser
import os
import subprocess
import sys
from tools.helper import run
from tools.logger import Logger

def mount(image, mount_point):
    umount(mount_point, False)
    if not os.path.exists(mount_point):
        os.makedirs(mount_point)
    run(["mount", "-o", "rw", image, mount_point])

def umount(mount_point, exists=True):
    if not os.path.exists(mount_point):
        if not exists:
            return
        Logger.error("{} does not exist!".format(mount_point))
        raise FileNotFoundError()
    # mountpoint exits non-zero when the path is not a mount point, prints its
    # message on stdout and leaves stderr empty. That is a normal answer to a
    # question, not a failure, so allow it and branch on the code below.
    if not run(["mountpoint", mount_point], ok_codes=(0, 1, 32)).returncode:
        run(["umount", mount_point])
    else:
        Logger.warning("{} is not a mount point".format(
            mount_point))

def resize(img_file, size):
    # e2fsck exit codes are a bitmask: 0 clean, 1 errors corrected, 2 errors
    # corrected and a reboot is advised. The first three are success; 4 and up
    # (uncorrected errors, operational error, usage error) must not reach
    # resize2fs.
    run(["e2fsck", "-y", "-f", img_file], ok_codes=(0, 1, 2))
    run(["resize2fs", img_file, size])

def get_image_dir():
    # Read waydroid config to get image location
    cfg = configparser.ConfigParser()
    cfg_file = os.environ.get("WAYDROID_CONFIG", "/var/lib/waydroid/waydroid.cfg")
    if not os.path.isfile(cfg_file):
        Logger.error("Cannot locate waydroid config file, reinit wayland and try again!")
        sys.exit(1)
    cfg.read(cfg_file)
    if "waydroid" not in cfg:
        Logger.error("Required entry in config was not found, Cannot continue!") #magisk
        sys.exit(1)
    return cfg["waydroid"]["images_path"]
