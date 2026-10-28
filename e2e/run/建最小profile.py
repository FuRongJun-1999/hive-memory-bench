import json, shutil, os
from pathlib import Path
root = Path(os.path.expanduser("~/.dsh/profiles"))
src = root / "lingshu-qq"
dst = root / "lingshu-test"
print("源存在:", src.exists(), "| 目标存在:", dst.exists())
if dst.exists():
    shutil.rmtree(dst)
# 复制（不含 node_modules，用 pnpm 重装更干净；先复制配置）
dst.mkdir(parents=True)
for name in ("cordis.yml", "cordis.patch.yml", "pnpm-workspace.yaml"):
    s = src / name
    if s.exists():
        shutil.copy2(s, dst / name)
pkg = json.loads((src / "package.json").read_text(encoding="utf-8"))
pkg["name"] = "dsh-profile-lingshu-test"
# 去掉 qqbot
pkg["dependencies"] = {k: v for k, v in pkg["dependencies"].items() if "qqbot" not in k}
pkg["dsh"]["profile"]["bundles"] = [b for b in pkg["dsh"]["profile"]["bundles"] if "qqbot" not in b]
(dst / "package.json").write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")
print("已建:", dst)
print("bundles:", pkg["dsh"]["profile"]["bundles"])
print("deps:", list(pkg["dependencies"]))