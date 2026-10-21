# Minimal STEP (ISO 10303-21) entity loader: id -> (TYPE, args-bytes). Joins multi-line entities.
import re
HEAD=re.compile(rb'#(\d+)\s*=\s*([A-Z_0-9]*)\s*\(')
def load(path,keep=None):
    db={};buf=b''
    with open(path,'rb') as f:
        data=False
        for line in f:
            if not data:
                if line.strip()==b'DATA;':data=True
                continue
            s=line.strip()
            if not s:continue
            buf+=s
            if not buf.endswith(b';'):continue
            m=HEAD.match(buf)
            if m:
                typ=m.group(2)
                if keep is None or typ in keep or typ==b'':
                    db[int(m.group(1))]=(typ,buf[m.end()-1:-1])
            buf=b''
    return db
REF=re.compile(rb'#(\d+)')
def refs(args):return [int(x) for x in REF.findall(args)]
NUM=re.compile(rb'[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?')
def nums(args):return [float(x) for x in NUM.findall(args)]
def split_top(args):
    # split "(a,b,(c,d),e)" top-level args
    s=args.strip()
    if s.startswith(b'(') and s.endswith(b')'):s=s[1:-1]
    out=[];depth=0;cur=b'';q=False
    for ch in s:
        c=bytes([ch])
        if c==b"'":q=not q
        if not q:
            if c==b'(':depth+=1
            elif c==b')':depth-=1
            elif c==b',' and depth==0:out.append(cur);cur=b'';continue
        cur+=c
    out.append(cur);return [x.strip() for x in out]
