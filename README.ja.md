# UV-K5 日本語・受信専用ファームウェア

[英語版README](README.md) | [操作・ビルドcheatsheet](CHEATSHEET.ja.md) | [開発者向けガイド](DEVELOPMENT.md) | [CHIRPドライバ](tools/chirp/README.ja.md) | [新機能の技術詳細](docs/FEATURES_TECHNICAL.ja.md) | [機能監査](docs/FEATURE_AUDIT.ja.md) | [実機テスト計画](docs/HARDWARE_TEST_PLAN.ja.md) | [bitmap/font atlas](docs/BITMAP_ATLAS.ja.md) | [ドキュメントサイト](docs/index.md)

## このリポジトリの位置づけ

このリポジトリは，[krisfail/uv-k5-firmware-custom-jp](https://github.com/krisfail/uv-k5-firmware-custom-jp)として公開している独立したフォークです．主なupstreamは[armel/uv-k5-firmware-custom](https://github.com/armel/uv-k5-firmware-custom)で，さらにその上流にEgzumer，OneOfEleven，fagciの成果があります．本リポジトリの日本語・受信専用版は，これらの成果を基に日本国内向けの受信機用途へ調整した派生版であり，公式Quansheng版や公式F4HWN版ではありません．

## AI支援（AI-Assisted）開発と現状有姿での提供

コードの分析，実装，テスト補助，文書作成の一部にAI支援を使用しています．公開前に保守者が確認していますが，AI支援は保守者によるレビューや利用者の実機確認を代替しません．

ファームウェアは**現状有姿（AS IS）**で提供し，動作や特定目的への適合を保証しません．書き込み失敗，無線機の破損，EEPROM・校正データ・設定の消失，復旧不能，法令・無線規制に反する使用について，保守者は責任を負いません．書き込み前にEEPROMと校正データをバックアップし，機種に対応したイメージと復旧手段を用意してください．

## この文書で分かること

この文書は，UV-K5向けの日本語・受信専用版を使う人を対象にしています．初めて使う場合は「対象と制約」「ビルド」「書き込み」の順に確認し，日常の操作は[CHEATSHEET.ja.md](CHEATSHEET.ja.md)を参照してください．

### 詳しい情報

- 日常操作と最小限のビルド手順は[CHEATSHEET.ja.md](CHEATSHEET.ja.md)
- CHIRPの機種選択・読み書き範囲・校正領域は[CHIRPドライバの説明](tools/chirp/README.ja.md)
- 開発者向けのソース構成・検証・atlas生成は[DEVELOPMENT.md](DEVELOPMENT.md)
- 実装の詳細は[技術詳細](docs/FEATURES_TECHNICAL.ja.md)，採否と除外機能は[機能監査](docs/FEATURE_AUDIT.ja.md)，実機確認項目は[実機テスト計画](docs/HARDWARE_TEST_PLAN.ja.md)

このREADMEは利用者向けの案内です．実装上の判断やAIエージェント向けの作業規則は，上記の開発者向け文書と[AGENTS.md](AGENTS.md)に分けて記載しています．

## 対象と制約

この版は，国内で受信機として使うことを目的にしています．ビルド設定で送信機能を無効化しているため，送信機として使うための設定や手順は提供しません．

- PTTは送信開始ではなく，モニター機能に割り当てています．
- 送信系のメニューと送信処理を除外しています．
- FM放送受信は`76.0–95.0 MHz`に固定しています．
- 表示名は`Kris v4.3J5`，エディション名は`JP-RX-Only`です．
- 日本語フォントは大きい文字と小さい文字の両方で使用します．表示幅の制約から，一部のメニュー名は短い英字表記を残しています．

対象機種の個体差，書き込み方法，受信環境による動作差があります．書き込み前に必ずEEPROMをバックアップし，異なる機種向けのイメージを使用しないでください．

## 受信機として追加した機能

- 受信バンドプリセット: 航空，特小，消防，アマチュア，船舶を用途別に選択
- `W/N`: `W+` 25 kHz，`W` 20 kHz，`N` 12.5 kHz，`N-` 6.25 kHzの4段階の受信帯域
- 受信モード: `MAIN ONLY`，`DUAL RX`，`SINGLE`
- メモリーバンク: `ALL`，`B1`〜`B8`，`NONE`
- `AUTO`スケルチ: 現在のFM受信状態を短時間測定して閾値を調整
- FM受信時の急激なゲイン変化を抑えるAGCガード
- スキャン中の一時スキップ（最大16周波数，電源断で消去）
- `RXExt`: 上記の追加受信機能をまとめてON/OFF（初期値ON）
- 日本語メニューと日本語フォント
- `専`／`用`の大字形は，パブリックドメインのIzumi 16から独立変換しています．詳細は[フォントの出所と変換](docs/FONT_SOURCES.ja.md)を参照してください．

メニューの`RXExt`を`OFF`にすると，プリセット，受信モードの`SINGLE`，メモリーバンク絞り込み，`AUTO`スケルチ，AGCガード，一時スキップを停止します．通常受信の4段階帯域幅，受信専用・PTTモニター，日本語表示，FM放送の`76.0–95.0 MHz`制限は変わりません．周波数ステップは帯域幅と独立して選べます．旧形式の保存データは互換性のためONとして扱います．

受信バンドプリセットは，周波数モードで`STAR`を短押しして選びます．`UP`／`DOWN`で選択，`M`で適用，`STAR`で適用後にスキャン，`EXIT`でキャンセルです．適用した範囲は実行時状態で，電源断後には保持されません．

### 受信バンドプリセット

周波数モードで`STAR`を短押しすると，次の8プリセットを選べます．

| プリセット | 周波数範囲 | 変調 | 帯域幅 | step |
| --- | --- | --- | --- | --- |
| `AIR VHF` | 118.000-137.000 MHz | AM | narrow | 25 kHz |
| `AIR UHF` | 225.000-400.000 MHz | AM | narrow | 100 kHz |
| `TOKUSHO` | 422.050-422.300 MHz | FM | narrow | 12.5 kHz |
| `FIRE` | 466.350-466.550 MHz | FM | narrow | 12.5 kHz |
| `140 HAM` | 144.000-146.000 MHz | FM | wide | 20 kHz |
| `430 HAM` | 430.000-440.000 MHz | FM | wide | 20 kHz |
| `MAR SHIP` | 156.025-157.425 MHz | FM | wide | 25 kHz |
| `MAR SHORE` | 160.625-162.025 MHz | FM | wide | 25 kHz |

`UP`／`DOWN`で循環選択し，`M`で現在のVFOへ適用，`STAR`で適用後にその範囲をスキャン，`EXIT`でキャンセルします．これは受信専用の操作で，送信は行いません．デュアル受信中，クロスバンド中，メモリーチャンネル表示中，既存の範囲指定中などは開けません．適用した範囲は実行時状態であり，VFO切替または電源再投入で解除されます．

## 基本操作

| 操作 | 動作 |
| --- | --- |
| `M`短押し | メニューを開く，項目を確定 |
| `UP` / `DOWN` | メニュー項目・周波数・設定値を移動 |
| `EXIT` | キャンセル，または画面を終了 |
| `F` + `2 A/B` | 上側／下側VFOを選択 |
| `F` + `3 VFO/MR` | 周波数モード／メモリーモードを切り替え |
| `PTT` | モニターを切り替え．送信しない |
| `F` + `0 FM` | FM放送受信を開く |
| `* SCAN`長押し | 周波数またはメモリーチャンネルをスキャン |
| スキャン中に`F1`短押し | 現在周波数を一時スキップ |

メニュー番号を数字キーで入力すると，その項目へ直接移動できます．メニュー全体の対応は上流版の[Wiki](https://github.com/armel/uv-k5-firmware-custom/wiki)も参照してください．

## 表示と利用できない操作

- 受信専用画面では送信出力の`LOW`／`HIGH`表示を出しません．
- 通常の`PTT`はモニター操作です．予期しないTX要求が最終的な安全ゲートへ到達した場合だけ，ビープ音と`TX DISABLE`を表示します．
- 受信拡張の条件が合わない操作は，ビープ音だけでなく`RXExt OFF`，`VFO ONLY`，`SCAN ACTIVE`，`FM ONLY`など短い理由を表示します．
- 起動画面の`MESSAGE`／`ALL`は，保存済みの上流版メッセージではなく，この版の受信専用表示を使用します．

## ビルド

コマンドはリポジトリのルートで実行します．必要なものは`arm-none-eabi-gcc`，GNU Make，Pythonです．回帰テストにはPythonが必要で，パック済みイメージの生成には`crcmod`が必要です．

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
make -j2
```

主な生成物は次のとおりです．

- `wrx-jp.bin`: 生のファームウェアイメージ
- `wrx-jp.packed.bin`: ビルドディレクトリに生成されるパック済みイメージ
- `release/wrx-jp-v4.3J5.packed.bin`: コミット対象のリリース相当イメージ
- `wrx-jp`: ELF形式のデバッグ用ファイル

UVTools2で書き込む場合は，パック済みではない`wrx-jp.bin`を選択してください．`*.packed.bin`はpack形式に対応したツールや配布用に保持するファイルで，UVTools2へそのまま渡すものではありません．

`wrx-jp.packed.bin`が必要なのに生成されない場合は，Pythonと`crcmod`を確認してから再ビルドします．

```powershell
python --version
python -m pip install crcmod
make -j2
```

設定を変えずに作り直す場合は，`make clean`の後に`make -j2`を実行します．`make`が`PYTHON NOT FOUND`または`CRCMOD NOT INSTALLED`と表示しても，生の`wrx-jp.bin`までのビルドは完了します．

## CHIRPドライバ

受信メモリーの読み書きには，[wrx-jp CHIRPドライバ](tools/chirp/README.ja.md)を使用します．このリポジトリの対象である旧UV-K5では`UV-K5 (wrx-jp RX-only)`を選び，K1／K5 V3では別のPY32プロファイルを選びます．アップロード前に対象機種の全イメージを保存してください．送信設定は扱いません．校正領域の保護範囲と例外はCHIRPの説明に集約しています．

## 隠しメニュー

電源OFFの状態で`PTT`と上側サイドキーを同時に押しながら電源を入れると，隠しメニューを開けます．受信専用版では送信ロック・送信調整項目は表示せず，`BatCal`，`BatTyp`，`Reset`などの保守項目を残しています．EEPROM初期化が必要な場合は`Reset`を使用する前に，EEPROMとcalibrationのバックアップを確認してください．

## 書き込み前後

1. EEPROMをバックアップする．
2. 対象機種に対応する`release/wrx-jp-v4.3J5.packed.bin`を選ぶ．
3. 書き込み手順は上流版の[Flashing the firmware](https://github.com/armel/uv-k5-firmware-custom/wiki/Flashing-the-firmware)を確認する．
4. 書き込み後，起動表示，周波数入力，FM放送，PTTのモニター動作を確認する．

PTTを押しても送信しないことがこの版の設計です．実機で予想外の動作を確認した場合は，使用を続けず，バックアップとファームウェアの対応機種を確認してください．

## 問い合わせ

READMEで解決しない場合は，対象機種，表示されている版，使用したイメージ名，再現手順を添えてリポジトリのIssueへ報告してください．実機で再現した表示や音の問題は，可能なら写真・動画と，書き込み前のバックアップの有無も添えてください．

## ライセンス

本リポジトリのライセンスは英語版[README](README.md)および各ソースファイルの記載に従います．

## 謝辞

上流プロジェクトのほか，受信専用・広帯域受信機化の設計検討では`UV-K5-RX-JP`の機能の一部を参考にしました．実装・ライセンス・配布物の権利関係はそれぞれの原著作物に従います．

