#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / pinned QEMU ARM64 RT early-boot trace, no compilation or flash
"""Track C: trace the R22 Image; symbolicate ELRs with its matching System.map.

FTRACE is disabled in this binary. QEMU -d exec,int,unimp,guest_errors is
used instead. Never report a kernel ftrace hash when CONFIG_FTRACE=n.
"""
import argparse, bisect, gzip, hashlib, json, re, shlex, subprocess, time
from pathlib import Path

IMAGE_SHA="812d46e04131cc1ded7dd26b13728f3d8834ff240d533cac80172dd070e6e907"
BOOT_APPEND=("earlycon=pl011,0x09000000 console=ttyAMA0,115200 "
             "loglevel=8 ignore_loglevel printk.time=1 nokaslr "
             "panic=5 initcall_debug=1 "
             "ftrace=function_graph "
             "ftrace_graph_filter=do_pre_smp_initcalls,smp_init,workqueue_init,rcu_init "
             "init=/init")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--artifact-root",type=Path,required=True)
    p.add_argument("--report-dir",type=Path,required=True)
    p.add_argument("--timeout",type=int,default=18)
    a=p.parse_args()
    root=a.artifact_root
    out=a.report_dir
    out.mkdir(parents=True,exist_ok=True)
    image=root/"outputs/qemu-rt/arch/arm64/boot/Image"
    sym=root/"outputs/qemu-rt/System.map"
    elf=root/"outputs/qemu-rt/vmlinux"
    config=(root/"outputs/qemu-rt/.config").read_text()
    ram=root/"smoke-initramfs.cpio.gz"
    assert sha(image.read_bytes())==IMAGE_SHA, "unexpected pinned binary"
    assert "# CONFIG_FTRACE is not set" in config
    assert elf.is_file() and elf.stat().st_size>1000000
    assert sym.is_file() and sym.stat().st_size>100000
    assert ram.stat().st_size>10000
    symbols=[]
    for line in sym.read_text().splitlines():
        x=line.split()
        if len(x)>=3:
            try:symbols.append((int(x[0],16),x[2]))
            except ValueError:pass
    symbols.sort()
    addresses=[x[0] for x in symbols]
    def resolve(pc):
        if pc is None:return None
        i=bisect.bisect_right(addresses,pc)-1
        if i<0:return None
        return {"name":symbols[i][1],"offset":hex(pc-addresses[i]),"symbol_address":hex(addresses[i])}
    trace=out/"qemu-preinit.log"
    cmd=["qemu-system-aarch64","-M","virt","-cpu","cortex-a72","-smp","4","-m","512",
         "-nodefaults","-serial","stdio","-monitor","none","-display","none","-nic","none",
         "-no-reboot","-d","exec,int,unimp,guest_errors","-D",str(trace),
         "-kernel",str(image),"-initrd",str(ram),"-append",BOOT_APPEND]
    (out/"qemu-command.txt").write_text(shlex.join(cmd)+"\n")
    t=time.monotonic_ns()
    try:
        run=subprocess.run(shlex.split((out/"qemu-command.txt").read_text()),
                           stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=a.timeout)
        code=run.returncode;console=run.stdout;timedout=False
    except subprocess.TimeoutExpired as e:
        code=124;console=e.stdout or b"";timedout=True
    duration=(time.monotonic_ns()-t)/1e9
    (out/"console-rt.txt").write_bytes(console)
    trace_text=trace.read_text(errors="replace") if trace.is_file() else ""
    trace_bytes=trace.stat().st_size if trace.is_file() else 0
    exceptions=[]
    last_significant=None
    tb_count=0
    for line in trace_text.splitlines():
        match=re.search(r"Trace\s+\d+:\s+0x[0-9a-fA-F]+\s+\[([0-9a-fA-F]+/)?([0-9a-fA-F]+)",line)
        if match:
            tb_count+=1
            pc=int(match.group(2),16)
            sym_pc=resolve(pc)
            if sym_pc and sym_pc["name"] not in ("cpu_do_idle","arch_cpu_idle","__cpu_do_idle"):
                last_significant={"pc":hex(pc),"symbol":sym_pc,"trace_line":line[:160]}
        if "Taking exception" in line:
            m=re.search(r"Taking exception\s+(\d+)\s+\[([^\]]+)\]",line)
            exceptions.append({"type":m.group(2) if m else "UNPARSED",
                               "number":int(m.group(1)) if m else None,"header":line[:280],
                               "pc":None,"symbol":None})
        if exceptions and ("with ELR" in line or "with PC" in line):
            m=re.search(r"(?:ELR|PC)\s*(?:0x)?([0-9a-fA-F]{8,16})",line)
            if m:
                pc=int(m.group(1),16)
                exceptions[-1]["pc"]=hex(pc)
                exceptions[-1]["symbol"]=resolve(pc)
    zipped=out/"qemu-preinit.log.gz"
    if trace.is_file():
        with trace.open("rb") as rd,gzip.open(zipped,"wb",compresslevel=6) as wr:
            for block in iter(lambda:rd.read(1<<20),b""):wr.write(block)
    logsha=sha(trace.read_bytes()) if trace.is_file() else None
    if trace.is_file():trace.unlink()
    text=console.decode("utf-8","replace")
    times=[float(x) for x in re.findall(r"(?m)^\[\s*(\d+\.\d+)\]",text)]
    results={"schema_version":1,"track":"C","run_image_source":42250522391,
             "image_sha":IMAGE_SHA,"config_sha":sha((root/"outputs/qemu-rt/.config").read_bytes()),
             "vmlinux_sha":sha(elf.read_bytes()),"system_map_sha":sha(sym.read_bytes()),
             "initramfs_sha":sha(ram.read_bytes()),
             "boot_cmdline":BOOT_APPEND,
             "qemu_exit_code":code,"timed_out":timedout,"duration_seconds":round(duration,6),
             "console_sha256":sha(console),"console_bytes":len(console),
             "console_lines":len(console.splitlines()),"console_first_40":text.splitlines()[:40],
             "console_last_20":text.splitlines()[-20:],
             "boot_reached_ms":round(1000*max(times),3) if times else None,
             "guest_running":"EXP76_QEMU_RT_SMOKE=GUEST_RUNNING" in text,
             "exception_count":len(exceptions),"last_5_exceptions":exceptions[-5:],
             "last_pc":last_significant["pc"] if last_significant else None,
             "last_symbol":last_significant["symbol"] if last_significant else None,
             "last_significant_pc":last_significant,
             "qemu_tb_count":tb_count,
             "qemu_trace_sha":logsha,"qemu_trace_sha256":logsha,"qemu_trace_bytes":trace_bytes,
             "ftrace_sha":None,"ftrace_sha256":None,"ftrace_available":False,
             "ftrace_status":"NOT_AVAILABLE_CONFIG_FTRACE_N",
             "hypothesis":"UNDETERMINED_TRACE_REQUIRES_STACK_OR_POST_IDLING_STATE",
             "build_performed":False,"flash_ready":False}
    (out/"exp76-track-c-preinit.json").write_text(json.dumps(results,indent=2)+"\n")
    print("EXP76_TRACK_C",json.dumps({k:v for k,v in results.items() if k not in ("console_first_40","console_last_20","last_significant_pc")},indent=2),flush=True)

if __name__=="__main__":
    main()
