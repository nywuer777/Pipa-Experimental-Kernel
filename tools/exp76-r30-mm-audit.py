# Python 3 / Ubuntu 24.04 / EXP76 R30 Stage82 mm/page_alloc.c reject and RT140 hunk audit / NO FLASH
"""Extract exact page-allocator rejected hunks, upstream patch sections, and effective tree context."""
from pathlib import Path
import argparse, difflib, hashlib, json, re, subprocess

TARGET="mm/page_alloc.c"
TERMS=("free_unref_page", "free_pcppages_bulk", "get_page_from_freelist",
       "local_lock", "pa_lock", "spin_lock_irqsave", "rmqueue")

def sha(raw): return hashlib.sha256(raw).hexdigest()
def write(out,name,content):
    raw=content.encode() if isinstance(content,str) else content
    p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    return {"file":str(p.relative_to(out)),"sha256":sha(raw),"bytes":len(raw)}

def split_hunks(text):
    starts=[m.start() for m in re.finditer(r"(?m)^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@",text)]
    return [text[at:starts[i+1] if i+1<len(starts) else len(text)]
            for i,at in enumerate(starts)]

def patch_section(text,path):
    start=re.search(r"(?m)^diff --git a/"+re.escape(path)+r" b/"+re.escape(path)+r"$",text)
    if not start: return ""
    rest=text[start.start():]
    nextsec=re.search(r"(?m)^diff --git a/",rest[1:])
    return rest[:1+nextsec.start()] if nextsec else rest

def extract_source_context(src):
    lines=src.splitlines(keepends=True)
    found=set()
    spans=[]
    for i,line in enumerate(lines):
        if any(x in line for x in TERMS):
            lo=max(0,i-12);hi=min(len(lines),i+21)
            spans.append((lo,hi))
    spans.sort()
    blocks=[]
    for lo,hi in spans:
        if blocks and lo<=blocks[-1][1]:
            blocks[-1]=(blocks[-1][0],max(hi,blocks[-1][1]))
        else:
            blocks.append((lo,hi))
    return "\n".join("## source lines %d-%d\n"%(lo+1,hi)+
                     "".join("%5d %s"%(k+1,lines[k]) for k in range(lo,hi))
                     for lo,hi in blocks)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--tree",type=Path,required=True)
    a.add_argument("--patch",type=Path,required=True)
    a.add_argument("--index",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    q=a.parse_args()
    tree=q.tree.resolve();out=q.out.resolve();out.mkdir(parents=True,exist_ok=True)
    idx=json.loads(q.index.read_text())
    entries=idx["entries"]
    mm=[e for e in entries if e["source"].startswith("mm/")]
    page=[e for e in mm if e["source"]==TARGET]
    matching=[{"source":e["source"],"hunks":e["hunk_count"],"reject_sha256":e["reject_sha256"]}
              for e in mm if any(s in json.dumps(e) for s in TERMS)]
    patch=q.patch.read_text(errors="replace")
    upstream=patch_section(patch,TARGET)
    current=(tree/TARGET).read_text()
    base=subprocess.run(["git","-C",str(tree),"show","HEAD:"+TARGET],check=True,
                        capture_output=True,text=True).stdout
    rej=tree/(TARGET+".rej")
    raw=rej.read_text(errors="replace") if rej.exists() else ""
    hunks=split_hunks(raw)
    upstream_hunks=split_hunks(upstream)
    related_reject=[{"index":i+1,"header":h.splitlines()[0],
                     "matches":[x for x in TERMS if x in h],
                     "text":h} for i,h in enumerate(hunks) if any(x in h for x in TERMS)]
    related_upstream=[{"index":i+1,"header":h.splitlines()[0],
                       "matches":[x for x in TERMS if x in h],
                       "text":h} for i,h in enumerate(upstream_hunks) if any(x in h for x in TERMS)]
    manifest=[]
    for name,content in [
      ("mm-reject-full.patch",raw),
      ("mm-upstream-rt140.patch",upstream),
      ("mm-relevant-reject-hunks.patch","\n".join(h["text"] for h in related_reject)),
      ("mm-relevant-upstream-hunks.patch","\n".join(h["text"] for h in related_upstream)),
      ("mm-current-context.txt",extract_source_context(current)),
      ("mm-base-context.txt",extract_source_context(base)),
      ("mm-effective-vs-base.diff","".join(difflib.unified_diff(base.splitlines(True),current.splitlines(True),
          fromfile="E404-base-mm/page_alloc.c",tofile="RT-reconstructed-mm/page_alloc.c"))),
      ("current-mm-page-alloc.c",current),
      ("base-mm-page-alloc.c",base),
    ]:manifest.append(write(out,name,content))
    report={
       "schema_version":1,"stage":"R30_STAGE82_MM_HUNK_AUDIT",
       "stage82_total_hunks":idx["total_rejected_hunks"],
       "stage82_rejected_files":idx["remaining_rejected_files"],
       "page_alloc_reject_present":rej.exists(),
       "page_alloc_reject_hunk_count":len(hunks),
       "page_alloc_related_reject_hunk_count":len(related_reject),
       "page_alloc_related_reject_hunks":[{k:v for k,v in h.items() if k!="text"} for h in related_reject],
       "page_alloc_upstream_total_hunks":len(upstream_hunks),
       "page_alloc_upstream_related_hunk_count":len(related_upstream),
       "page_alloc_upstream_related_hunks":[{k:v for k,v in h.items() if k!="text"} for h in related_upstream],
       "stage82_mm_paths":[{"source":e["source"],"hunk_count":e["hunk_count"]} for e in mm],
       "stage82_mm_keyword_matches":matching,
       "current_mm_sha256":sha(current.encode()),
       "base_mm_sha256":sha(base.encode()),
       "page_alloc_reject_sha256":sha(raw.encode()) if raw else None,
       "official_patch_sha256":sha(q.patch.read_bytes()),
       "source_diff_file":"mm-effective-vs-base.diff",
       "artifact_files":manifest,"source_modified":False,"flash_ready":False}
    manifest.append(write(out,"step1-audit.json",json.dumps(report,indent=2)+"\n"))
    hlines=[h["text"] for h in related_reject]
    print("R30_MM_AUDIT",json.dumps({k:v for k,v in report.items() if k not in ("artifact_files",)},indent=2),flush=True)
    print("R30_REJECT_HUNKS_FULL_BEGIN\n"+"\n".join(hlines)+"\nR30_REJECT_HUNKS_FULL_END",flush=True)
    if not hlines:
        print("R30_REJECT_HUNKS=ZERO; UPSTREAM_RELATED_HUNKS_FOLLOW\n"+
              "\n".join(x["text"] for x in related_upstream)+
              "\nR30_UPSTREAM_HUNKS_END",flush=True)
if __name__=="__main__":
    main()
