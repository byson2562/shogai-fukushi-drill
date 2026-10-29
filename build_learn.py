#!/usr/bin/env python3
"""Build site/learn.html from site/content/*.md (technical-books style chapters).

Markdown subset: front matter (title), :::message blocks, ##/### headings,
dialogue lines "**名前**：本文", "- " / "1. " lists, "> " quotes, tables,
paragraphs, inline **bold**. "### コラム ..." sections render as a box.
Numbered sections ("## 1.2　...") get an id so the chapter-end check can link back.

Chapter-end checks live in content/checks/NN.json (same question format as
zundamon-drill: truefalse / choice / fill / essay, each with the section it refers to).
"""
import html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
CHECKS = CONTENT / "checks"
TEMPLATE = ROOT / "learn-template.html"
OUT = ROOT / "learn.html"

SPEAKERS = {"ずんだもん": "z", "めたん": "m", "四国めたん": "m"}
NAME = {"z": "ずんだもん", "m": "四国めたん"}

def esc(s):
    return html.escape(s, quote=False)

def inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s

def table(lines):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    rows = [r for r in rows if not all(re.fullmatch(r":?-+:?", c or "-") for c in r)]
    head, body = rows[0], rows[1:]
    out = ["<div class=\"tbl\"><table><thead><tr>"] + [f"<th>{inline(c)}</th>" for c in head] + ["</tr></thead><tbody>"]
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)

def convert(md):
    title = ""
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if m:
        fm = m.group(1)
        t = re.search(r'title:\s*"?(.*?)"?\s*$', fm, re.M)
        title = t.group(1) if t else ""
        md = md[m.end():]
    lines = md.split("\n")
    out = []
    i = 0
    column_open = False

    def close_column():
        nonlocal column_open
        if column_open:
            out.append("</div>")
            column_open = False

    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1; continue
        if ln.startswith(":::message"):
            buf = []; i += 1
            while i < len(lines) and not lines[i].startswith(":::"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append(f"<div class=\"msg\">{inline(' '.join(b for b in buf if b.strip()))}</div>")
            continue
        if ln.startswith("@["):
            i += 1; continue
        h = re.match(r"^(#{2,4})\s+(.*)$", ln)
        if h:
            level = len(h.group(1)); text = h.group(2).strip()
            close_column()
            if level == 3 and text.startswith("コラム"):
                column_open = True
                out.append(f"<div class=\"column\"><div class=\"column-title\"><span class=\"tag tag-blue\">コラム</span><span>{inline(text[len('コラム'):].strip(' 　'))}</span></div>")
            else:
                sec = re.match(r"^(\d+\.\d+)\s", text)
                attr = f' id="sec-{sec.group(1).replace(".", "-")}"' if sec and level == 2 else ""
                out.append(f"<h{level}{attr}>{inline(text)}</h{level}>")
            i += 1; continue
        d = re.match(r"^\*\*(ずんだもん|四国めたん|めたん)\*\*[：:]\s*(.*)$", ln)
        if d:
            who = SPEAKERS[d.group(1)]
            out.append(f"<p class=\"line {who}\"><span class=\"who\">{NAME[who]}</span>{inline(d.group(2))}</p>")
            i += 1; continue
        if ln.lstrip().startswith("|"):
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                buf.append(lines[i]); i += 1
            out.append(table(buf)); continue
        if re.match(r"^\s*[-*]\s+", ln):
            buf = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                buf.append(re.sub(r"^\s*[-*]\s+", "", lines[i])); i += 1
            out.append("<ul>" + "".join(f"<li>{inline(b)}</li>" for b in buf) + "</ul>"); continue
        if re.match(r"^\s*\d+\.\s+", ln):
            buf = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                buf.append(re.sub(r"^\s*\d+\.\s+", "", lines[i])); i += 1
            out.append("<ol>" + "".join(f"<li>{inline(b)}</li>" for b in buf) + "</ol>"); continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> ").rstrip()); i += 1
            out.append(f"<blockquote>{inline(' '.join(buf))}</blockquote>"); continue
        # paragraph
        buf = [ln]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{2,4}\s|\*\*(ずんだもん|四国めたん|めたん)\*\*|\||\s*[-*]\s|\s*\d+\.\s|>|:::|@\[)", lines[i]):
            buf.append(lines[i]); i += 1
        out.append(f"<p>{inline(' '.join(b.strip() for b in buf))}</p>")
    close_column()
    return title, "".join(out)

def load_check(stem, body):
    p = CHECKS / f"{stem}.json"
    if not p.exists():
        return None
    qs = json.loads(p.read_text(encoding="utf-8"))["questions"]
    secs = set(s.replace("-", ".") for s in re.findall(r'id="sec-([\d-]+)"', body))
    errors = []
    for i, q in enumerate(qs, 1):
        need = {"truefalse": ("q", "answer", "explain"), "choice": ("q", "choices", "answer", "explain"),
                "fill": ("q", "accept", "explain"), "essay": ("q", "model", "points")}.get(q.get("type"))
        if need is None:
            errors.append(f"Q{i}: unknown type {q.get('type')}"); continue
        errors += [f"Q{i}: missing {k}" for k in need + ("ref",) if k not in q]
        if q["type"] == "truefalse" and not isinstance(q.get("answer"), bool):
            errors.append(f"Q{i}: answer must be true/false")
        if q["type"] == "choice" and not (isinstance(q.get("answer"), int) and 0 <= q["answer"] < len(q.get("choices", []))):
            errors.append(f"Q{i}: answer out of range")
        if q.get("ref") not in secs:
            errors.append(f"Q{i}: ref {q.get('ref')} is not a section of this chapter")
    if errors:
        sys.exit(f"{p.name}: " + "; ".join(errors))
    return qs

def main():
    chapters = []
    for p in sorted(CONTENT.glob("*.md")):
        title, body = convert(p.read_text(encoding="utf-8"))
        n = int(p.stem)
        appendix = "付録" in title
        z = len(re.findall(r'class="line z"', body)); mm = len(re.findall(r'class="line m"', body))
        check = load_check(p.stem, body)
        chapters.append({"n": n, "title": title, "html": body, "appendix": appendix, "check": check, "chars": len(p.read_text(encoding="utf-8")), "z": z, "m": mm})
    tpl = TEMPLATE.read_text(encoding="utf-8")
    data = json.dumps([{k: c[k] for k in ("title", "html", "appendix", "check")} for c in chapters], ensure_ascii=False)
    data = data.replace("</script", "<\\/script")
    OUT.write_text(tpl.replace("/*__CHAPTERS__*/", "const CH = " + data + ";"), encoding="utf-8")
    for c in chapters:
        q = f", check {len(c['check'])}問" if c["check"] else ""
        print(f"{c['n']:02d} {c['title']}: {c['chars']} chars, ずんだもん {c['z']} / めたん {c['m']}{q}")
    print("total chars", sum(c["chars"] for c in chapters), "->", OUT.name, OUT.stat().st_size, "bytes")

if __name__ == "__main__":
    main()
