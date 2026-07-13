# raspberry_pi_fourier_transformer

マイク（KY-037 + MCP3008 ADC）で拾った音をラズパイ上でリアルタイムFFTにかけ、
ピーク周波数の帯域に応じてLEDを点滅させるプロジェクトです。pygameで音のスペクトラムも画面に表示します。

## 使うもの（ハードウェア）

- Raspberry Pi
- MCP3008（ADC, SPI接続）+ マイクセンサー（KY-037など）: CH0に接続
- LED: GPIO17
- タクトスイッチ: GPIO23（プルアップ、押すとLOW）
- スピーカー: GPIO18（PWM出力）

## ラズパイで実行する（本番）

```bash
pip install numpy pygame spidev RPi.GPIO
python main_sound_fft.py
```

起動するとpygameウィンドウが開き、スペクトラムが表示されます。操作方法は以下の通りです。

| 操作 | 動作 |
|---|---|
| スイッチ1回押し | FFT解析（`capturing`）の開始／もう一度押すと停止（トグル式） |
| スイッチ素早く2連続押し | 最後に検出したピーク周波数を**ピッチ補正**（一番近い平均律の音に補正）してGPIO18のスピーカーから1秒間鳴らす（`play_peak_tone`） |
| スイッチ素早く3連続／4連続押し | 直近スペクトラムの上位3つ／4つのピーク（`top_n_peaks`）をそれぞれピッチ補正し、0.3秒ずつ順番にループ再生（`play_topn_loop`）。もう一度押すと停止 |
| `Esc`キー／ウィンドウを閉じる | 終了 |

- 検出したピーク周波数の帯域（`FREQ_BANDS`）に応じてLEDの点滅速度が変化します（下表）
- 画面には検出したピーク周波数に一番近い平均律の音名（例: `A4`）と補正後の周波数も表示されます
- スピーカー再生に使うスペクトラムは「押した瞬間」ではなく、押した時刻より`PRESS_LOOKBACK_SEC`（0.3秒）前のスナップショットです（`shared.snapshots`に直近`SNAPSHOT_HISTORY_LEN`件分の履歴を保持し`get_snapshot_before`で取得）。スイッチを押す際の振動・ノイズがそのまま鳴ってしまうのを防ぐためです

| 周波数帯 | 点滅速度 |
|---|---|
| 0–300 Hz | 2.0 Hz |
| 300–1000 Hz | 5.0 Hz |
| 1000 Hz– | 10.0 Hz |

## 録音→再生する（voice_record_playback.py）

```bash
pip install numpy pygame spidev RPi.GPIO
python voice_record_playback.py
```

- スイッチ（GPIO23）を押している間だけマイクを録音（LEDが点灯）
- 離すと録音終了、実測サンプリングレートから44.1kHzへリサンプリングして自動再生
- 安全のため最大5秒（`MAX_RECORD_SEC`）で録音を自動停止
- `Ctrl+C`で終了

**音の出力先は3.5mmイヤホンジャック固定**です。起動時に`amixer cset numid=3 1`を実行して自動的にジャック出力へ切り替えます
（この制御が効かない機種・OSの場合は`sudo raspi-config` → `System Options` → `Audio` → `Headphones`で手動設定してください）。
再生には、ラズパイの3.5mmジャックにイヤホンやスピーカーを挿しておく必要があります。

## ラップトップで検証する（実機なし）

ラズパイの実機が手元になくても、FFT処理や画面表示だけを手元PCで確認できます。

```bash
pip install numpy pygame
python tests/test_sound_fft_laptop.py
```

操作方法:

| キー | 動作 |
|---|---|
| `SPACE` | 疑似スイッチを押す（押している間だけ疑似音をFFT解析） |
| `↑` / `↓` | 疑似音（サイン波）の周波数を上下させる |
| `Esc` | 終了 |

画面右上の丸はLEDの代わりの表示で、点灯/消灯でLEDの点滅状態を確認できます。

Pythonの標準ライブラリのみを使った疑似マイク・疑似スイッチで動作するため、`spidev`や`RPi.GPIO`は不要です。ロジックを確認したあとラズパイに持っていく場合は、そのまま`main_sound_fft.py`を使ってください（このテスト用ファイルはラズパイでは使いません）。

## ファイル構成

| ファイル | 内容 |
|---|---|
| `main_sound_fft.py` | **本番用。ラズパイ実機でのみ動作。** マイク入力→FFT→LED点滅→pygame表示。 |
| `voice_record_playback.py` | **本番用。ラズパイ実機でのみ動作。** スイッチを押している間マイクで録音し、離すと録音した音を再生する。 |
| `tests/test_sound_fft_laptop.py` | **ラップトップ用の検証スクリプト。** 実機ハードウェアの代わりに疑似サイン波と疑似スイッチ（キーボード）を使い、FFT・表示ロジックだけを手元PCで確認できる。 |
| `tests/test_measure_samplerate.py` | ADCの実効サンプリングレートを計測する簡易スクリプト。 |
| `tests/test_fft.py` | FFTのピーク検出だけを試すための簡易スクリプト（LED/pygameなし）。 |
| `tests/test_f_range.py` | ADCの読み取り値のmin/max/範囲を確認するスクリプト。 |
| `tests/test_adc_ky_037.py` | ADCの生値をバーで表示する動作確認スクリプト。 |
| `tests/test_blink.py` / `tests/test.py` | LEDの点滅だけを試す動作確認スクリプト。 |
| `tests/test_SW.py` / `tests/test_tact.py` | タクトスイッチの入力だけを試す動作確認スクリプト。 |
| `tests/test_speaker.py` | GPIO18のスピーカーがPWMで鳴るかどうかだけを確認するスクリプト（200Hz〜2000Hzを掃引）。 |
| `tests/test_pygame_display.py` | pygameウィンドウが開くかどうかだけを確認するスクリプト。 |

`tests/`配下（`test_sound_fft_laptop.py`を除く）は開発中の動作確認用スクリプトで、いずれもラズパイ実機（`spidev` / `RPi.GPIO`）が必要です。

## 必要なライブラリ

- `numpy`
- `pygame`
- （ラズパイ実機のみ）`spidev`, `RPi.GPIO`

## FFT処理の仕様（詳細）

<details>
<summary>クリックで展開: ブロック単位FFTの仕組みとキャリブレーションの詳細</summary>

`audio_worker`がやっているのは「サンプル単位で滑らかに更新され続ける連続ストリーミングFFT」ではなく、
**一定個数のサンプルをまとめて撮っては解析し直す、ブロック単位のFFT（非オーバーラップの短時間フーリエ変換）を高頻度で繰り返す方式**です。
体感としては「リアルタイム」に近い動きをしますが、正確には以下のような処理になっています。

0. 実効サンプルレートは`read_block`内で`N`回分のADC読み取りにかかった実時間から都度計測しているが、実機のチューナーと比較すると常に全音（半音2つ）分フラットに検出される（＝計測レートが実際より低く見積もられている）ことを確認したため、`RATE_CALIBRATION`（`2 ** (2/12)`）を掛けて補正している。手元の機体でズレ幅が異なる場合は`RATE_CALIBRATION`を`2 ** (ズレの半音数/12)`に置き換えて再キャリブレーションすること
1. `N=2048`個のADC値を、可能な限り高速に連続読み取り（`read_adc`をN回呼ぶだけ）→ これを`NUM_AVERAGES`（4）回繰り返して`compute_spectrum`でFFT
2. 複数回分のスペクトルを平均（`average_spectra`）してランダムなノイズを打ち消す
3. 起動時に計測した定常ノイズのスペクトル（`noise_profile`、`calibrate_noise_profile`）を差し引く（`subtract_noise_profile`）
4. `LOW_CUT_FREQ`（80Hz）未満と`HIGH_CUT_FREQ`（2000Hz）超を0にカット（`apply_band_limit`、声の帯域外の電気的ノイズがピークとして誤検出されるのを防ぐため）
5. ブロック内の最大値に対する割合以下のビンを0にカット（`apply_noise_floor`、ノイズフロア除去）
6. 周波数方向に移動平均をかけてスペクトルの形をなめらかにする（`smooth_spectrum`）
7. 一番強い周波数（`peak`）とその強さ（`strength`）を取り出す
8. 直近`PEAK_HISTORY`（5）回分の`peak`の中央値を取って表示・LED点滅用の値を安定させる
9. `shared`（ロック付き共有変数）に書き込み、pygame側の表示スレッドがそれを読んで描画

これを`while shared.running`のループで、`capturing=True`の間（スイッチを押すたびにON/OFFがトグルされる）ずっと繰り返します。
音声取得（`audio_worker`）と画面描画（`run_display`）は別スレッドで動いており、`shared`変数経由で
最新の解析結果だけをやり取りしているため、描画側は常に「直近に完成した1ブロック分」の結果を表示します。

なお、起動直後（`main`関数の最初）に`calibrate_noise_profile`で無音状態のノイズを`CALIBRATION_BLOCKS`（3）ブロック分計測するため、
**プログラム起動直後の数百ミリ秒はマイクに向かって喋らず静かにしておく**必要があります。

補足の数値の目安（実測サンプルレートが`tests/test_measure_samplerate.py`の`MEASURED_RATE=39271`Hz程度の場合）:

- 1ブロックの所要時間: `2048 / 39271 ≈ 52ms`
- スペクトル平均（`NUM_AVERAGES=4`）のため、1回の解析結果が出るまで`52ms × 4 ≈ 208ms`程度かかる → 更新頻度は以前（約50msごと）よりゆっくりになる
- 周波数分解能（1本あたりの幅）: `rate / N ≈ 19Hz`

つまり「連続的に滑らかに追従する」のではなく、「約200msごとにまとめて撮り直したスナップショットを次々に表示することで、疑似的にリアルタイムに見せている」のが実態です。ノイズ対策を厚くした分、以前より更新間隔は長くなっています。

</details>
