#!/usr/bin/env python3
"""
clone_voice.py - Clone a voice from a short audio sample and generate narration.

Supports multiple open-source voice cloning engines with automatic GPU detection
and engine selection. Falls back gracefully when GPU is unavailable.

Engines (ranked by quality):
  1. Qwen3-TTS   — Best quality, 3-second cloning, Apache 2.0, needs CUDA GPU (4-8GB VRAM)
  2. Coqui XTTS  — Multilingual, 5-second cloning, good quality, needs CUDA GPU (6GB+ VRAM)
  3. OpenVoice   — Lightweight zero-shot, lower quality, smaller GPU footprint
  4. Chatterbox  — Real-time, MIT license, moderate GPU needs

Usage:
    # Check which engines are available on this system
    uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/clone_voice.py --check-engines

    # Clone voice and generate narration
    uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/clone_voice.py \
        --voice-sample /path/to/my_voice.wav \
        --script RECORDING_SCRIPT.md \
        --output-dir ./output \
        --engine auto

    # Record a voice sample from microphone (10 seconds)
    uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/clone_voice.py \
        --record 10 \
        --output-dir ./output
"""

import argparse
import os
import sys
import subprocess
import shutil


def check_cuda_available():
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def get_cuda_vram_gb():
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return props.total_mem / (1024 ** 3)
    except Exception:
        pass
    return 0


def check_engine_available(engine: str) -> dict:
    result = {"available": False, "reason": ""}

    if engine == "qwen3-tts":
        try:
            import qwen3_tts
            if not check_cuda_available():
                result["reason"] = "CUDA GPU required but not found"
                return result
            vram = get_cuda_vram_gb()
            if vram < 4:
                result["reason"] = f"Needs 4GB+ VRAM, found {vram:.1f}GB"
                return result
            result["available"] = True
        except ImportError:
            result["reason"] = "qwen3-tts not installed (pip install qwen3-tts)"

    elif engine == "coqui-xtts":
        try:
            from TTS.api import TTS
            if not check_cuda_available():
                result["reason"] = "CUDA GPU required but not found"
                return result
            vram = get_cuda_vram_gb()
            if vram < 6:
                result["reason"] = f"Needs 6GB+ VRAM, found {vram:.1f}GB"
                return result
            result["available"] = True
        except ImportError:
            result["reason"] = "TTS not installed (pip install TTS)"

    elif engine == "openvoice":
        try:
            import openvoice
            if not check_cuda_available():
                result["reason"] = "CUDA GPU recommended but not found (CPU mode very slow)"
                return result
            result["available"] = True
        except ImportError:
            result["reason"] = "openvoice not installed (pip install openvoice)"

    elif engine == "chatterbox":
        try:
            import chatterbox
            if not check_cuda_available():
                result["reason"] = "CUDA GPU required but not found"
                return result
            result["available"] = True
        except ImportError:
            result["reason"] = "chatterbox not installed (pip install chatterbox-tts)"

    return result


def check_all_engines():
    engines = [
        ("qwen3-tts", "Qwen3-TTS (Alibaba)", "Best quality, 3s cloning, Apache 2.0, 4-8GB VRAM"),
        ("coqui-xtts", "Coqui XTTS v2", "Multilingual, 5s cloning, 6GB+ VRAM"),
        ("openvoice", "OpenVoice", "Zero-shot, lightweight, ~4GB VRAM"),
        ("chatterbox", "Chatterbox (Resemble AI)", "Real-time, MIT license, ~4GB VRAM"),
    ]

    print("Voice Cloning Engine Status")
    print("=" * 70)

    has_cuda = check_cuda_available()
    vram = get_cuda_vram_gb()
    print(f"CUDA Available: {'Yes' if has_cuda else 'No'}")
    if has_cuda:
        print(f"GPU VRAM: {vram:.1f} GB")
    print()

    any_available = False
    for engine_id, name, desc in engines:
        status = check_engine_available(engine_id)
        icon = "OK" if status["available"] else "X "
        print(f"  [{icon}] {name:<30} {desc}")
        if not status["available"]:
            print(f"       Reason: {status['reason']}")
        else:
            any_available = True

    print()
    if not has_cuda:
        print("NOTE: All voice cloning engines require a CUDA-compatible NVIDIA GPU.")
        print("      Without a GPU, use edge-tts neural voices instead (generate_audio.py).")
        print("      edge-tts Multilingual Neural voices are excellent and require no GPU.")
    elif not any_available:
        print("NOTE: GPU detected but no cloning engines installed.")
        print("      Install one with: pip install qwen3-tts  (recommended)")
    else:
        print("Run with --voice-sample and --script to clone a voice and generate narration.")


def _ensure_recording_deps():
    try:
        import sounddevice  # noqa: F401
        import soundfile  # noqa: F401
    except ImportError:
        print("Installing recording dependencies (sounddevice, soundfile)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "sounddevice", "soundfile"],
            stdout=subprocess.DEVNULL,
        )


def _write_status(output_dir: str, status: str, detail: str = ""):
    status_path = os.path.join(output_dir, ".recording_status")
    import json, time as _t
    with open(status_path, "w") as f:
        json.dump({"status": status, "detail": detail, "ts": _t.time()}, f)


def record_voice_sample(duration: int, output_dir: str, skip_countdown: bool = False) -> str:
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "voice_sample.wav")

    _ensure_recording_deps()
    import sounddevice as sd
    import soundfile as sf
    import time

    sample_rate = 44100

    _write_status(output_dir, "preparing")

    print()
    print(f"  Duration : {duration} seconds")
    print(f"  Format   : WAV {sample_rate} Hz mono")
    print()

    import platform
    if platform.system() == "Darwin":
        print("  (macOS: allow microphone access if prompted)")
        print()

    if not skip_countdown:
        _write_status(output_dir, "countdown", "3")
        for i in [3, 2, 1]:
            print(f"\a  >>>  {i}  <<<", flush=True)
            _write_status(output_dir, "countdown", str(i))
            time.sleep(1)
        print()

    _write_status(output_dir, "recording", str(duration))
    print(f"\a{'=' * 50}")
    print(f"||{'':^48}||")
    print(f"||{'RECORDING NOW — START READING!':^48}||")
    print(f"||{f'({duration} seconds)':^48}||")
    print(f"||{'':^48}||")
    print(f"{'=' * 50}")
    print()

    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")

    for elapsed in range(duration):
        remaining = duration - elapsed
        bar_len = 30
        filled = int(bar_len * elapsed / duration)
        bar = "#" * filled + "-" * (bar_len - filled)
        msg = f"  [{bar}] {remaining}s remaining"
        print(msg, end="\r", flush=True)
        _write_status(output_dir, "recording", f"{remaining}s remaining")
        time.sleep(1)

    sd.wait()

    print(f"  [{'#' * 30}] done!          ")
    print()
    print(f"\a{'=' * 50}")
    print(f"||{'':^48}||")
    print(f"||{'>>> STOP — RECORDING COMPLETE <<<':^48}||")
    print(f"||{'':^48}||")
    print(f"{'=' * 50}")
    print()

    sf.write(output_path, audio, sample_rate)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"  Saved: {output_path} ({size_kb:.0f} KB)")
    print()
    _write_status(output_dir, "done", f"{size_kb:.0f} KB")
    return output_path


def extract_narration(script_path: str) -> str:
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    narration_parts = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith('"') and stripped.endswith('"'):
            narration_parts.append(stripped[1:-1])

    if not narration_parts:
        print("ERROR: No quoted narration lines found in script.", file=sys.stderr)
        sys.exit(1)

    print(f"Extracted {len(narration_parts)} narration segments.")
    return " ... ".join(narration_parts)


def select_engine(preferred: str) -> str:
    if preferred != "auto":
        status = check_engine_available(preferred)
        if status["available"]:
            return preferred
        print(f"WARNING: {preferred} not available ({status['reason']}). Trying alternatives...", file=sys.stderr)

    priority = ["qwen3-tts", "coqui-xtts", "openvoice", "chatterbox"]
    for engine in priority:
        status = check_engine_available(engine)
        if status["available"]:
            print(f"Selected engine: {engine}")
            return engine

    print("ERROR: No voice cloning engine available.", file=sys.stderr)
    print("Install one (requires CUDA GPU):", file=sys.stderr)
    print("  pip install qwen3-tts       # Recommended, best quality", file=sys.stderr)
    print("  pip install TTS             # Coqui XTTS", file=sys.stderr)
    print("  pip install chatterbox-tts  # Chatterbox", file=sys.stderr)
    print("\nOr use edge-tts neural voices (no GPU needed):", file=sys.stderr)
    print("  python generate_audio.py --voices en-US-AndrewMultilingualNeural", file=sys.stderr)
    sys.exit(1)


def clone_with_qwen3(voice_sample: str, text: str, output_file: str):
    print("Cloning with Qwen3-TTS...")
    from qwen3_tts import Qwen3TTS

    model = Qwen3TTS.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    model.cuda()

    audio = model.synthesize(
        text=text,
        ref_audio=voice_sample,
    )

    import soundfile as sf
    sf.write(output_file.replace(".mp3", ".wav"), audio, 24000)
    _convert_wav_to_mp3(output_file.replace(".mp3", ".wav"), output_file)
    print(f"Done: {output_file}")


def clone_with_coqui(voice_sample: str, text: str, output_file: str):
    print("Cloning with Coqui XTTS v2...")
    from TTS.api import TTS

    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
    tts.tts_to_file(
        text=text,
        speaker_wav=voice_sample,
        language="en",
        file_path=output_file.replace(".mp3", ".wav"),
    )
    _convert_wav_to_mp3(output_file.replace(".mp3", ".wav"), output_file)
    print(f"Done: {output_file}")


def clone_with_openvoice(voice_sample: str, text: str, output_file: str):
    print("Cloning with OpenVoice...")
    from openvoice import se_extractor
    from openvoice.api import BaseSpeakerTTS, ToneColorConverter

    ckpt_base = "checkpoints/base_speakers/EN"
    ckpt_converter = "checkpoints/converter"

    base_speaker_tts = BaseSpeakerTTS(f"{ckpt_base}/config.json", device="cuda")
    base_speaker_tts.load_ckpt(f"{ckpt_base}/checkpoint.pth")

    tone_color_converter = ToneColorConverter(f"{ckpt_converter}/config.json", device="cuda")
    tone_color_converter.load_ckpt(f"{ckpt_converter}/checkpoint.pth")

    source_se = se_extractor.get_se(voice_sample, tone_color_converter, target_dir="processed", vad=True)

    tmp_path = output_file.replace(".mp3", "_tmp.wav")
    base_speaker_tts.tts(text, tmp_path, speaker="default", language="English")

    tone_color_converter.convert(
        audio_src_path=tmp_path,
        src_se=source_se,
        tgt_se=source_se,
        output_path=output_file.replace(".mp3", ".wav"),
    )

    os.remove(tmp_path)
    _convert_wav_to_mp3(output_file.replace(".mp3", ".wav"), output_file)
    print(f"Done: {output_file}")


def clone_with_chatterbox(voice_sample: str, text: str, output_file: str):
    print("Cloning with Chatterbox...")
    from chatterbox.tts import ChatterboxTTS

    model = ChatterboxTTS.from_pretrained(device="cuda")
    wav = model.generate(text, audio_prompt_path=voice_sample)

    import torchaudio
    torchaudio.save(output_file.replace(".mp3", ".wav"), wav, model.sr)
    _convert_wav_to_mp3(output_file.replace(".mp3", ".wav"), output_file)
    print(f"Done: {output_file}")


def _convert_wav_to_mp3(wav_path: str, mp3_path: str):
    if shutil.which("ffmpeg"):
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-q:a", "2", mp3_path],
            capture_output=True,
        )
        if os.path.exists(mp3_path):
            os.remove(wav_path)
            return
    print(f"  ffmpeg not found — output saved as WAV: {wav_path}")
    if mp3_path != wav_path:
        os.rename(wav_path, mp3_path.replace(".mp3", ".wav"))


def main():
    parser = argparse.ArgumentParser(
        description="Clone a voice from audio sample and generate narration"
    )
    parser.add_argument("--check-engines", action="store_true",
                        help="Check which voice cloning engines are available")
    parser.add_argument("--record", type=int, metavar="SECONDS",
                        help="Record a voice sample from microphone (e.g., --record 10)")
    parser.add_argument("--voice-sample", help="Path to voice sample audio file (WAV/MP3, 3-30 seconds)")
    parser.add_argument("--script", help="Path to RECORDING_SCRIPT.md")
    parser.add_argument("--text", help="Direct text to synthesize (alternative to --script)")
    parser.add_argument("--output-dir", help="Directory for output files")
    parser.add_argument("--engine", default="auto",
                        choices=["auto", "qwen3-tts", "coqui-xtts", "openvoice", "chatterbox"],
                        help="Voice cloning engine (default: auto-select best available)")
    parser.add_argument("--ref-text", default=None,
                        help="Transcript of what was said in the voice sample (improves prosody cloning)")
    parser.add_argument("--no-confirm", action="store_true",
                        help="Skip interactive keep/re-record prompt after recording (for non-interactive callers)")
    args = parser.parse_args()

    if args.check_engines:
        check_all_engines()
        return

    if args.record:
        if not args.output_dir:
            parser.error("--output-dir required with --record")
        os.makedirs(args.output_dir, exist_ok=True)
        if args.no_confirm:
            voice_path = record_voice_sample(args.record, args.output_dir, skip_countdown=False)
            print(f"\nVoice sample ready: {voice_path}")
        else:
            while True:
                voice_path = record_voice_sample(args.record, args.output_dir)
                print()
                print("  Options:")
                print("  [k] Keep this recording and continue")
                print("  [r] Re-record")
                print("  [q] Quit")
                print()
                choice = input("  Your choice [k/r/q]: ").strip().lower()
                if choice in ("k", ""):
                    print(f"\nVoice sample ready: {voice_path}")
                    break
                elif choice == "r":
                    print("\nRe-recording...\n")
                    continue
                elif choice == "q":
                    print("Exiting.")
                    sys.exit(0)
                else:
                    print("  Keeping recording.")
                    break
        return

    if not args.voice_sample:
        parser.error("--voice-sample is required for voice cloning (or use --record to capture one)")

    if not os.path.isfile(args.voice_sample):
        print(f"ERROR: Voice sample not found: {args.voice_sample}", file=sys.stderr)
        sys.exit(1)

    if args.script:
        narration_text = extract_narration(args.script)
    elif args.text:
        narration_text = args.text
    else:
        parser.error("--script or --text is required for voice cloning generation")

    if not args.output_dir:
        parser.error("--output-dir is required")

    os.makedirs(args.output_dir, exist_ok=True)

    engine = select_engine(args.engine)
    output_file = os.path.join(args.output_dir, f"demo_narration_cloned_{engine.replace('-', '_')}.mp3")

    clone_functions = {
        "qwen3-tts": clone_with_qwen3,
        "coqui-xtts": clone_with_coqui,
        "openvoice": clone_with_openvoice,
        "chatterbox": clone_with_chatterbox,
    }

    clone_functions[engine](args.voice_sample, narration_text, output_file)

    size_mb = os.path.getsize(output_file) / (1024 * 1024) if os.path.exists(output_file) else 0
    wav_fallback = output_file.replace(".mp3", ".wav")
    if not os.path.exists(output_file) and os.path.exists(wav_fallback):
        size_mb = os.path.getsize(wav_fallback) / (1024 * 1024)
        print(f"\nOutput: {wav_fallback} ({size_mb:.2f} MB)")
    else:
        print(f"\nOutput: {output_file} ({size_mb:.2f} MB)")

    print("Done!")


if __name__ == "__main__":
    main()
