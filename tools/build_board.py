"""노트(0*/ *.md)를 읽어 한눈에 보는 보드(board.html)를 만든다.

사용: python3 tools/build_board.py   → 저장소 루트에 board.html 생성
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/juyoung7676love-afk/M1/blob/master/"


def inline(text, note_dir):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<em>\1</em>", text)

    def link(m):
        label, href = m.group(1), m.group(2)
        if href.startswith("http"):
            return f'<a href="{href}" target="_blank" rel="noopener">{label}</a>'
        path = href.split("#")[0]
        target = (note_dir / path).resolve().relative_to(ROOT).as_posix() if path else ""
        return f'<a href="#" class="note-link" data-note="{html.escape(target)}">{label}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)


def render(lines, note_dir):
    """노트에서 쓰는 마크다운 부분집합(목록·표·인용·소제목)을 HTML로 바꾼다."""
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
        elif s.startswith("### "):
            out.append(f"<h4>{inline(s[4:], note_dir)}</h4>")
            i += 1
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[1:] if not re.fullmatch(r"[-: ]*", "".join(r))]
            t = "<div class='tbl'><table><thead><tr>" + "".join(f"<th>{inline(c, note_dir)}</th>" for c in head) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c, note_dir)}</td>" for c in r) + "</tr>" for r in body)
            out.append(t + "</tbody></table></div>")
        elif s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            cls = " class='warn'" if "⚠️" in " ".join(buf) else ""
            out.append(f"<blockquote{cls}>{inline(' '.join(buf), note_dir)}</blockquote>")
        elif re.match(r"\s*([-*]|\d+\.)\s", line):
            items = []
            while i < len(lines) and re.match(r"\s*([-*]|\d+\.)\s", lines[i]):
                m = re.match(r"(\s*)([-*]|\d+\.)\s+(.*)", lines[i])
                items.append((len(m.group(1)), m.group(2) not in "-*", m.group(3)))
                i += 1
            out.append(render_list(items, note_dir))
        else:
            out.append(f"<p>{inline(s, note_dir)}</p>")
            i += 1
    return "".join(out)


def render_list(items, note_dir):
    html_out, stack = "", []
    for indent, ordered, text in items:
        while stack and indent < stack[-1][0]:
            html_out += f"</li></{stack.pop()[1]}>"
        if not stack or indent > stack[-1][0]:
            tag = "ol" if ordered else "ul"
            stack.append((indent, tag))
            html_out += f"<{tag}><li>"
        else:
            html_out += "</li><li>"
        html_out += inline(text, note_dir)
    while stack:
        html_out += f"</li></{stack.pop()[1]}>"
    return html_out


def plain(lines):
    t = " ".join(l.strip() for l in lines if l.strip() and not re.fullmatch(r"\|[-:| ]*\|", l.strip()))
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return re.sub(r"[*`>|#_]+|^\s*[-]\s|\s-\s", " ", t).replace("  ", " ").strip()


def parse(path):
    rel = path.relative_to(ROOT).as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    title, summary, created, updated = path.stem, "", "", ""
    body = []
    for line in lines:
        if line.startswith("# ") and title == path.stem:
            title = line[2:].strip()
        elif line.startswith("> 한 줄 요약:"):
            summary = line.split(":", 1)[1].strip()
        elif line.startswith("최초 작성:"):
            created = line.split(":", 1)[1].strip()
        elif line.startswith("업데이트:"):
            updated = line.split(":", 1)[1].strip()
        elif line.strip() == "---":
            continue
        else:
            body.append(line)
    if not created:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
        created = m.group(1) if m else ""

    sections, name, buf = [], "개요", []
    for line in body:
        if line.startswith("## "):
            if any(l.strip() for l in buf):
                sections.append((name, buf))
            name, buf = line[3:].strip(), []
        else:
            buf.append(line)
    if any(l.strip() for l in buf):
        sections.append((name, buf))

    cat = path.parent.name.split("_", 1)[1]
    note = {"path": rel, "title": title, "summary": summary, "cat": cat,
            "created": created, "updated": updated or created, "url": REPO_URL + rel}
    rows = []
    # "관련"·"출처" 섹션은 링크 모음이라 보드 행에서는 뺀다
    sections = [(n, b) for n, b in sections if not n.startswith(("관련", "출처"))]
    for idx, (sec, sl) in enumerate(sections):
        text = plain(sl)
        rows.append({"note": rel, "order": idx, "section": sec, "html": render(sl, path.parent),
                     "text": text, "flag": any(k in text for k in ("확인 필요", "채울 것", "정리 필요"))})
    return note, rows


def main():
    cats = [d.name.split("_", 1)[1] for d in sorted(ROOT.glob("[0-9][0-9]_*/")) if d.is_dir()]
    notes, rows = [], []
    for p in sorted(ROOT.glob("[0-9][0-9]_*/*.md")):
        if p.name == "README.md":
            continue
        n, r = parse(p)
        notes.append(n)
        rows.extend(r)
    data = json.dumps({"cats": cats, "notes": notes, "rows": rows}, ensure_ascii=False).replace("</", "<\\/")
    tpl = (ROOT / "tools" / "board_template.html").read_text(encoding="utf-8")
    (ROOT / "board.html").write_text(tpl.replace("/*__DATA__*/null", data), encoding="utf-8")
    print(f"board.html: 노트 {len(notes)}개, 항목 {len(rows)}개")


if __name__ == "__main__":
    main()
