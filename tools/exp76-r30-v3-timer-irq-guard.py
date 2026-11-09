# Python 3 / Ubuntu 24.04 Actions / explicit timer softirq IRQ-state hypothesis for EXP76 R30 V3, QEMU ONLY
"""Guard the upstream RT140 irq_work_tick_soft call with local IRQ save/restore.

The V3 Image from 42649956950 hit a hard BUG at irq_work_tick_soft+0xa8:
the function executes BRK when the caller has DAIF.I clear. The
run_timer_softirq caller executes in ktimersoftd context with IRQs enabled.
Isolate this additional source change to the V3 workflow, not the proven
page-allocator-only R30 boot.
"""
from pathlib import Path
import argparse,difflib,hashlib,json,subprocess

FILE="kernel/time/timer.c"
FUNC="static __latent_entropy void run_timer_softirq(struct softirq_action *h)"

def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tree",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    tree=a.tree.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    path=tree/FILE
    before=path.read_text()
    assert FUNC in before,"pinned RT timer callback missing"
    pos=before.index(FUNC);stop=before.find("\n}\n",pos)
    assert stop>pos,"function closing brace not located"
    section=before[pos:stop+3]
    old="\tirq_work_tick_soft();"
    assert section.count(old)==1,f"expected one soft irq_work call in timer callback, got {section.count(old)}"
    assert "#include <linux/interrupt.h>" in before or "#include <linux/irq_work.h>" in before,"IRQ state header not found"
    changed=section.replace(old,"\t/* PREEMPT_RT ktimersoftd calls this with IRQ enabled; irq_work requires disabled. */\n\t{\n\t\tunsigned long irqflags;\n\t\tlocal_irq_save(irqflags);\n\t\tirq_work_tick_soft();\n\t\tlocal_irq_restore(irqflags);\n\t}",1)
    after=before[:pos]+changed+before[stop+3:]
    assert after!=before
    path.write_text(after)
    diff="".join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
                     fromfile="a/"+FILE,tofile="b/"+FILE))
    (out/"timer-v3-irq-guard.patch").write_text(diff)
    subprocess.run(["git","-C",str(tree),"diff","--check"],check=True)
    result={"schema_version":1,"stage":"R30_V3_TIMER_IRQ_STATE_TEST_ONLY",
            "prior_bug":"irq_work_tick_soft+0xa8 BRK#0x800 when !irqs_disabled in ktimersoftd",
            "changed_source":FILE,"source_sha256_before":hashlib.sha256(before.encode()).hexdigest(),
            "source_sha256_after":h(path),"patch_sha256":h(out/"timer-v3-irq-guard.patch"),
            "additional_to_3_stage82_mm_hunks":True,"boot_retested":False,"flash_ready":False}
    (out/"timer-v3-source-guard.json").write_text(json.dumps(result,indent=2)+"\n")
    print("R30_V3_TIMER_GUARD",json.dumps(result,indent=2),flush=True)
if __name__=="__main__":
    main()
