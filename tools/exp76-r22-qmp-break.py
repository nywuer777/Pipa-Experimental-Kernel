#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / QEMU ARM64 QMP serial BREAK SysRq-t against pinned RT Image / NO BUILD NO FLASH
"""Send a real QEMU chardev BREAK and 't' over a PTY, record guest bytes."""
import argparse
import hashlib
import json
import os
import re
import selectors
import shlex
import socket
import subprocess
import termios
import time
import tty
from pathlib import Path

def digest(x):
    return hashlib.sha256(x).hexdigest()

def qmp_exchange(sock, obj):
    raw=(json.dumps(obj,separators=(',',':'))+'\n').encode()
    sock.sendall(raw)
    payload=b''
    until=time.monotonic()+3
    while time.monotonic()<until:
        try: part=sock.recv(65536)
        except socket.timeout: continue
        if not part:break
        payload+=part
        if b'\n' in payload:
            for chunk in payload.splitlines():
                try:
                    item=json.loads(chunk)
                    if 'return' in item or 'error' in item:return item
                except ValueError:pass
    return {'error':'QMP no response','raw':payload.decode('utf-8','replace')[:500]}

def run(image,initrd,out,seconds):
    out.mkdir(parents=True,exist_ok=True)
    qmp_path='/tmp/exp76-r22-qmp-break.sock'
    try:os.unlink(qmp_path)
    except FileNotFoundError:pass
    append=("earlycon=pl011,0x09000000 console=ttyAMA0,115200 "
            "loglevel=8 ignore_loglevel printk.time=1 nokaslr panic=5 "
            "initcall_debug=1 sysrq_always_enabled=1 init=/init")
    cmd=[
        'qemu-system-aarch64','-M','virt','-cpu','cortex-a72','-smp','4','-m','512',
        '-nodefaults','-chardev','pty,id=exp76serial','-serial','chardev:exp76serial',
        '-qmp',f'unix:{qmp_path},server=on,wait=off',
        '-monitor','none','-display','none','-nic','none','-no-reboot',
        '-kernel',str(image),'-initrd',str(initrd),'-append',append]
    cmdfile=out/'qemu-cmdline.txt'
    cmdfile.write_text(shlex.join(cmd)+'\n')
    cmd=shlex.split(cmdfile.read_text())
    start=time.monotonic()
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                          stdin=subprocess.DEVNULL,bufsize=0)
    assert proc.stdout
    hostfd=proc.stdout.fileno()
    os.set_blocking(hostfd,False)
    sel=selectors.DefaultSelector()
    sel.register(hostfd,selectors.EVENT_READ,'qemu')
    host=bytearray()
    guest=bytearray()
    ttyfd=None
    ttyname=None
    sock=None
    qmp_log=[]
    events=[]
    break_sent=False
    while time.monotonic()-start<seconds:
        elapsed=time.monotonic()-start
        if sock is None and os.path.exists(qmp_path):
            try:
                s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                s.settimeout(.5)
                s.connect(qmp_path)
                greeting=s.recv(65536)
                qmp_log.append({'greeting':greeting.decode('utf-8','replace')[:1000]})
                result=qmp_exchange(s,{'execute':'qmp_capabilities'})
                qmp_log.append({'capabilities':result})
                if 'return' in result:sock=s
                else:s.close()
            except (OSError,TimeoutError) as e:
                events.append({'qmp_connect_error':str(e)[:200]})
        if elapsed>=5 and sock and ttyfd is not None and not break_sent:
            answer=qmp_exchange(sock,{'execute':'chardev-send-break',
                                     'arguments':{'id':'exp76serial'}})
            qmp_log.append({'chardev_send_break':answer})
            if 'return' in answer:
                os.write(ttyfd,b't')
                events.append({'at':round(elapsed,4),
                               'method':'QMP chardev-send-break then ASCII t',
                               'qmp_return':True})
            else:
                events.append({'at':round(elapsed,4),
                               'method':'QMP chardev-send-break','qmp_return':False})
            break_sent=True
        for key,_ in sel.select(timeout=.15):
            try: b=os.read(key.fd,65536)
            except (BlockingIOError,OSError): b=b''
            if not b:continue
            if key.data=='qemu':
                host.extend(b)
                if ttyfd is None:
                    m=re.search(rb'char device redirected to (/dev/pts/[0-9]+)',host)
                    if m:
                        ttyname=m.group(1).decode()
                        ttyfd=os.open(ttyname,os.O_RDWR|os.O_NONBLOCK|os.O_NOCTTY)
                        tty.setraw(ttyfd,termios.TCSANOW)
                        sel.register(ttyfd,selectors.EVENT_READ,'serial')
            else:guest.extend(b)
        if proc.poll() is not None and elapsed>0.5:break
    timed_out=proc.poll() is None
    if timed_out:
        proc.terminate()
        try:proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait(timeout=4)
    if ttyfd is not None:
        for _ in range(40):
            try:b=os.read(ttyfd,65536)
            except (BlockingIOError,OSError):break
            if not b:break
            guest.extend(b)
        os.close(ttyfd)
    if sock:sock.close()
    sel.close()
    console=bytes(guest)
    status=bytes(host)
    (out/'qemu-console-qmp-break.txt').write_bytes(console)
    (out/'host-qemu-status.txt').write_bytes(status)
    guest_text=console.decode('utf-8','replace')
    sysrq_task_lines=[
        l for l in guest_text.splitlines()
        if ('SysRq : Show State' in l or 'sysrq: Show State' in l
            or 'sysrq: Show State Uninterruptible' in l)]
    result={
      'test_id':'EXP76_R22_QMP_BREAK_TASK_DUMP_NO_BUILD',
      'image_sha256':digest(image.read_bytes()),
      'initrd_sha256':digest(initrd.read_bytes()),
      'duration_sec':round(time.monotonic()-start,6),
      'qemu_exit_code':proc.returncode,'host_timed_out':timed_out,
      'console_sha256':digest(console),'console_bytes':len(console),
      'console_lines':len(console.splitlines()),
      'last_printk':next((l for l in reversed(guest_text.splitlines())
                           if re.search(r'\[\s*[0-9.]+\]',l)),None),
      'boot_guest_running':'EXP76_QEMU_RT_SMOKE=GUEST_RUNNING' in guest_text,
      'sysrq_t_dump_found':bool(sysrq_task_lines),
      'sysrq_t_lines':sysrq_task_lines,
      'pty_name':ttyname,'events':events,'qmp_replies':qmp_log,
      'qemu_cmdline_sha256':digest(cmdfile.read_bytes()),
      'host_status_sha256':digest(status),
      'kernel_build_performed':False,'flash_ready':False}
    (out/'qmp-break-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    print('EXP76_R22_QMP_END')

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--image',type=Path,required=True)
    a.add_argument('--initrd',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    a.add_argument('--seconds',type=float,default=22.0)
    x=a.parse_args()
    run(x.image,x.initrd,x.out,x.seconds)

if __name__=='__main__':
    main()
