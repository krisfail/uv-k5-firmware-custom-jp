# ビットマップ／フォント atlas

`tools/render_bitmap_atlas.py` は、ファームウェアのビルドには参加せず、Cソース内の`uint8_t` bitmap／font配列を読み取ってOLED向けのatlasを生成するオフライン補助ツールです。bit 0を画面上端として描画します。

## 実行

リポジトリのルートで実行します。引数を省略すると、`bitmaps.c`と`font.c`を読み取ります。

```powershell
python -X utf8 tools/render_bitmap_atlas.py --out C:\Users\yukim\uv-kx-jp\tmp\uv-k5-bitmap-atlas
```

生成物:

- `bitmap_atlas.svg`: ブラウザで開けるatlas
- `bitmap_atlas_inventory.json`: 配列名、条件分岐を含む出現順、サイズ、元バイト列

フォント配列には、コードポイント、ソースコメント、占有／空き状態、グリフ単位の元バイト列も収録します。新しい文字を追加する前は、[FONT_BITMAP_ANNOTATIONS.ja.md](FONT_BITMAP_ANNOTATIONS.ja.md)の台帳とこのinventoryを突き合わせてください。

`gFontBig`は14 bytes/glyph（7列×2 OLEDページ）として認識し、連続した長いbyte列ではなくglyphごとのグリッドに配置します。`gFontBigDigits`も同じ2ページ形式として表示します。`gFontBig`のglyphラベルは`0x21`（`!`）からのコード値です。`#if 0`で無効化された旧配列は除外します。

PNGが必要な場合はImageMagickで変換できます。

```powershell
magick -background white bitmap_atlas.svg bitmap_atlas.png
```

対象を限定する場合は`--source`を繰り返します。

```powershell
python -X utf8 tools/render_bitmap_atlas.py `
  --source bitmaps.c `
  --source font.c `
  --out C:\Users\yukim\uv-kx-jp\tmp\uv-k5-bitmap-atlas
```

条件コンパイルで同名配列が複数存在する場合も、ソース上の出現順を保ち、atlasでは`[2]`のように区別します。これは各ビルド条件の候補を比較するためで、全配列が同一ビルドに同時に入ることを意味しません。

このツールはソースや生成済みファームウェアを書き換えません。表示の意味や実機LCD上の見え方を自動判定するものでもありません。フォントの帰属・ライセンス表示は既存の`NOTICE`やソースコメントから削除しないでください。
