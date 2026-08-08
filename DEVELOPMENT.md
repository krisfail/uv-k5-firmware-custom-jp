# 開発者向けガイド（旧UV-K5）

このリポジトリは、DP32G030搭載の旧UV-K5向け`wrx-jp`派生版です。UV-K1／UV-K5 V3（PY32F071）とは対象チップ、ドライバ、メモリーマップ、ビルド系統が異なります。両系統のコードや手順を混ぜないでください。

## 開発を始める前に

- 利用者向けの概要と書き込み手順は[README.md](README.md)または[README.ja.md](README.ja.md)を読む。
- 追加受信機能、EEPROM、フォント、未検証範囲は[docs/FEATURES_TECHNICAL.ja.md](docs/FEATURES_TECHNICAL.ja.md)を正とする。
- フォントやビットマップを追加する前に、[docs/FONT_BITMAP_ANNOTATIONS.ja.md](docs/FONT_BITMAP_ANNOTATIONS.ja.md)とatlas inventoryを確認する。
- CHIRPの機種プロファイルとcalibration境界は[tools/chirp/README.ja.md](tools/chirp/README.ja.md)を読む。

## ビルドとホストテスト

ARM GNU Toolchain（`arm-none-eabi-gcc`）を用意し、リポジトリルートで実行します。

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
make -j2
```

Pythonと`crcmod`がある場合はpacked imageも生成されます。生成物は`wrx-jp`、`wrx-jp.bin`、環境が揃った場合は`wrx-jp.packed.bin`です。K5はフラッシュ容量が厳しいため、機能追加のたびに`arm-none-eabi-size wrx-jp`で余裕を確認します。

変更後は少なくともホストテスト、ビルド、`git diff --check`を実行します。テストはソース構造や境界を確認するもので、RF性能、LCDの見え方、実機書き込みの成功を保証しません。

## ソースの見取り図

| 場所 | 役割 |
| --- | --- |
| `Makefile` | `wrx-jp`の定義、コンパイルフラグ、出力名 |
| `driver/` | BK4819、EEPROM、LCDなどのハードウェアドライバ |
| `app/` | スキャン、受信拡張、メニュー操作、アプリケーション状態 |
| `ui/` | メイン画面、メニュー、起動画面、フォント表示 |
| `font.c` / `bitmaps.c` | 文字グリフと画面ビットマップ |
| `tests/` | ホスト側の回帰テスト |
| `tools/chirp/` | RX-only用CHIRPドライバと境界説明 |

## 変更時の境界

- この版は日本国内向け受信専用です。送信経路、送信メニュー、送信を誘発する操作を再導入しません。PTTはモニターとして維持します。
- `RXExt`は追加受信機能の一括スイッチです。受信専用制約、日本語表示、PTTモニター、FM放送帯域の制約を解除するスイッチにしてはいけません。
- 旧UV-K5のcalibration領域`0x1E00–0x1EBF`は利用者設定や受信拡張の保存先ではありません。CHIRPの通常アップロード範囲にも含めません。
- 新しい永続データを追加する場合は、既存設定、calibration、復旧手順、CHIRPの境界を確認し、技術文書とテストを同じ変更単位で更新します。
- 実機未検証の動作は、READMEやリリース説明で未検証と明示します。

## フォントとatlas

注釈付きatlasを生成するには、例えば次を実行します。

```powershell
python -X utf8 tools/render_bitmap_atlas.py `
  --source font.c `
  --source bitmaps.c `
  --out C:\Users\yukim\uv-kx-jp\tmp\uv-k5-bitmap-atlas
```

新しい文字は既存コードや字形の重複を確認してから追加します。コードポイント、意味、元バイト列は台帳とソースコメントの両方に残してください。K5は大フォントの空き容量も小さいため、文字追加を機械的に増やさないでください。

## コミット、署名、実機確認

既存の未コミット変更を確認してから編集し、意図しない生成物や改行変換を取り込まないでください。コミット、タグ、署名、リリース用バイナリの作成は、リポジトリ管理者の手順に従います。署名が必要な場合は、対話的な署名者の手順を変更しません。

実機へ書き込む前に、個体のEEPROMとcalibrationをバックアップし、機種に一致するイメージを使います。新機能の静的テストやビルド成功を、実機動作の保証として扱わないでください。
