# Python 3 / Ubuntu 24.04 GitHub Actions / pack real ARM64 exp76_rt_spin_sleep.ko + V3 gate and RT config into QEMU initramfs / NO FLASH
"""Extend the pinned smoke initramfs with an actual external RT spinlock module."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path

APPLET_NAMES=("mount","dmesg","insmod","rmmod","timeout","awk","grep","sed","cat",
              "mktemp","wc","tail","tr","mkdir","ls","sleep","sync","poweroff","echo")
INIT="""#!/bin/sh
export PATH=/bin
mkdir -p /proc /sys /tmp /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys
echo 'EXP76_QEMU_RT_SMOKE=BEGIN'
echo 'EXP76_QEMU_RT_SMOKE=GUEST_RUNNING'
echo 'EXP76_RT_SPIN_SLEEP_V3=BEGIN'
/bin/sh /probe/gate.sh execute normal /probe/rt.ko /config/rt.config /tmp/normal
rc=$?
echo "EXP76_RT_SPIN_SLEEP_V3_GATE_RC=$rc"
if [ "$rc" -eq 0 ]; then
  echo 'RT_SEMANTICS_VERIFIED=PASS'
else
  echo 'RT_SEMANTICS_VERIFIED=FAIL'
fi
sync
poweroff -f
"""
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for blk in iter(lambda:f.read(1048576),b""):h.update(blk)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser()
    for f in ("original","module","config","gate","output","report"):
        p.add_argument("--"+f,type=Path,required=True)
    a=p.parse_args()
    src=a.original.resolve();module=a.module.resolve();cfg=a.config.resolve()
    gate=a.gate.resolve();dest=a.output.resolve();report=a.report.resolve()
    assert all(x.is_file() for x in (src,module,cfg,gate))
    assert "CONFIG_PREEMPT_RT_FULL=y" in cfg.read_text()
    assert "CONFIG_MODULES=y" in cfg.read_text()
    assert "CONFIG_MODULE_UNLOAD=y" in cfg.read_text()
    root=Path("/tmp/exp76-r30-v3-root")
    if root.exists():shutil.rmtree(root)
    root.mkdir(parents=True)
    with src.open("rb") as f:
        decompressor=subprocess.Popen(["gzip","-dc"],stdin=f,stdout=subprocess.PIPE)
        assert decompressor.stdout is not None
        extract=subprocess.run(["cpio","-id","--no-absolute-filenames","--quiet"],
                               stdin=decompressor.stdout,cwd=root,check=True)
        decompressor.stdout.close()
        assert decompressor.wait()==0
    assert (root/"bin/busybox").is_file(),"original BusyBox static missing"
    (root/"probe").mkdir(exist_ok=True);(root/"config").mkdir(exist_ok=True)
    (root/"tmp").mkdir(exist_ok=True);(root/"proc").mkdir(exist_ok=True)
    (root/"sys").mkdir(exist_ok=True)
    shutil.copyfile(module,root/"probe/rt.ko")
    shutil.copyfile(gate,root/"probe/gate.sh")
    shutil.copyfile(cfg,root/"config/rt.config")
    boot=root/"init";boot.write_text(INIT);boot.chmod(0o755)
    for applet in APPLET_NAMES:
        pth=root/"bin"/applet
        if pth.is_symlink() or pth.exists():continue
        pth.symlink_to("busybox")
    dest.parent.mkdir(parents=True,exist_ok=True)
    manifest={}
    for label,path in [
       ("original_initramfs",src),("external_module",module),
       ("effective_rt_config",cfg),("gate_script",gate)]:
        manifest[label]={"sha256":sha(path),"bytes":path.stat().st_size}
    index=subprocess.Popen(["find",".","-print0"],cwd=root,stdout=subprocess.PIPE)
    assert index.stdout is not None
    cpio=subprocess.Popen(["cpio","--null","-ov","--format=newc"],
                          cwd=root,stdin=index.stdout,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    index.stdout.close();data,err=cpio.communicate(timeout=60)
    assert index.wait(timeout=10)==0 and cpio.returncode==0,err.decode(errors="replace")[:3000]
    with dest.open("wb") as out:
        compressor=subprocess.run(["gzip","-9"],input=data,stdout=out,check=True)
    manifest["v3_initramfs"]={"sha256":sha(dest),"bytes":dest.stat().st_size}
    manifest["retained_original_busybox_sha256"]=sha(root/"bin/busybox")
    result={"schema_version":1,"stage":"R30_V3_INITRAMFS","files":manifest,
            "module_path":"/probe/rt.ko","gate_path":"/probe/gate.sh",
            "config_path":"/config/rt.config",
            "rt_semantics_verified":"AWAITING_GUEST_OUTPUT", "flash_ready":False}
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,indent=2)+"\n")
    print("R30_V3_INITRAMFS",json.dumps(result,indent=2),flush=True)
if __name__=="__main__":
    main()
