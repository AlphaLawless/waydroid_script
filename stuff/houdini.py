from stuff.general import General


class Houdini(General):
    """Removal only: libhoudini can no longer be installed.

    The only builds available (supremegamers, for Android 11 and 13) carry an
    expiry compiled into libhoudini.so, 2026-08-31 00:00 UTC. Past it ARM apps
    hang at launch or close immediately, with nothing in the logs naming the
    translator. There is no newer build to point at, so installing it would
    only break ARM apps; libndk is the translator that remains.

    The file list and properties stay so `remove libhoudini` can still undo
    an earlier install.
    """
    id = "libhoudini"
    partition = "system"
    apply_props = {
        "ro.product.cpu.abilist": "x86_64,x86,arm64-v8a,armeabi-v7a,armeabi",
        "ro.product.cpu.abilist32": "x86,armeabi-v7a,armeabi",
        "ro.product.cpu.abilist64": "x86_64,arm64-v8a",
        "ro.dalvik.vm.native.bridge": "libhoudini.so",
        "ro.enable.native.bridge.exec": "1",
        "ro.dalvik.vm.isa.arm": "x86",
        "ro.dalvik.vm.isa.arm64": "x86_64"
    }
    files = [
        "bin/arm",
        "bin/arm64",
        "bin/houdini",
        "bin/houdini64",
        "etc/binfmt_misc",
        "etc/init/houdini.rc",
        "lib/arm",
        "lib/libhoudini.so",
        "lib64/arm64",
        "lib64/libhoudini.so"
    ]

    def __init__(self, android_version="11") -> None:
        super().__init__()
