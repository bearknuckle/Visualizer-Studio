"""
Visualizer Studio v2.0.0
MP4を読み込み、動画最下部に棒状スペクトラムを追加してMP4を書き出すベース版。

必要:
    pip install numpy librosa pillow

別途 FFmpeg が PATH に必要です。
"""

import os
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import numpy as np
import librosa
from PIL import Image, ImageDraw


APP_NAME = "Visualizer Studio v2.0.3"


class VisualizerStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("Visualizer Studio v2.0.3")
        self.root.geometry("760x560")
        self.root.minsize(680, 500)

        self.input_path = None
        self.output_path = None
        self.processing = False

        self.bar_count = tk.IntVar(value=40)
        self.max_height = tk.IntVar(value=140)
        self.opacity = tk.IntVar(value=85)

        self.progress_value = tk.DoubleVar(value=0)
        self.status_text = tk.StringVar(value="待機中")
        self.detail_text = tk.StringVar(value="")

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Visualizer Studio v2.0.3",
            font=("Meiryo", 20, "bold")
        ).pack(anchor="w")

        ttk.Label(
            main,
            text="長時間動画でもGUIを止めずに処理状況を表示する改善版",
            font=("Meiryo", 10)
        ).pack(anchor="w", pady=(5, 20))

        file_frame = ttk.LabelFrame(main, text="動画")
        file_frame.pack(fill="x", pady=(0, 15))

        self.file_label = ttk.Label(
            file_frame,
            text="MP4ファイルが選択されていません",
            wraplength=650
        )
        self.file_label.pack(anchor="w", padx=10, pady=10)

        self.select_button = ttk.Button(
            file_frame,
            text="MP4を読み込む",
            command=self.select_mp4
        )
        self.select_button.pack(anchor="e", padx=10, pady=(0, 10))

        settings = ttk.LabelFrame(main, text="スペクトラム設定")
        settings.pack(fill="x", pady=(0, 15))

        rows = [
            ("バー本数", self.bar_count, 20, 120),
            ("最大高さ(px)", self.max_height, 40, 400),
            ("透明度(%)", self.opacity, 10, 100),
        ]

        for row, (label, variable, minimum, maximum) in enumerate(rows):
            ttk.Label(settings, text=label).grid(
                row=row, column=0, padx=10, pady=6, sticky="w"
            )
            ttk.Scale(
                settings,
                from_=minimum,
                to=maximum,
                variable=variable,
                orient="horizontal"
            ).grid(row=row, column=1, padx=10, pady=6, sticky="ew")
            ttk.Label(settings, textvariable=variable, width=6).grid(
                row=row, column=2, padx=10, pady=6
            )

        settings.columnconfigure(1, weight=1)

        progress_frame = ttk.LabelFrame(main, text="処理状況")
        progress_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(
            progress_frame,
            textvariable=self.status_text,
            font=("Meiryo", 10, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 3))

        self.progress = ttk.Progressbar(
            progress_frame,
            variable=self.progress_value,
            maximum=100,
            mode="determinate"
        )
        self.progress.pack(fill="x", padx=10, pady=5)

        ttk.Label(
            progress_frame,
            textvariable=self.detail_text
        ).pack(anchor="w", padx=10, pady=(3, 10))

        button_frame = ttk.Frame(main)
        button_frame.pack(fill="x", pady=(5, 0))

        self.export_button = ttk.Button(
            button_frame,
            text="スペクトラム付きMP4を書き出す",
            command=self.export_video
        )
        self.export_button.pack(side="right")

    def select_mp4(self):
        if self.processing:
            return

        path = filedialog.askopenfilename(
            title="MP4動画を選択",
            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")]
        )

        if not path:
            return

        self.input_path = Path(path)
        self.file_label.config(text=str(self.input_path))
        self.status_text.set("MP4を読み込みました。")
        self.detail_text.set("書き出しボタンを押すと処理を開始します。")
        self.progress_value.set(0)

    def export_video(self):
        if self.processing:
            return

        if not self.input_path:
            messagebox.showwarning(
                "Visualizer Studio",
                "先にMP4動画を読み込んでください。"
            )
            return

        output = filedialog.asksaveasfilename(
            title="出力先を選択",
            defaultextension=".mp4",
            initialfile=f"{self.input_path.stem}_visualizer.mp4",
            filetypes=[("MP4 Video", "*.mp4")]
        )

        if not output:
            return

        self.output_path = Path(output)
        self.processing = True

        self.select_button.config(state="disabled")
        self.export_button.config(state="disabled")
        self.progress_value.set(0)
        self.status_text.set("処理を開始しています...")
        self.detail_text.set("準備中...")
        self.root.update_idletasks()

        # GUIスレッドとは別に処理することで、
        # 1時間級の動画でもウィンドウが「応答なし」にならないようにする。
        import threading

        worker = threading.Thread(
            target=self._render_worker,
            daemon=True
        )
        worker.start()

    def _render_worker(self):
        try:
            self._render()
        except Exception as exc:
            self.root.after(0, self._processing_error, str(exc))
        else:
            self.root.after(0, self._processing_finished)

    def _set_progress(self, value, status=None, detail=None):
        def update():
            self.progress_value.set(max(0, min(100, value)))
            if status is not None:
                self.status_text.set(status)
            if detail is not None:
                self.detail_text.set(detail)

        self.root.after(0, update)

    def _render(self):
        """
        v2.0.2:
        音声を解析し、FFmpegのdrawbox filterで動画最下部に
        音楽連動の棒状スペクトラムを焼き込む。
        """

        ffmpeg = self._find_ffmpeg()
        ffprobe = self._find_ffprobe()

        if ffmpeg is None:
            raise RuntimeError(
                "FFmpegが見つかりません。\n"
                "FFmpegをインストールしてPATHに追加してください。"
            )

        if ffprobe is None:
            raise RuntimeError(
                "FFprobeが見つかりません。\n"
                "FFmpegのbinフォルダがPATHに入っているか確認してください。"
            )

        with tempfile.TemporaryDirectory(prefix="visualizer_studio_") as tmp:
            tmp_path = Path(tmp)
            audio_path = tmp_path / "audio.wav"

            self._set_progress(
                2,
                "動画情報を取得しています...",
                "解像度・フレームレート・長さを確認中..."
            )

            width, height, fps, duration = self._get_video_info(ffprobe)

            self._set_progress(
                5,
                "音声を抽出しています...",
                f"{width}x{height} / {fps:.2f} fps / {self._format_time(duration)}"
            )

            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i", str(self.input_path),
                    "-vn",
                    "-ac", "1",
                    "-ar", "44100",
                    str(audio_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            self._set_progress(
                10,
                "音声を解析しています...",
                "スペクトラムデータを生成中..."
            )

            y, sr = librosa.load(str(audio_path), sr=44100, mono=True)

            # 約1時間の動画でもメモリ使用量を抑えるため、
            # 音声をチャンク単位で解析する。
            n_fft = 2048
            hop_length = 1024
            count = max(10, int(self.bar_count.get()))

            chunk_seconds = 30
            chunk_samples = int(chunk_seconds * sr)

            all_frames = []
            total_samples = len(y)

            for chunk_start in range(0, total_samples, chunk_samples):
                chunk_end = min(chunk_start + chunk_samples, total_samples)
                chunk = y[chunk_start:chunk_end]

                spec = np.abs(
                    librosa.stft(
                        chunk,
                        n_fft=n_fft,
                        hop_length=hop_length
                    )
                )

                band_edges = np.linspace(0, spec.shape[0], count + 1)

                for i in range(spec.shape[1]):
                    values = np.empty(count, dtype=np.float32)

                    for b in range(count):
                        band_start = int(band_edges[b])
                        band_end = max(
                            band_start + 1,
                            int(band_edges[b + 1])
                        )
                        values[b] = np.mean(
                            spec[band_start:band_end, i]
                        )

                    # 全体を毎フレーム最大値で正規化すると、
                    # 無音に近い部分でもバーが大きくなるため、
                    # sqrt圧縮 + ローカル正規化を使用。
                    values = np.sqrt(values)

                    max_value = values.max()
                    if max_value > 1e-8:
                        values /= max_value

                    # 少し滑らかにする
                    values = np.clip(values, 0.0, 1.0)
                    all_frames.append(values)

                processed_seconds = chunk_end / sr
                progress = 10 + (
                    processed_seconds / duration * 25
                    if duration else 25
                )

                self._set_progress(
                    progress,
                    "音声を解析しています...",
                    f"{self._format_time(processed_seconds)} / "
                    f"{self._format_time(duration)}"
                )

            spectrum = np.asarray(all_frames, dtype=np.float32)

            # FFmpeg側で動画FPSに合わせてスペクトラムフレームを
            # 選択できるよう、一時ファイルへ保存。
            spectrum_path = tmp_path / "spectrum.npy"
            np.save(spectrum_path, spectrum)

            self._set_progress(
                38,
                "ビジュアライザーを生成しています...",
                f"{count}本のバーを動画へ合成中..."
            )

            # ---------------------------------------------------------
            # FFmpeg filter_complex用のフレーム単位スペクトラム生成
            #
            # drawboxを1フレームずつ変更する巨大なfilter文字列は、
            # 1時間動画では非常に大きくなってしまうため、
            # PNGオーバーレイ動画を別途生成してから合成する。
            # ---------------------------------------------------------

            overlay_pattern = tmp_path / "overlay_%08d.png"
            overlay_fps = fps

            # 元動画をフレーム単位で画像化するのではなく、
            # 透明PNGのスペクトラム動画を生成する。
            # FFmpegのgeqでは音声データを直接扱いにくいため、
            # Python/OpenCVなしで扱えるようPillowでフレーム生成する。
            #
            # 長時間動画では全フレームを保持せず、逐次生成する。
            self._create_overlay_frames(
                spectrum=spectrum,
                width=width,
                height=height,
                fps=fps,
                output_pattern=overlay_pattern,
                duration=duration
            )

            self._set_progress(
                78,
                "動画を書き出しています...",
                "スペクトラムを元動画へ合成中..."
            )

            # PNG連番を透明オーバーレイとして読み込み、
            # 元動画へ合成。
            #
            # 音声は元動画からコピーせず、AACで再エンコードする。
            # これにより映像フィルター適用時にも音声同期を安定させる。
            filter_complex = (
                "[0:v][1:v]overlay=0:0:format=auto[v]"
            )

            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i", str(self.input_path),
                    "-framerate", f"{overlay_fps:.6f}",
                    "-i", str(overlay_pattern),
                    "-filter_complex", filter_complex,
                    "-map", "[v]",
                    "-map", "0:a?",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    "-movflags", "+faststart",
                    str(self.output_path),
                ],
                check=True
            )

            self._set_progress(
                100,
                "処理完了",
                f"{self._format_time(duration)} のビジュアライザー動画を作成しました。"
            )

    def _create_overlay_frames(
        self,
        spectrum,
        width,
        height,
        fps,
        output_pattern,
        duration
    ):
        """
        透明PNGを1フレームずつ生成する。
        棒状スペクトラムは画面最下部に配置する。
        """

        count = spectrum.shape[1]
        max_height = max(10, int(self.max_height.get()))
        alpha = int(255 * max(0, min(100, self.opacity.get())) / 100)

        # バー間隔
        total_width = width
        gap = max(1, width // 180)
        bar_width = max(
            1,
            int((total_width - gap * (count - 1)) / count)
        )

        # FFTのフレーム数を動画FPSへ変換
        total_frames = max(1, int(np.ceil(duration * fps)))

        # 表示の滑らかさ用に前フレームを保持
        previous = np.zeros(count, dtype=np.float32)

        for frame_index in range(total_frames):
            time_sec = frame_index / fps
            spectrum_index = int(
                time_sec * 44100 / 1024
            )

            spectrum_index = min(
                spectrum_index,
                len(spectrum) - 1
            )

            current = spectrum[spectrum_index]

            # スムージング
            current = previous * 0.35 + current * 0.65
            previous = current

            image = Image.new(
                "RGBA",
                (width, height),
                (0, 0, 0, 0)
            )
            draw = ImageDraw.Draw(image)

            for i, value in enumerate(current):
                bar_height = int(
                    max_height * float(value)
                )

                if bar_height <= 0:
                    continue

                x = i * (bar_width + gap)

                # 最下部から上へ伸びる
                y1 = height
                y2 = max(0, height - bar_height)

                draw.rectangle(
                    [x, y2, x + bar_width, y1],
                    fill=(255, 255, 255, alpha)
                )

            output = str(output_pattern).replace(
                "%08d",
                f"{frame_index + 1:08d}"
            )
            image.save(output)

            if frame_index % max(1, int(fps * 2)) == 0:
                progress = 38 + (
                    frame_index / total_frames * 40
                )
                self._set_progress(
                    progress,
                    "ビジュアライザーを生成しています...",
                    f"{self._format_time(time_sec)} / "
                    f"{self._format_time(duration)}"
                )

    def _get_video_info(self, ffprobe):
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries",
                "stream=width,height,r_frame_rate,duration",
                "-of", "default=noprint_wrappers=1:nokey=0",
                str(self.input_path)
            ],
            check=True,
            capture_output=True,
            text=True
        )

        values = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value

        width = int(values["width"])
        height = int(values["height"])

        rate = values.get("r_frame_rate", "30/1")
        numerator, denominator = rate.split("/")
        fps = float(numerator) / float(denominator)

        duration = float(values.get("duration", 0) or 0)

        if duration <= 0:
            duration_result = subprocess.run(
                [
                    ffprobe,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(self.input_path)
                ],
                check=True,
                capture_output=True,
                text=True
            )
            duration = float(duration_result.stdout.strip())

        return width, height, fps, duration

    @staticmethod
    def _find_ffprobe():
        for command in ("ffprobe", "ffprobe.exe"):
            try:
                result = subprocess.run(
                    [command, "-version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if result.returncode == 0:
                    return command
            except FileNotFoundError:
                pass
        return None

    def _processing_finished(self):
        self.processing = False
        self.select_button.config(state="normal")
        self.export_button.config(state="normal")

        messagebox.showinfo(
            "Visualizer Studio",
            f"書き出しが完了しました。\n\n{self.output_path}"
        )

    def _processing_error(self, error_message):
        self.processing = False
        self.select_button.config(state="normal")
        self.export_button.config(state="normal")
        self.status_text.set("エラー")
        self.detail_text.set("処理を中断しました。")

        messagebox.showerror(
            "Visualizer Studio - エラー",
            error_message
        )

    @staticmethod
    def _format_time(seconds):
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _find_ffmpeg():
        for command in ("ffmpeg", "ffmpeg.exe"):
            try:
                result = subprocess.run(
                    [command, "-version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if result.returncode == 0:
                    return command
            except FileNotFoundError:
                pass

        return None

def main():
    root = tk.Tk()
    app = VisualizerStudio(root)
    root.mainloop()


if __name__ == "__main__":
    main()
