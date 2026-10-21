#!/usr/bin/env python3
"""Build site/learn.html from site/content/*.md (technical-books style chapters).

Markdown subset: front matter (title), :::message blocks, ##/### headings,
dialogue lines "**名前**：本文", "- " / "1. " lists, "> " quotes, tables,
paragraphs, inline **bold**. "### コラム ..." sections render as a box.
"""
import html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
TEMPLATE = ROOT / "learn-template.html"
OUT = ROOT / "learn.html"

SPEAKERS = {"ずんだもん": "z", "めたん": "m", "四国めたん": "m"}
NAME = {"z": "ずんだもん", "m": "四国めたん"}

def face(who, text):
    """Pick a bust image (assets/*_bust.png) from the line's content."""
    if who == "z":
        if re.search(r"(わかった|なるほど|できた|できるようになった|楽しみ|やったー|合格|見事|覚えたのだ|言えるようになった)", text): return "zunda_happy"
        if re.search(r"(困|不安|心配|わからない|あやふや|ごちゃごちゃ|覚えきれない|追いつかない|嫌な予感)", text): return "zunda_trouble"
        if "？" in text or "?" in text: return "zunda_think"
        if re.search(r"(つまり|ということは|じゃあ|なのだ。$)", text) and len(text) > 60: return "zunda_idea"
        return "zunda_normal"
    if re.search(r"(注意|誤り|ダメ|間違|引っかけ|入れ替えた|混ぜられ|気をつけ)", text): return "metan_warn"
    if re.search(r"(完璧|合格|お疲れさま|見事|正解です|安心)", text): return "metan_smile"
    if re.search(r"(^|[。、])(では|まず|流れ|整理|表で|3つ|2つ|ポイント)", text) or len(text) > 120: return "metan_point"
    return "metan_normal"

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
                out.append(f"<h{level}>{inline(text)}</h{level}>")
            i += 1; continue
        d = re.match(r"^\*\*(ずんだもん|四国めたん|めたん)\*\*[：:]\s*(.*)$", ln)
        if d:
            who = SPEAKERS[d.group(1)]
            out.append(f"<div class=\"line {who}\"><img class=\"av {who}\" src=\"assets/{face(who, d.group(2))}_bust.png\" alt=\"\" width=\"44\" height=\"44\" loading=\"lazy\"><div class=\"bubble\"><span class=\"who\">{NAME[who]}</span>{inline(d.group(2))}</div></div>")
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

def main():
    chapters = []
    for p in sorted(CONTENT.glob("*.md")):
        title, body = convert(p.read_text(encoding="utf-8"))
        n = int(p.stem)
        appendix = "付録" in title
        z = len(re.findall(r'class="line z"', body)); mm = len(re.findall(r'class="line m"', body))
        chapters.append({"n": n, "title": title, "html": body, "appendix": appendix, "chars": len(p.read_text(encoding="utf-8")), "z": z, "m": mm})
    tpl = TEMPLATE.read_text(encoding="utf-8")
    data = json.dumps([{k: c[k] for k in ("title", "html", "appendix")} for c in chapters], ensure_ascii=False)
    data = data.replace("</script", "<\\/script")
    OUT.write_text(tpl.replace("/*__CHAPTERS__*/", "const CH = " + data + ";"), encoding="utf-8")
    for c in chapters:
        print(f"{c['n']:02d} {c['title']}: {c['chars']} chars, ずんだもん {c['z']} / めたん {c['m']}")
    print("total chars", sum(c["chars"] for c in chapters), "->", OUT.name, OUT.stat().st_size, "bytes")

if __name__ == "__main__":
    main()
