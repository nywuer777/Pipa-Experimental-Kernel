# Python 3 / Ubuntu 24.04 GH Actions / apply 3 exact Stage82 RT140 mm/page_alloc.c pairing hunks to temporary E404 RT tree / NO FLASH
"""Pinned Stage82 page allocator fix: local_lock acquire/release must balance."""
from pathlib import Path
import argparse,difflib,hashlib,json,re,subprocess

SOURCE="mm/page_alloc.c"
BEFORE_SHA="d416b26c1068bf4c305890bea1a04e5db4c4a90faa6982a21353baf1b14307df"
REJECT_SHA="bc50f79ee420962007d789a6d8f652e550e2cf324b6956f49f881b03f833c4c6"
CALLS={"__free_pages_ok":2,"rmqueue_pcplist":1,"rmqueue":2}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def one(text,old,new,what):
    count=text.count(old)
    assert count==1,f"{what}: expected 1 exact source occurrence got {count}"
    return text.replace(old,new,1)

def function_section(src,identifier,end_marker):
    pos=src.find(identifier)
    assert pos>=0,identifier+" not found"
    end=src.find(end_marker,pos+len(identifier))
    assert end>pos,identifier+" end missing"
    return pos,end,src[pos:end]

def replace_section(src,name,end,changes):
    lo,hi,chunk=function_section(src,name,end)
    for old,new,tag in changes:
        chunk=one(chunk,old,new,tag)
    return src[:lo]+chunk+src[hi:]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tree",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();tree=a.tree.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=tree/SOURCE;reject=tree/(SOURCE+".rej")
    raw=source.read_bytes(); assert sha(raw)==BEFORE_SHA,("unexpected reconstructed mm source",sha(raw))
    assert sha(reject.read_bytes())==REJECT_SHA,"Stage82 reject changed"
    rej=reject.read_text();assert len(re.findall(r"(?m)^@@ ",rej))==3,"expected 3 rejects"
    markers=(
      "+\tlocal_lock_irqsave(pa_lock, flags);",
      "+\tlocal_unlock_irqrestore(pa_lock, flags);",
    )
    for mark in markers: assert mark in rej,f"RT140 reject missing {mark}"
    src=raw.decode()
    modified=replace_section(src,"static void __free_pages_ok(struct page *page, unsigned int order)\n{",
    "static void __free_pages_boot_core",[
      ("\tlocal_irq_save(flags);","\tlocal_lock_irqsave(pa_lock, flags);","__free_pages_ok acquire"),
      ("\tlocal_irq_restore(flags);","\tlocal_unlock_irqrestore(pa_lock, flags);","__free_pages_ok release")
    ])
    modified=replace_section(modified,"static struct page *rmqueue_pcplist(","/*\n * Allocate a page from the given zone.",[
      ("\tlocal_irq_save(flags);","\tlocal_lock_irqsave(pa_lock, flags);","rmqueue_pcplist acquire")
    ])
    modified=replace_section(modified,"struct page *rmqueue(struct zone *preferred_zone,",
      "/*\n * A watermark",[
      ("\tlocal_irq_restore(flags);","\tlocal_unlock_irqrestore(pa_lock, flags);","rmqueue success restore"),
      ("\tlocal_irq_restore(flags);","\tlocal_unlock_irqrestore(pa_lock, flags);","rmqueue failed restore"),
    ])
    assert modified!=src
    source.write_text(modified)
    assert source.read_text()==modified
    diff="".join(difflib.unified_diff(src.splitlines(True),modified.splitlines(True),
             fromfile="a/mm/page_alloc.c",tofile="b/mm/page_alloc.c"))
    assert diff.count("@@")==6,"expected exactly 3 unified diff hunks"
    assert diff.count("+\tlocal_lock_irqsave(pa_lock, flags);")==2
    assert diff.count("+\tlocal_unlock_irqrestore(pa_lock, flags);")==3
    assert diff.count("-\tlocal_irq_save(flags);")==2
    assert diff.count("-\tlocal_irq_restore(flags);")==3
    dpath=out/"mm-page-alloc-stage82-fix.patch";dpath.write_text(diff)
    # confirm exactly 3 source function areas edited and no .rej modifications
    assert sha(reject.read_bytes())==REJECT_SHA
    subprocess.run(["git","-C",str(tree),"diff","--check"],check=True)
    report={
      "schema_version":1,"stage":"EXP76_R30_PA_LOCK_FIX",
      "upstream":"4.19.325-rt140", "target":SOURCE,
      "rejected_stage82_hunks":3,"applied_hunks":3,
      "functions":["__free_pages_ok","rmqueue_pcplist","rmqueue"],
      "target_pre_sha256":BEFORE_SHA,
      "target_post_sha256":sha(source.read_bytes()),
      "reject_sha256":REJECT_SHA,
      "diff_sha256":sha(dpath.read_bytes()),
      "modified_line_count":5, "only_page_allocator_code_changed_by_r30":True,
      "rejects_deleted":False,"config_mutated":False,
      "flash_ready":False
    }
    (out/"step3-fix.json").write_text(json.dumps(report,indent=2)+"\n")
    print("R30_MM_APPLIED",json.dumps(report,indent=2),flush=True)
    print("R30_SOURCE_DIFF_BEGIN\n"+diff+"R30_SOURCE_DIFF_END",flush=True)
if __name__=="__main__":
    main()
