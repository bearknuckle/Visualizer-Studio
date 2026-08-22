# Visualizer Studio

MP4動画に音楽連動型の棒状スペクトラムを追加するWindows向けビジュアライザーツールです。

## Concept

MP4動画を読み込むだけで、動画の最下部に音楽に合わせて動くスペクトラムを追加し、新しいMP4として書き出します。

## Current Version

**v2.0.3**

### v2.0.3 changes

- Spectrum bars: 40
- Narrower spacing between bars
- Thicker, easier-to-see spectrum
- Spectrum positioned at the bottom of the video
- Long-video processing tested with approximately 1-hour video
- Windows EXE build tested

## Project Structure

```text
Visualizer-Studio/
├── README.md
├── Visualizer_Studio.py
└── versions/
    └── v2.0.3/
        └── Visualizer_Studio.py
```

## Requirements for source version

- Windows
- Python 3.x
- FFmpeg
- FFprobe
- Required Python packages used by the application

## EXE Version

A Windows EXE version is also being developed.

The portable distribution is intended to allow users to run:

```text
Visualizer_Studio.exe
```

without separately installing Python or FFmpeg.

## Development Policy

The `versions/` directory stores stable source snapshots.

When a new version is developed, the previous stable version should remain unchanged.

Example:

```text
v2.0.3  Stable
   ↓
v2.0.4  Development
```

This makes it possible to return to a known working version if a future change causes a problem.

## License

License information will be added when the project's distribution policy is decided.
