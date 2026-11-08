# -*- coding: utf-8 -*-
"""rubric / 六元素 判分实验运行器（可携带上云）

- 单断言协议（推荐）：每条断言一次调用；开卷只给该点所引章节
- 六条一次判协议（原设计）：每题一次调用
- 默认关推理（thinking=disabled）：deepseek-flash 是推理模型，不关会把 max_tokens
  全烧在 reasoning_content 上、content 恒空（2026-11-09 踩过，见验证报告）

环境变量：DEEPSEEK_API_KEY
用法：
  python run_rubric.py --set mcq/reasoning/题目_多跳六元素_rubric92_平衡掩码.json \
      --protocol single --arms closed,chapter --workers 10 --out rbvs.jsonl
"""
import os, re, json, time, argparse, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.environ.get("RUBRIC_MODEL", "deepseek-flash")
CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn2int(s):
    s = s.strip()
    if s in CN:
        return CN[s]
    if s.startswith("十"):
        return 10 + (CN.get(s[1:], 0) if len(s) > 1 else 0)
    if "十" in s:
        a, b = s.split("十")
        return CN.get(a, 0) * 10 + (CN.get(b, 0) if b else 0)
    return None


def split_chapters(txt):
    lines = txt.split("\n")
    heads = []
    for i, ln in enumerate(lines):
        m = re.match(r"^#{1,2}\s+第([一二三四五六七八九十]+)章", ln)
        if m:
            heads.append((i, cn2int(m.group(1))))
    ch = {}
    for k, (i, num) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        ch[num] = "\n".join(lines[i:end])
    return ch


def chat(messages, max_tokens=200, thinking="disabled"):
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens,
            "temperature": 0.0}
    if thinking:
        body["thinking"] = {"type": thinking}
    req = urllib.request.Request(API + "/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"]})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode("utf-8"))
    ch = d["choices"][0]
    return (ch["message"].get("content") or ""), ch.get("finish_reason")


def parse_yes(tx):
    t = (tx or "").replace("*", "").strip()
    if not t:
        return None
    h = t[:12]
    if "不符合" in h or "不是" in h or "错误" in h:
        return False
    if h.startswith("是") or "正确" in h or "符合" in h:
        return True
    if h.startswith("否") or "不符合" in h:
        return False
    m = re.search(r"(是|否)", t)
    return None if not m else (m.group(1) == "是")


SYS_C = "判断这条描述是否完全符合原文。你手里没有原文，只能凭印象判断，不要拒答。只回答一个字：是 或 否。"
SYS_O = "依据材料判断这条描述是否完全符合原文。只回答一个字：是 或 否。不要解释。"
SYS_BC = "判断下列每条断言是否符合原文。你手里没有原文，只能凭印象判断，不要拒答。对每条输出「是」或「否」，一行一条。格式示例：\n1: 是\n2: 否"
SYS_BO = "依据材料判断下列每条断言是否完全符合原文。对每条输出「是」或「否」，一行一条。格式示例：\n1: 是\n2: 否"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--protocol", default="single", choices=["single", "batch"])
    ap.add_argument("--arms", default="closed,chapter")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    items = json.load(open(args.set, encoding="utf-8"))
    chapters = split_chapters(open(args.corpus, encoding="utf-8").read())
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    def chapter_of(stmt):
        m = re.match(r"^第(\d+)章", stmt.strip())
        return chapters.get(int(m.group(1)), "") if m else ""

    def ask_single(arm, stmt):
        if arm == "closed":
            u = "【描述】%s\n\n即使没有原文，也请凭印象判断：这条描述是否完全符合原文？只回答「是」或「否」。" % stmt
            return [{"role": "system", "content": SYS_C}, {"role": "user", "content": u}]
        u = "【材料】\n%s\n\n【描述】%s\n\n这条描述是否完全符合原文？只回答「是」或「否」。" % (chapter_of(stmt), stmt)
        return [{"role": "system", "content": SYS_O}, {"role": "user", "content": u}]

    def ask_batch(arm, stmts):
        lst = "\n".join("%d: %s" % (i + 1, s) for i, s in enumerate(stmts))
        if arm == "closed":
            u = "断言：\n%s\n\n即使没有原文，也请凭印象判断，逐条给出「是/否」。" % lst
            return [{"role": "system", "content": SYS_BC}, {"role": "user", "content": u}]
        u = "【材料】\n%s\n\n断言：\n%s\n\n逐条判断是否符合原文，给出「是/否」。" % (chapter_of(stmts[0]), lst)
        return [{"role": "system", "content": SYS_BO}, {"role": "user", "content": u}]

    def call(msgs, tries=3):
        for i in range(tries):
            try:
                tx, fin = chat(msgs)
                if tx.strip():
                    return tx
            except Exception:
                pass
            time.sleep(1 + i)
        return ""

    rows = []

    def work_single(t):
        stmt, truth, arm, qid, pi = t
        tx = call(ask_single(arm, stmt))
        return {"qid": qid, "pi": pi, "arm": arm, "truth": truth, "got": parse_yes(tx), "stmt": stmt}

    def work_batch(t):
        stmts, truths, arm, qid = t
        tx = call(ask_batch(arm, stmts), max_tokens=800)
        t2 = tx.replace("*", "")
        got = [None] * len(stmts)
        for i in range(len(stmts)):
            m = re.search(r"(?:^|\n)\s*(?:\(|第)?\s*%d\s*(?:\)|条)?\s*[.、:：,，]?\s*(是|否)" % (i + 1), t2)
            if m:
                got[i] = (m.group(1) == "是")
        return {"qid": qid, "arm": arm, "truth": truths, "got": got}

    tasks = []
    for q in items:
        pts = q.get("points") or [{"stmt": q["stmt"], "answer": q["answer"]}]
        for arm in arms:
            if args.protocol == "single":
                for pi, p in enumerate(pts):
                    tasks.append((p["stmt"], bool(p["answer"]), arm, q.get("qid"), pi))
            else:
                tasks.append(([p["stmt"] for p in pts], [bool(p["answer"]) for p in pts], arm, q.get("qid")))

    t0 = time.time()
    with open(args.out, "w", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=args.workers) as ex:
        fn = work_single if args.protocol == "single" else work_batch
        for i, r in enumerate(ex.map(fn, tasks), 1):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            if i % 100 == 0:
                print("  %d/%d（%.0fs）" % (i, len(tasks), time.time() - t0), flush=True)
    print("作答已写:", args.out)
    print("判分：python grade_rubric.py --answers %s --protocol %s" % (args.out, args.protocol))


if __name__ == "__main__":
    main()
