"""Đọc bản tin Markdown mới nhất của Horizon (data/summaries/horizon-*.md)
và upsert từng mục vào bảng `papers` trên Supabase qua REST API."""

import glob
import os
import re

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

# Khớp mỗi mục Horizon sinh ra dạng:
# ## [Tiêu đề](url) ⭐️ 8.5/10
#
# Đoạn tóm tắt...
#
# rss · arXiv q-fin.TR · Jul 5, 14:30
ITEM_RE = re.compile(
    r"^## \[(?P<title>.*?)\]\((?P<url>.*?)\) ⭐️ (?P<score>[\d.]+|\?)/10\n"
    r"\n(?P<summary>.*?)\n\n(?P<source_line>[^\n]*·[^\n]*)\n",
    re.MULTILINE | re.DOTALL,
)


def latest_summary_file():
    files = sorted(glob.glob("data/summaries/horizon-*.md"))
    return files[-1] if files else None


def run_date_from_filename(path):
    m = re.search(r"horizon-(\d{4}-\d{2}-\d{2})-", os.path.basename(path))
    return f"{m.group(1)}T00:00:00Z" if m else None


def parse_items(markdown_text):
    items = []
    for m in ITEM_RE.finditer(markdown_text):
        score = m.group("score")
        items.append(
            {
                "title": m.group("title").strip(),
                "url": m.group("url").strip(),
                "score": None if score == "?" else float(score),
                "summary": m.group("summary").strip(),
                "source": m.group("source_line").split("·")[0].strip(),
            }
        )
    return items


def push(row):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/papers", headers=HEADERS, json=row, timeout=30
    )
    r.raise_for_status()


def main():
    path = latest_summary_file()
    if not path:
        print("Khong tim thay file ket qua Horizon trong data/summaries/.")
        return

    print(f"Doc file: {path}")
    text = open(path, encoding="utf-8").read()
    items = parse_items(text)
    published_at = run_date_from_filename(path)

    ok = 0
    for item in items:
        row = {
            "title": item["title"],
            "url": item["url"],
            "source": item["source"],
            "ai_score": item["score"],
            "ai_summary_vi": item["summary"],
            "published_at": published_at,
        }
        try:
            push(row)
            ok += 1
        except Exception as e:
            print("Bo qua 1 item loi:", item["url"], e)

    print(f"Da ghi {ok}/{len(items)} paper vao Supabase.")


if __name__ == "__main__":
    main()
