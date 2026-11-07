#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 RT Track A/B Clang21 build and QEMU 4cpu smoke, no flash
"""Reproducible no-FLASH vanilla-vs-vendor QEMU build/smoke driver."""
import argparse, hashlib, json, os, re, shlex, subprocess, time
from pathlib import Path

APPEND=("earlycon=pl011,0x09000000 console=ttyAMA0,115200 "
        "loglevel=8 ignore_loglevel printk.time=1 nokaslr "
        "panic=5 initcall_debug=1 init=/init")
DEFAULT_REQUIRED={
    "CONFIG_PREEMPT_RT_FULL":"y",
    "CONFIG_SMP":"y",
    "CONFIG_SERIAL_AMBA_PL011":"y",
    "CONFIG_SERIAL_AMBA_PL011_CONSOLE":"y",
    "CONFIG_BLK_DEV_INITRD":"y",
    "CONFIG_MAGIC_SYSRQ":"y",
    "CONFIG_PRINTK":"y",
    "CONFIG_BINFMT_ELF":"y",
    "CONFIG_ARM_PSCI_FW":"y"
}

def sha(path):
    if not path.is_file():return None
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):h.update(block)
    return h.hexdigest()

def run_logged(argv,where,timeout):
    t=time.monotonic_ns()
    where.parent.mkdir(parents=True,exist_ok=True)
    code=None;timed_out=False
    with where.open("wb") as log:
        proc=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT)
        try:code=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=5)
            code=124
    return {"exit_code":code,"timed_out":timed_out,
            "duration_seconds":round((time.monotonic_ns()-t)/1e9,6),
            "sha256":sha(where),"bytes":where.stat().st_size}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--track",choices=("A","B"),required=True)
    p.add_argument("--tree",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--reports",type=Path,required=True)
    p.add_argument("--initramfs",type=Path,required=True)
    p.add_argument("--build-seconds",type=int,default=7200)
    p.add_argument("--qemu-seconds",type=int,default=45)
    a=p.parse_args()
    a.reports.mkdir(parents=True,exist_ok=True)
    config=a.output/".config"
    assert config.stat().st_size>0,"no effective Kconfig"
    rawconfig=config.read_text()
    kconfig={}
    for line in rawconfig.splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            k,v=line.split("=",1);kconfig[k]=v
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            kconfig[line.split()[1]]="n"
    required={k:{"expected":v,"actual":kconfig.get(k,"<absent>")} for k,v in DEFAULT_REQUIRED.items()}
    missing={k:v for k,v in required.items() if v["actual"]!=v["expected"]}
    env=os.environ.copy()
    clang=Path(env["ANDROID_CLANG_BIN"])/"clang"
    assert clang.is_file(),f"missing Android Clang 21: {clang}"
    path=str(clang.parent)+":"+env.get("PATH","")
    env["PATH"]=path
    cmd=["make","-C",str(a.tree.absolute()),"O="+str(a.output.absolute()),"ARCH=arm64",
         "CC=clang","LD=ld.lld","AR=aarch64-linux-gnu-ar","NM=aarch64-linux-gnu-nm","OBJCOPY=llvm-objcopy",
         "HOSTCC=gcc","CROSS_COMPILE=aarch64-linux-gnu-",
         "CLANG_TRIPLE=aarch64-linux-gnu-","LLVM_IAS=1","-j8","Image"]
    (a.reports/"build-command.txt").write_text(shlex.join(cmd)+"\n")
    report={"schema_version":1,"track":a.track,
            "kernel_tree":str(a.tree),"config_sha":sha(config),
            "initramfs_sha":sha(a.initramfs),"android_llvm_commit":env.get("ANDROID_LLVM_COMMIT"),
            "required_kconfig":required,"required_missing":missing,
            "requested_boot_append":APPEND,"boots":False,"guest_running":False,
            "image_sha":None,"vmlinux_sha":None,"system_map_sha":None,
            "build_exit_code":None,"boot_exit_code":None,"reached_ms":None,
            "console_sha256":None,"console_bytes":None,"console_lines":None,
            "last_lines":[],"build_complete":False,"flash_ready":False}
    name="exp76-track-a-vanilla.json" if a.track=="A" else "exp76-track-b-minimal.json"
    dest=a.reports/name
    dest.write_text(json.dumps(report,indent=2)+"\n")
    if missing:
        report["error"]="REQUIRED_KCONFIG_NOT_ENABLED_AFTER_OLDDEFCONFIG"
        dest.write_text(json.dumps(report,indent=2)+"\n")
        print("EXP76_TRACK_CONFIG_NOT_QUALIFIED",json.dumps(missing,indent=2))
        raise SystemExit(2)
    built=run_logged(cmd,a.reports/"build.log",a.build_seconds)
    report["build"]=built
    report["build_exit_code"]=built["exit_code"]
    image=a.output/"arch/arm64/boot/Image"
    elf=a.output/"vmlinux"
    sym=a.output/"System.map"
    report["image_sha"]=sha(image)
    report["vmlinux_sha"]=sha(elf)
    report["system_map_sha"]=sha(sym)
    report["build_complete"]=built["exit_code"]==0 and all(v is not None for v in
                       (report["image_sha"],report["vmlinux_sha"],report["system_map_sha"]))
    if not report["build_complete"]:
        report["error"]="BUILD_FAILED_OR_MISSING_IMAGE_ELF"
        report["build_log_tail"]=(a.reports/"build.log").read_text(errors="replace").splitlines()[-50:]
        dest.write_text(json.dumps(report,indent=2)+"\n")
        print("EXP76_TRACK_BUILD_FAILURE",json.dumps({k:v for k,v in report.items() if k not in ("required_kconfig",)},indent=2),flush=True)
        raise SystemExit(3)
    args=["qemu-system-aarch64","-M","virt","-cpu","cortex-a72","-smp","4","-m","512",
          "-nodefaults","-serial","stdio","-monitor","none","-display","none",
          "-nic","none","-no-reboot","-kernel",str(image),"-initrd",str(a.initramfs),
          "-append",APPEND]
    (a.reports/"qemu-command.txt").write_text(shlex.join(args)+"\n")
    log=a.reports/"console-full.txt"
    run=run_logged(shlex.split((a.reports/"qemu-command.txt").read_text()),log,a.qemu_seconds)
    console=log.read_text(errors="replace").replace("\r","")
    times=[float(x) for x in re.findall(r"(?m)^\[\s*(\d+\.\d+)\]",console)]
    report.update({
        "boot":run,"boot_exit_code":run["exit_code"],
        "console_sha256":sha(log),"console_bytes":log.stat().st_size,
        "console_lines":len(log.read_bytes().splitlines()),
        "reached_ms":round(1000*max(times),3) if times else None,
        "last_lines":console.splitlines()[-20:],
        "console_first_40":console.splitlines()[:40],
        "guest_running":"EXP76_QEMU_RT_SMOKE=GUEST_RUNNING" in console,
        "kernel_panic":"Kernel panic" in console,
        "boots":"EXP76_QEMU_RT_SMOKE=GUEST_RUNNING" in console and "Kernel panic" not in console,
        "initramfs_exercised":"EXP76_QEMU_RT_SMOKE=BEGIN" in console})
    if a.track=="B":report["advanced_from_032"]=report["reached_ms"] is not None and report["reached_ms"]>32.0
    dest.write_text(json.dumps(report,indent=2)+"\n")
    print("EXP76_TRACK_RESULT",json.dumps({k:v for k,v in report.items() if k not in ("required_kconfig","last_lines","console_first_40")},indent=2),flush=True)
    print("EXP76_LAST_20\n"+"\n".join(report["last_lines"]),flush=True)
    if not report["boots"]:raise SystemExit(5)

if __name__=="__main__":
    main()
