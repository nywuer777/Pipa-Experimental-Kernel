#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / pinned E404 RT140 QEMU hardware breakpoint + lock owner capture / NO FLASH
"""Stop on the exact first B2 task_blocks_on_rt_mutex() entry and read lock owner."""
import argparse
import hashlib
import json
import re
import shlex
import socket
import subprocess
import time
from pathlib import Path

EXPECTED = {
    "Image": "aeffed3f051eb3f1166763fb9fdfb3a6e8c521fe90a000c9ff48019897a64c2b",
    "vmlinux": "e59f413d3b31c1e47298647303a3c1c23ba94178325c2626c233c44dd25acb0a",
    "config": "19294205006587189cbf79043ab81f83a0d2bfa4b4860a595f66a5df2398eac5",
    "initramfs": "b9c25fcc2934473c45458b68b2f65f682e55cc3648e803ba64ca410fe6f70e5e"
}
APPEND = ("earlycon=pl011,0x09000000 console=ttyAMA0,115200 loglevel=8 "
          "ignore_loglevel printk.time=1 nokaslr panic=5 initcall_debug=1 init=/init")

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def symbol_pc(smap, name):
    hits=[]
    for line in smap.read_text().splitlines():
        bits=line.split()
        if len(bits)>=3 and bits[2]==name:
            hits.append(int(bits[0],16))
    assert len(hits)==1, f"Expected one {name}, found {hits}"
    return hits[0]

def wait_port(port, wait_seconds=7.0):
    end=time.monotonic()+wait_seconds
    while time.monotonic()<end:
        try:
            with socket.create_connection(("127.0.0.1",port),timeout=0.3):
                return True
        except OSError:
            time.sleep(0.12)
    return False

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--artifact-root",type=Path,required=True)
    p.add_argument("--initramfs",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--port",type=int,default=12371)
    p.add_argument("--gdb-timeout",type=int,default=30)
    a=p.parse_args()
    root,out=a.artifact_root.resolve(),a.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    image=root/"r23b/output/arch/arm64/boot/Image"
    elf=root/"r23b/output/vmlinux"
    smap=root/"r23b/output/System.map"
    config=root/"r23b/reports/effective.config"
    ram=a.initramfs.resolve()
    for name,path in (("Image",image),("vmlinux",elf),("config",config),("initramfs",ram)):
        actual=sha(path)
        assert actual==EXPECTED[name],f"{name} hash mismatch: {actual}"
    lock_pc=symbol_pc(smap,"task_blocks_on_rt_mutex")
    pa_lock_pc=symbol_pc(smap,"pa_lock")
    freelist_pc=symbol_pc(smap,"get_page_from_freelist")
    assert freelist_pc == 0xffffff801010dff0, "unexpected pinned freelist start"
    freelist_ret_pc = freelist_pc + 0x9bc
    pa_lock_fn_pc=symbol_pc(smap,"rt_spin_lock")
    pa_unlock_fn_pc=symbol_pc(smap,"rt_spin_unlock")
    # CPU0 per-CPU base from pinned Image GDB evidence; checked again at target breakpoint.
    expected_pa_lock=0xffffffc01ffa2488
    assert pa_lock_pc==0xffffff801030c488, "unexpected pinned pa_lock symbol"
    dump=out/"console-full.txt"
    cmd=["qemu-system-aarch64","-M","virt","-cpu","cortex-a72","-smp","4","-m","512",
         "-nodefaults","-serial","file:"+str(dump),"-monitor","none","-display","none",
         "-nic","none","-no-reboot","-S","-gdb",f"tcp:127.0.0.1:{a.port}",
         "-kernel",str(image),"-initrd",str(ram),"-append",APPEND]
    (out/"qemu-command.txt").write_text(shlex.join(cmd)+"\n")
    # The target is at task_blocks_on_rt_mutex entry: x0=rt_mutex*,
    # x1=waiter*, x2=task*. rt_mutex.owner is after raw_spinlock_t
    # and rb_root_cached. Read +0x18 as a candidate, not a proven task identity.
    cmds=[
        "set pagination off",
        "set confirm off",
        "set architecture aarch64",
        "file "+str(elf),
        f"target remote 127.0.0.1:{a.port}",
        f"hbreak *0x{pa_lock_fn_pc:x} if $x0 == 0x{expected_pa_lock:x}",
        "commands 1",
        "silent",
        'printf "PA_LOCK_ENTER lock=%p owner_raw=0x%lx caller=%p\\n", $x0, *(unsigned long*)($x0+0x18), $x30',
        "continue",
        "end",
        f"hbreak *0x{pa_unlock_fn_pc:x} if $x0 == 0x{expected_pa_lock:x}",
        "commands 2",
        "silent",
        'printf "PA_LOCK_EXIT lock=%p owner_raw=0x%lx caller=%p\\n", $x0, *(unsigned long*)($x0+0x18), $x30',
        "continue",
        "end",
        f"hbreak *0x{freelist_ret_pc:x}",
        "commands 3",
        "silent",
        'printf "PA_LOCK_FREELIST_RETURN owner_raw=0x%lx retval=%p lr=%p\\n", *(unsigned long*)(0xffffffc01ffa2488+0x18), $x0, $x30',
        "continue",
        "end",
        f"hbreak *0x{lock_pc:x}",
        "continue",
        'printf "EXP76_LOCK_BREAK_HIT PC=%p\\n", $pc',
        'printf "EXP76_LOCK_ARGS lock=%p waiter=%p task=%p\\n", $x0, $x1, $x2',
        "info registers x0 x1 x2 x3 pc sp x29 x30",
        "bt 32",
        "x/8gx $x0",
        "set $owner_raw = *(unsigned long*)($x0+0x18)",
        'printf "EXP76_LOCK_OWNER_CANDIDATE raw=0x%lx ptr=0x%lx\\n", $owner_raw, $owner_raw & 0xfffffffffffffffc',
        "set $owner_ptr = $owner_raw & 0xfffffffffffffffc",
        "x/12gx $owner_ptr",
        "info threads",
        "detach",
        "quit"
    ]
    gdb_file=out/"breakpoint.gdb"
    gdb_file.write_text("\n".join(cmds)+"\n")
    gcmd=["gdb-multiarch","-q","-nx","-batch","-x",str(gdb_file)]
    (out/"gdb-command.txt").write_text(shlex.join(gcmd)+"\n")
    start=time.monotonic()
    gdb_exit=None
    gdb_timedout=False
    gdb_output=b""
    with (out/"qemu-stderr.txt").open("wb") as err:
        proc=subprocess.Popen(cmd,stderr=err,stdout=subprocess.DEVNULL,stdin=subprocess.DEVNULL)
        try:
            if wait_port(a.port):
                try:
                    g=subprocess.run(gcmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=a.gdb_timeout)
                    gdb_exit=g.returncode
                    gdb_output=g.stdout
                except subprocess.TimeoutExpired as exc:
                    gdb_timedout=True
                    gdb_exit=124
                    gdb_output=exc.stdout or b""
            else:
                gdb_exit=125
                gdb_output=b"QEMU GDB PORT NOT AVAILABLE"
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=4)
    gdb_path=out/"gdb-lock-owner.txt"
    gdb_path.write_bytes(gdb_output)
    info=gdb_output.decode("utf-8","replace")
    def extract(pattern):
        match=re.search(pattern,info)
        return match.group(1) if match else None
    lines=dump.read_text(errors="replace").splitlines() if dump.exists() else []
    data=dump.read_bytes() if dump.exists() else b""
    timestamps=[float(m.group(1)) for line in lines
                if (m:=re.match(r"^\[\s*(\d+\.\d+)\]",line))]
    result={
        "schema_version":1,"track":"B2-RTMUTEX-OWNER",
        "source_build_run_id":42629841386,
        "target_symbol":"task_blocks_on_rt_mutex",
        "target_address":hex(lock_pc),
        "image_sha256":sha(image),"vmlinux_sha256":sha(elf),
        "system_map_sha256":sha(smap),"config_sha256":sha(config),
        "initramfs_sha256":sha(ram),
        "gdb_exit_code":gdb_exit,"gdb_timed_out":gdb_timedout,
        "gdb_raw_sha256":sha(gdb_path),"gdb_raw_bytes":len(gdb_output),
        "break_hit": "EXP76_LOCK_BREAK_HIT" in info,
        "pa_lock_symbol_address":hex(pa_lock_pc),
        "pa_lock_cpu0_expected_address":hex(expected_pa_lock),
        "pa_lock_freelist_return_count":len(re.findall(r"PA_LOCK_FREELIST_RETURN",info)),
        "pa_lock_enter_count":len(re.findall(r"PA_LOCK_ENTER",info)),
        "pa_lock_exit_count":len(re.findall(r"PA_LOCK_EXIT",info)),
        "pa_lock_event_lines":[line for line in info.splitlines() if line.startswith("PA_LOCK_")],
        "lock_address":extract(r"EXP76_LOCK_ARGS lock=(0x[0-9a-fA-F]+)"),
        "owner_candidate_raw":extract(r"EXP76_LOCK_OWNER_CANDIDATE raw=(0x[0-9a-fA-F]+)"),
        "task_identity_proven":False,
        "guest_running":b"EXP76_QEMU_RT_SMOKE=GUEST_RUNNING" in data,
        "console_sha256":hashlib.sha256(data).hexdigest(),
        "console_lines":len(lines),"last_lines":lines[-20:],
        "reached_ms":round(1000*max(timestamps),3) if timestamps else None,
        "duration_seconds":round(time.monotonic()-start,3),
        "build_performed":False,"flash_ready":False,
        "caveat":"RT-mutex.owner offset +0x18 is a candidate from struct layout; verify raw bytes before attributing task ownership."
    }
    (out/"exp76-track-b2-rtmutex-owner.json").write_text(json.dumps(result,indent=2)+"\n")
    print("EXP76_B2_RTMUTEX",json.dumps(result,indent=2),flush=True)
    if not result["break_hit"]:
        raise SystemExit("Hardware breakpoint not reached; report and raw GDB log preserved")

if __name__=="__main__":
    main()
