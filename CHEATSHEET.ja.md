# UV-K5 日本語・受信専用版 cheatsheet

[日本語版README](README.ja.md) | [英語版README](README.md) | [CHIRPドライバ](tools/chirp/README.ja.md)

注意事項、forkの関係、AI支援開発、免責、バックアップの要件は[README.ja.md](README.ja.md)を確認してください。

このファイルは早見表です。対象機種、メモリーマップ、CHIRPの読み書き範囲などの説明を重複して管理しません。

## まず確認

- 用途: 日本国内向けの受信専用運用
- 版: `Kris v4.3J2` / `JP-RX-Only`
- `PTT`: モニター。送信しない
- FM放送: `76.0–95.0 MHz`

## 実機操作

| 操作 | 動作 |
| --- | --- |
| `M`短押し | メニュー／確定 |
| `EXIT` | 戻る／キャンセル |
| `UP` / `DOWN` | 選択・周波数変更 |
| `F` + `2 A/B` | VFO A/B切替 |
| `F` + `3 VFO/MR` | VFO／メモリー切替 |
| `PTT` | モニター切替 |
| `F` + `0 FM` | FM放送 |
| `* SCAN`長押し | スキャン開始 |
| スキャン中に`F1`短押し | 現在周波数を一時スキップ |

## 受信設定

| 設定 | 値・動作 |
| --- | --- |
| `W/N` | `W+` 25 kHz / `W` 20 kHz / `N` 12.5 kHz / `N-` 6.25 kHz |
| 受信モード | `MAIN ONLY` / `DUAL RX` / `SINGLE` |
| `Bank` | `ALL` / `B1`〜`B8` |
| `BnkSet` | 現在のメモリーをバンクへ割り当て |
| スケルチ | 数値または`AUTO` |
| `RXExt` | 追加受信機能をまとめて`ON` / `OFF`（初期値`ON`） |
| プリセット | `STAR`短押しで選択 |

`RXExt=OFF`では、プリセット、SINGLE、バンク絞り込み、AUTOスケルチ、AGCガード、一時スキップが停止します。通常受信の4段階帯域幅、受信専用動作、PTTモニター、日本語表示、FM放送帯域制限は維持されます。周波数ステップは帯域幅と独立して選択できます。

## CHIRP

機種選択、バックアップ、校正領域の保護範囲は[CHIRPドライバの説明](tools/chirp/README.ja.md)を確認してください。要点は、旧UV-K5プロファイルを選び、アップロード前に全イメージを保存し、送信設定を扱わないことです。

## ビルド（リポジトリのルート）

```powershell
# テスト
make test

# ビルド
make -j2

# パック済みイメージが必要な場合（初回のみ）
python -m pip install crcmod
make -j2
```

生成物:

- `wrx-jp.bin`: 生イメージ
- `wrx-jp.packed.bin`: 書き込み用イメージ
- `wrx-jp`: ELF

作り直し:

```powershell
make clean
make -j2
```

## 書き込み前チェック

- EEPROMをバックアップしたか
- UV-K5向けのイメージを選んだか
- ファイル名と版を確認したか
- 書き込み後にPTTがモニター動作になることを確認するか
