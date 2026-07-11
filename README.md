# ブログ君 — コード書けないけどAIで作ってみた

Claude Codeへのコピペ指示だけで運営する実験ブログ。

- 公開URL: https://aeon282499-hash.github.io/blog-kun/
- 仕組み: `articles/` にmarkdownを置いてpushすると、GitHub Actionsが `build.py` でHTMLに変換してGitHub Pagesへ自動デプロイ

## 構成

```
articles/   記事（markdown・frontmatter付き）
pages/      固定ページ（プロフィール・プライバシーポリシー・お問い合わせ）
templates/  HTMLテンプレート（Jinja2）
static/     CSS・画像
build.py    ビルドスクリプト（依存: markdown, jinja2）
.github/workflows/deploy.yml  自動ビルド&デプロイ
```

## 記事のfrontmatter

```
---
title: 記事タイトル
date: 2026-07-11
category: カテゴリ名
description: 検索結果やSNSに出る説明文（80〜120字目安）
tags: タグ1, タグ2
---
```

## 運営メモ（Claude Codeへの指示例）

- 記事作成: 「仕様書の記事テンプレに沿って、キーワード◯番の記事下書きを articles/ に作って」
- 体験の書き込み: 「◯◯の記事の[ここに体験を書く]欄に、次の内容を清書して入れて: （箇条書きで貼る）」
- 公開: pushすれば自動で反映される（反映まで1〜2分）

## ローカルでのビルド確認

```
pip install markdown jinja2
python build.py
```

`dist/` に生成される。
