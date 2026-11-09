# Python 3 / Ubuntu 24.04 GitHub Actions / E404 RT140 QEMU virt PL011 PTY BREAK + sysrq-t / NO FLASH
"""Capture raw kernel serial and try BREAK then 't' to dump blocked tasks on timeout."""
import argparse,fcntl,hashlib,json,os,pty,re,select,shlex,signal,subprocess,termios,time,tty
from pathlib import Path

APPEND=("earlycon=pl011,0x09000000 console=ttyAMA0,115200 "
        "loglevel=8 ignore_loglevel printk.time=1 nokaslr "
        "panic=5 initcall_debug=1 init=/init")
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as fd:
        for x in iter(lambda:fd.read(1<<20),b""):h.update(x)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--kernel",type=Path,required=True)
    ap.add_argument("--initrd",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--before-break",type=float,default=12)
    ap.add_argument("--after-break",type=float,default=8)
    a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    kernel=a.kernel.resolve();initrd=a.initrd.resolve()
    for x in [kernel,initrd]:assert x.is_file() and x.stat().st_size>1000,x
    # Explicitly own both ends of a POSIX PTY. QEMU's -serial pty prints
    # its assigned slave on stdout in some builds, which was discarded before.
    # -serial stdio connected to the PTY slave is stable and permits BREAK.
    fd, slave = pty.openpty()
    pty_path=os.ttyname(slave)
    tty.setraw(slave)
    os.set_blocking(fd, False)
    cmd=["qemu-system-aarch64","-M","virt","-cpu","cortex-a72","-smp","4","-m","512",
         "-nodefaults","-serial","stdio","-monitor","none","-display","none",
         "-nic","none","-no-reboot","-kernel",str(kernel),"-initrd",str(initrd),
         "-append",APPEND]
    (out/"qemu-command.txt").write_text(shlex.join(cmd)+"\n")
    proc=subprocess.Popen(cmd,stdout=slave,stderr=subprocess.PIPE,
                          stdin=slave,bufsize=0)
    os.close(slave)
    assert proc.stderr is not None
    os.set_blocking(proc.stderr.fileno(),False)
    err=b""
    start=time.monotonic()
    raw=bytearray();ioctl_status=[];break_sent=False
    try:
        deadline=time.monotonic()+a.before_break+a.after_break
        break_time=time.monotonic()+a.before_break
        while time.monotonic()<deadline and proc.poll() is None:
            if fd is not None and select.select([fd],[],[],0.1)[0]:
                try:raw.extend(os.read(fd,65536))
                except (BlockingIOError,OSError):pass
            if not break_sent and time.monotonic()>=break_time:
                break_sent=True
                if fd is not None:
                    try:
                        termios.tcsendbreak(fd,0)
                        ioctl_status.append("TCSENDBREAK_OK")
                    except OSError as ex:ioctl_status.append("TCSENDBREAK_ERROR:"+repr(ex))
                    try:
                        # Write SysRq key immediately after the serial BREAK.
                        os.write(fd,b"t")
                        ioctl_status.append("SYSRQ_T_WRITTEN")
                    except OSError as ex:ioctl_status.append("SYSRQ_T_ERROR:"+repr(ex))
                else:ioctl_status.append("SERIAL_PTY_UNAVAILABLE")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait(timeout=3)
        if fd is not None:
            for _ in range(10):
                if not select.select([fd],[],[],0.05)[0]:break
                try:raw.extend(os.read(fd,65536))
                except (BlockingIOError,OSError):break
            os.close(fd)
    data=bytes(raw)
    console=out/"console-full.txt";console.write_bytes(data)
    logs=data.decode("utf-8","replace").splitlines()
    timestamps=[float(m.group(1)) for ln in logs
                if (m:=re.match(r"^\[\s*(\d+\.\d+)\]",ln))]
    report={
       "schema_version":1,"track":"R30_PTYSYSRQ","image_sha256":digest(kernel),
       "initramfs_sha256":digest(initrd),
       "pty":pty_path,"sysrq_attempted":break_sent,
       "sysrq_transport_events":ioctl_status,
       "sysrq_task_dump_observed":any("SysRq : Show State" in ln or "Show State" in ln for ln in logs),
       "serial_console_sha256":digest(console),"console_bytes":len(data),
       "console_lines":len(logs),"last_lines":logs[-30:],
       "boot_reached_ms":round(max(timestamps)*1000,3) if timestamps else None,
       "guest_running":b"EXP76_QEMU_RT_SMOKE=GUEST_RUNNING" in data,
       "qemu_exit_after_harness_stop":proc.returncode,
       "qemu_stderr":err.decode("utf-8","replace")[:1600],
       "flash_ready":False}
    (out/"sysrq-audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print("R30_PTYSYSRQ",json.dumps(report,indent=2),flush=True)
if __name__=="__main__":
    main()
