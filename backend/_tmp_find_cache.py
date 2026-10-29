import docling, os

out = open("_cache_report.txt", "w", encoding="utf-8")
def log(*a):
    out.write(" ".join(str(x) for x in a) + "\n")

# (1) HuggingFace hub default cache paths (pure-python constants)
try:
    from huggingface_hub.constants import HF_HOME, HF_HUB_CACHE
    log("HF_DEFAULT_HOME =", HF_HOME)
    log("HF_DEFAULT_HUB_CACHE =", HF_HUB_CACHE)
except Exception as e:
    log("huggingface_hub constants err:", repr(e))

root = os.path.dirname(docling.__file__)
rel = lambda p: os.path.relpath(p, root)

# (2) PdfPipelineOptions.artifacts_path — find its dataclass default
log("\n=== artifacts_path references in installed docling ===")
for d, _, fs in os.walk(root):
    for f in fs:
        if not f.endswith(".py"):
            continue
        p = os.path.join(d, f)
        try:
            lines = open(p, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        for i, l in enumerate(lines):
            if "artifacts_path" in l:
                log("%s:%d: %s" % (rel(p), i + 1, l.strip()))

# (3) default cache/dir home resolution inside docling
import re
kw = re.compile(r"(cache_dir|default_cache|models_dir|DoclingCache|cache_home|os\.path\.expanduser|Path\.home)")
log("\n=== docling cache/default-cache resolution lines ===")
seen = set()
for d, _, fs in os.walk(root):
    for f in fs:
        if not f.endswith(".py"):
            continue
        p = os.path.join(d, f)
        try:
            lines = open(p, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        for i, l in enumerate(lines):
            if kw.search(l):
                key = (rel(p), i + 1)
                if key in seen:
                    continue
                seen.add(key)
                log("%s:%d: %s" % (rel(p), i + 1, l.strip()))

out.close()
print("WROTE _cache_report.txt")
