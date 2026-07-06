# raspberry_pi_fourier_transformer

マイク（KY-037 + MCP3008 ADC）で拾った音をラズパイ上でリアルタイムFFTにかけ、
ピーク周波数の帯域に応じてLEDを点滅させるプロジェクトです。pygameで音のスペクトラムも画面に表示します。

## 使うもの（ハードウェア）

- Raspberry Pi
- MCP3008（ADC, SPI接続）+ マイクセンサー（KY-037など）: CH0に接続
- LED: GPIO17
- タクトスイッチ: GPIO23（プルアップ、押すとLOW）

スイッチを押している間だけ録音・FFT解析（`capturing`）が行われます。
検出したピーク周波数の帯域（`FREQ_BANDS`）に応じて、LEDの点滅速度が変わります。

| 周波数帯 | 点滅速度 |
|---|---|
| 0–300 Hz | 2.0 Hz |
| 300–1000 Hz | 5.0 Hz |
| 1000 Hz– | 10.0 Hz |

## ファイル構成

| ファイル | 内容 |
|---|---|
| `main_sound_fft.py` | **本番用。ラズパイ実機でのみ動作。** マイク入力→FFT→LED点滅→pygame表示。 |
| `test_sound_fft_laptop.py` | **ラップトップ用の検証スクリプト。** 実機ハードウェアの代わりに疑似サイン波と疑似スイッチ（キーボード）を使い、FFT・表示ロジックだけを手元PCで確認できる。 |
| `05_measure_samplerate.py` | ADCの実効サンプリングレートを計測する簡易スクリプト。 |
| `06_test_fft.py` | FFTのピーク検出だけを試すための簡易スクリプト（LED/pygameなし）。 |
| `f_range_test.py` | ADCの読み取り値のmin/max/範囲を確認するスクリプト。 |
| `test_adc_ky_037.py` | ADCの生値をバーで表示する動作確認スクリプト。 |
| `blink.py` / `test.py` | LEDの点滅だけを試す動作確認スクリプト。 |
| `test_SW.py` / `tact.py` | タクトスイッチの入力だけを試す動作確認スクリプト。 |
| `pygame_display_test.py` | pygameウィンドウが開くかどうかだけを確認するスクリプト。 |

`05_`〜`pygame_display_test.py` あたりは開発中の動作確認用スクリプトで、いずれもラズパイ実機（`spidev` / `RPi.GPIO`）が必要です。

## ラズパイで実行する（本番）

```bash
pip install numpy pygame spidev RPi.GPIO
python main_sound_fft.py
```

- 起動するとpygameウィンドウが開きます
- スイッチを押している間だけ音を取り込み、FFTのスペクトラムをバーグラフで表示
- 検出したピーク周波数の帯域に応じてLEDが点滅
- `Esc`キーかウィンドウを閉じると終了

## ラップトップで検証する（実機なし）

ラズパイの実機が手元になくても、FFT処理や画面表示だけを手元PCで確認できます。

```bash
pip install numpy pygame
python test_sound_fft_laptop.py
```

操作方法:

| キー | 動作 |
|---|---|
| `SPACE` | 疑似スイッチを押す（押している間だけ疑似音をFFT解析） |
| `↑` / `↓` | 疑似音（サイン波）の周波数を上下させる |
| `Esc` | 終了 |

画面右上の丸はLEDの代わりの表示で、点灯/消灯でLEDの点滅状態を確認できます。

このスクリプトはPythonの標準ライブラリのみを使った疑似マイク・疑似スイッチで動作するため、`spidev`や`RPi.GPIO`は不要です。ロジックを確認したあとラズパイに持っていく場合は、そのまま`main_sound_fft.py`を使ってください（このテスト用ファイルはラズパイでは使いません）。

## 必要なライブラリ

- `numpy`
- `pygame`
- （ラズパイ実機のみ）`spidev`, `RPi.GPIO`
