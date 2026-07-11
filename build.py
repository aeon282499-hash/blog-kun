# -*- coding: utf-8 -*-
"""
自作静的サイトジェネレーター（ブログ君）
articles/*.md と pages/*.md を読んで dist/ にHTMLを生成する。
依存: markdown, jinja2 のみ。
"""
import json
import re
import shutil
import sys
from datetime import datetime, date
from pathlib import Path
from urllib.parse import quote

import markdown
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent
DIST = ROOT / "dist"

# ---------------------------------------------------------------
# サイト設定（ここを書き換えればサイト名などを変更できる）
# ---------------------------------------------------------------
SITE = {
    "name": "コード書けないけどAIで作ってみた",
    "tagline": "プログラミング未経験がClaude Codeを「コピペだけ」で使い倒す実験ブログ",
    "url": "https://aeon282499-hash.github.io/blog-kun",  # 末尾スラッシュなし
    "base_path": "/blog-kun",  # ルート公開なら "" にする
    "author": "星野（仮）",
    "description": "コードが書けない運営者が、Claude CodeなどのAIツールをコピペ指示だけでどこまで使えるかを実体験ベースで発信するブログです。",
}

AD_DISCLOSURE = "※本記事にはアフィリエイト広告を含みます"


def u(path: str) -> str:
    """サイト内URLを base_path 付きで返す（日本語はエンコード）"""
    return SITE["base_path"] + quote(path)


def full_url(path: str) -> str:
    return SITE["url"] + quote(path)


# ---------------------------------------------------------------
# frontmatter 付き markdown の読み込み
# ---------------------------------------------------------------
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def parse_md_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        raise ValueError(f"frontmatterがありません: {path.name}")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip().strip('"')
    meta["body_md"] = m.group(2)
    meta["slug"] = path.stem
    return meta


def make_markdown():
    return markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "nl2br"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
    )


def render_toc(toc_tokens) -> str:
    """h2/h3 から目次HTMLを生成（h2が2つ未満なら空文字）"""
    h2s = [t for t in toc_tokens if t["level"] == 2]
    if len(h2s) < 2:
        return ""
    items = []
    for t in h2s:
        items.append(f'<li><a href="#{t["id"]}">{t["name"]}</a>')
        subs = [c for c in t.get("children", []) if c["level"] == 3]
        if subs:
            items.append("<ul>")
            for c in subs:
                items.append(f'<li><a href="#{c["id"]}">{c["name"]}</a></li>')
            items.append("</ul>")
        items.append("</li>")
    return '<nav class="toc"><div class="toc-title">目次</div><ul>' + "".join(items) + "</ul></nav>"


def safe_jsonld(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


# ---------------------------------------------------------------
# ビルド本体
# ---------------------------------------------------------------
def main():
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    # static コピー
    shutil.copytree(ROOT / "static", DIST / "static")

    today = date.today().isoformat()
    sitemap_entries = []  # (loc, lastmod)

    # ---- 記事の読み込み ----
    articles = []
    for f in sorted((ROOT / "articles").glob("*.md")):
        a = parse_md_file(f)
        for key in ("title", "date", "category", "description"):
            if key not in a:
                raise ValueError(f"{f.name}: frontmatterに {key} がありません")
        a["tags"] = [t.strip() for t in a.get("tags", "").split(",") if t.strip()]
        a["url_path"] = f"/articles/{a['slug']}/"
        a["url"] = u(a["url_path"])
        a["full_url"] = full_url(a["url_path"])
        datetime.strptime(a["date"], "%Y-%m-%d")  # 形式チェック
        articles.append(a)
    articles.sort(key=lambda a: (a["date"], a["slug"]), reverse=True)

    # ---- カテゴリ ----
    categories = {}
    for a in articles:
        categories.setdefault(a["category"], []).append(a)
    for cat in categories:
        for a in categories[cat]:
            a["category_url"] = u(f"/category/{cat}/")

    base_ctx = {
        "site": SITE,
        "u": u,
        "categories": sorted(categories.keys()),
        "category_url": lambda c: u(f"/category/{c}/"),
        "current_year": date.today().year,
    }

    # ---- 記事ページ ----
    tpl_article = env.get_template("article.html")
    for a in articles:
        md = make_markdown()
        body_html = md.convert(a["body_md"])
        toc_html = render_toc(md.toc_tokens)

        # 関連記事: 同カテゴリの最新3件（足りなければ他カテゴリの最新で補完）
        related = [r for r in categories[a["category"]] if r["slug"] != a["slug"]][:3]
        if len(related) < 3:
            extra = [r for r in articles if r["slug"] != a["slug"] and r not in related]
            related += extra[: 3 - len(related)]

        jsonld = safe_jsonld({
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": a["title"],
            "description": a["description"],
            "datePublished": a["date"],
            "author": {"@type": "Person", "name": SITE["author"]},
            "mainEntityOfPage": a["full_url"],
        })
        breadcrumb = safe_jsonld({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "ホーム", "item": SITE["url"] + "/"},
                {"@type": "ListItem", "position": 2, "name": a["category"],
                 "item": full_url(f"/category/{a['category']}/")},
                {"@type": "ListItem", "position": 3, "name": a["title"], "item": a["full_url"]},
            ],
        })

        out = DIST / "articles" / a["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(tpl_article.render(
            **base_ctx,
            article=a,
            body_html=body_html,
            toc_html=toc_html,
            related=related,
            ad_disclosure=AD_DISCLOSURE,
            page_title=f"{a['title']} | {SITE['name']}",
            page_description=a["description"],
            canonical=a["full_url"],
            og_type="article",
            jsonld_blocks=[jsonld, breadcrumb],
        ), encoding="utf-8")
        sitemap_entries.append((a["full_url"], a["date"]))

    # ---- トップページ ----
    tpl_index = env.get_template("index.html")
    jsonld_site = safe_jsonld({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE["name"],
        "url": SITE["url"] + "/",
        "description": SITE["description"],
    })
    (DIST / "index.html").write_text(tpl_index.render(
        **base_ctx,
        articles=articles,
        categories_map=categories,
        page_title=f"{SITE['name']} | {SITE['tagline']}",
        page_description=SITE["description"],
        canonical=SITE["url"] + "/",
        og_type="website",
        jsonld_blocks=[jsonld_site],
    ), encoding="utf-8")
    sitemap_entries.append((SITE["url"] + "/", today))

    # ---- カテゴリページ ----
    tpl_cat = env.get_template("category.html")
    for cat, arts in categories.items():
        out = DIST / "category" / cat / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(tpl_cat.render(
            **base_ctx,
            category=cat,
            articles=arts,
            page_title=f"{cat} の記事一覧 | {SITE['name']}",
            page_description=f"「{cat}」カテゴリの記事一覧です。",
            canonical=full_url(f"/category/{cat}/"),
            og_type="website",
            jsonld_blocks=[],
        ), encoding="utf-8")
        sitemap_entries.append((full_url(f"/category/{cat}/"), today))

    # ---- 固定ページ ----
    tpl_page = env.get_template("page.html")
    for f in sorted((ROOT / "pages").glob("*.md")):
        p = parse_md_file(f)
        md = make_markdown()
        body_html = md.convert(p["body_md"])
        out = DIST / p["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(tpl_page.render(
            **base_ctx,
            page=p,
            body_html=body_html,
            page_title=f"{p['title']} | {SITE['name']}",
            page_description=p.get("description", SITE["description"]),
            canonical=full_url(f"/{p['slug']}/"),
            og_type="website",
            jsonld_blocks=[],
        ), encoding="utf-8")
        sitemap_entries.append((full_url(f"/{p['slug']}/"), today))

    # ---- sitemap.xml / robots.txt ----
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in sitemap_entries:
        lines.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    lines.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")

    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE['url']}/sitemap.xml\n", encoding="utf-8")

    # 404ページ（トップへの導線）
    tpl_404 = env.get_template("404.html")
    (DIST / "404.html").write_text(tpl_404.render(
        **base_ctx,
        page_title=f"ページが見つかりません | {SITE['name']}",
        page_description=SITE["description"],
        canonical=SITE["url"] + "/",
        og_type="website",
        jsonld_blocks=[],
    ), encoding="utf-8")

    print(f"OK: articles={len(articles)} categories={len(categories)} "
          f"pages={len(list((ROOT / 'pages').glob('*.md')))} -> dist/")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"BUILD ERROR: {e}", file=sys.stderr)
        sys.exit(1)
