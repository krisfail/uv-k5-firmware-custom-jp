# 日本語フォントの出所と変換

この文書は，人間の開発者が日本語字形の出所と生成方法を確認するための記録です．利用者向けの表示案内は`README.ja.md`，AIエージェント向けの規則は`AGENTS.md`を参照してください．

## `専`・`用`の字形

`0x98=専`，`0x99=用`のプレースホルダを，Unifoundryが公開する**Izumi 16 Plane 1，JIS X 0213:2004**の16×16 BDFから独立に変換しました．公式ページは，このIzumi 16をパブリックドメインのJIS X 0213フォントとして説明しています．

- 配布元: [Unifoundry Japanese Font Encodings](https://unifoundry.com/japanese/)
- ファイル: `izmg16-2004-1.bdf.gz`
- 取得元URL: `https://unifoundry.com/japanese/izmg16-2004-1.bdf.gz`
- SHA-256: `005345196615E692C54EF67286B44DD0EAA3A899D066CD407A4B3A810822C20`
- ライセンス上の扱い: 配布元の説明に従い，該当字形はパブリックドメイン

他の日本語字形には既存の帰属・ライセンスがあるため，この変更で既存フォント全体を置き換えたわけではありません．`rainy-knight/uv-k5-jp`由来部分の帰属は`README.md`および既存のNOTICEを維持します．

## クリーンルーム変換

`tools/import_public_domain_bitmap_font.py`は，BDFのUnicode/JIS対応を読み取り，

1. BDFの16×16ビットマップを読み取る．
2. ISO-2022-JPのJIS row-cell値で対象字形を選択する．
3. 16行のうち，共通表示契約の上2行・字形10行・下4行へ縦方向に配置する．
4. `専`／`用`は，16×16の線の構造を7列／10列へ収める独立の低解像度再構成を使う．その他の字形は，対象列へ対応するソース列に点が一つでもあれば点灯する縮小規則で変換する．
5. OLEDのLSB-first，2ページ形式へC初期化子として出力する．

として出力します．

K5では通常大字形の`0x98`／`0x99`と，起動画面で使う10×16特大字形の同2字を更新しました．`受`／`信`は既存の通常大字形を使い，起動画面の4字を同じ7×14系で描画して，字幅の混在を避けています．K5の容量を超えないよう，10×16特大字形は`専`／`用`だけです．ビルドは取得済みBDFを必要とせず，変換後のC配列だけを使用します．

変換例:

```powershell
python -X utf8 tools/import_public_domain_bitmap_font.py `
  tmp/open-fonts/izmg16-2004-1.bdf.gz
```

出力をソースへ反映した後は，atlasとフォント一覧を再生成します．

```powershell
python -X utf8 tools/render_bitmap_atlas.py `
  --out docs/assets/font-atlas `
  --markdown-out docs/FONT_INVENTORY.ja.md
```
