#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import traceback


def log(msg: str):
    ts = time.strftime("%H:%M:%S", time.localtime())
    print(f"[{ts}] {msg}", flush=True)


def log_gpu():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"], text=True
        ).strip()
        log(f"GPU: {out}")
    except Exception:
        log("GPU: nvidia-smi not available")


def log_mem():
    try:
        import torch
        if torch.cuda.is_available():
            alloc = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            log(f"CUDA memory: allocated={alloc:.2f}GB, reserved={reserved:.2f}GB")
    except Exception:
        pass


def log_stage_contents(path: str):
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                sz = os.path.getsize(fp) / 1024
                log(f"  STAGE FILE: {fp} ({sz:.1f} KB)")
    else:
        log(f"  STAGE PATH NOT FOUND: {path}")


def _normalize_punctuation(text: str) -> str:
    import re
    text = text.replace("\u2014", ", ")
    text = text.replace("\u2013", ", ")
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def extract_narration(script_path: str) -> list[tuple[str, bool]]:
    log(f"Reading script: {script_path}")
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    log(f"Script size: {len(content)} chars, {len(content.splitlines())} lines")

    results = []
    section_break_before_next = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            section_break_before_next = True
            continue
        if stripped.startswith('"') and stripped.endswith('"'):
            text = _normalize_punctuation(stripped[1:-1])
            results.append((text, section_break_before_next and len(results) > 0))
            section_break_before_next = False

    if not results:
        log("ERROR: No quoted narration lines found in script.")
        sys.exit(1)

    log(f"Extracted {len(results)} narration segments")
    for i, (seg, brk) in enumerate(results):
        brk_tag = " [section-break]" if brk else ""
        log(f"  Segment {i+1}{brk_tag}: {seg[:80]}{'...' if len(seg)>80 else ''} ({len(seg)} chars)")
    total_chars = sum(len(s) for s, _ in results)
    log(f"Total narration text: {total_chars} chars")
    return results


def transcribe_voice_sample(audio_path: str) -> str:
    t0 = time.time()
    try:
        import whisper
        log("  Loading Whisper tiny model for auto-transcription...")
        whisper_model = whisper.load_model("tiny", device="cuda", download_root="/app/whisper_models")
        log(f"  Whisper loaded in {time.time()-t0:.1f}s")
        log_mem()

        t1 = time.time()
        result = whisper_model.transcribe(audio_path, language="en", fp16=True)
        transcript = result["text"].strip()
        log(f"  Transcription done in {time.time()-t1:.1f}s")
        log(f"  Transcript: {transcript[:120]}{'...' if len(transcript)>120 else ''}")

        del whisper_model
        import torch
        torch.cuda.empty_cache()
        log(f"  Whisper model unloaded, VRAM freed")
        log_mem()
        return transcript
    except Exception as e:
        log(f"  WARNING: Auto-transcription failed: {e}")
        traceback.print_exc()
        return ""


def _patch_offline_tokenizer():
    if os.environ.get("HF_HUB_OFFLINE") == "1":
        try:
            import transformers.tokenization_utils_base as tub
            tub._patch_mistral_regex = lambda cls, *a, **kw: cls
            log("  Patched _patch_mistral_regex for offline mode")
        except Exception as e:
            log(f"  WARNING: Could not patch offline tokenizer: {e}")


def main():
    log("=" * 60)
    log("VOICE CLONING JOB STARTED")
    log("=" * 60)
    job_start = time.time()

    _patch_offline_tokenizer()

    log("STEP 1/8: Environment check")
    log(f"  Python: {sys.version}")
    log(f"  CWD: {os.getcwd()}")
    log(f"  ENV VOICE_SAMPLE_PATH={os.environ.get('VOICE_SAMPLE_PATH', '<not set>')}")
    log(f"  ENV SCRIPT_PATH={os.environ.get('SCRIPT_PATH', '<not set>')}")
    log(f"  ENV OUTPUT_DIR={os.environ.get('OUTPUT_DIR', '<not set>')}")
    log(f"  ENV HF_HOME={os.environ.get('HF_HOME', '<not set>')}")
    log(f"  ENV REF_TEXT={os.environ.get('REF_TEXT', '<not set>')}")

    log("STEP 2/8: GPU & system check")
    log_gpu()

    log("STEP 3/8: Checking stage files")
    log_stage_contents("/stage")

    voice_sample = os.environ.get("VOICE_SAMPLE_PATH", "/stage/input/voice_sample.wav")
    script_path = os.environ.get("SCRIPT_PATH", "")
    text = os.environ.get("TEXT", "")
    output_dir = os.environ.get("OUTPUT_DIR", "/stage/output")

    if not os.path.isfile(voice_sample):
        log(f"FATAL: Voice sample not found: {voice_sample}")
        sys.exit(1)
    vs_size = os.path.getsize(voice_sample) / 1024
    log(f"Voice sample OK: {voice_sample} ({vs_size:.1f} KB)")

    if script_path and os.path.isfile(script_path):
        segment_pairs = extract_narration(script_path)
        segments = [t for t, _ in segment_pairs]
        section_breaks = [b for _, b in segment_pairs]
    elif text:
        segments = [text]
        section_breaks = [False]
        log(f"Using TEXT env var: {len(text)} chars")
    else:
        log("FATAL: No SCRIPT_PATH or TEXT provided.")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    log(f"Output dir: {output_dir}")

    log("STEP 4/8: Importing ML libraries")
    t0 = time.time()
    try:
        import torch
        log(f"  torch {torch.__version__} imported ({time.time()-t0:.1f}s)")
        log(f"  CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            log(f"  CUDA device: {torch.cuda.get_device_name(0)}")
            log(f"  CUDA version: {torch.version.cuda}")

        t1 = time.time()
        import soundfile as sf
        log(f"  soundfile imported ({time.time()-t1:.1f}s)")

        t2 = time.time()
        from qwen_tts import Qwen3TTSModel
        log(f"  qwen_tts imported ({time.time()-t2:.1f}s)")

        try:
            import flash_attn
            log(f"  flash_attn {flash_attn.__version__} available")
            use_flash = True
        except ImportError:
            log("  WARNING: flash_attn NOT installed, using default attention")
            use_flash = False
    except ImportError as e:
        log(f"FATAL: Missing dependency: {e}")
        traceback.print_exc()
        sys.exit(1)

    log("STEP 5/8: Auto-transcribing voice sample")
    ref_text = os.environ.get("REF_TEXT", "")
    if ref_text:
        log(f"  REF_TEXT provided via env var, skipping auto-transcription")
        log(f"  REF_TEXT: {ref_text[:120]}{'...' if len(ref_text)>120 else ''}")
    else:
        log("  No REF_TEXT provided, running Whisper auto-transcription...")
        ref_text = transcribe_voice_sample(voice_sample)
        if not ref_text:
            log("  Auto-transcription returned empty, falling back to x-vector only mode")

    log("STEP 6/8: Loading Qwen3-TTS model")
    hf_home = os.environ.get("HF_HOME", "")
    model_path = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    if hf_home and os.path.isfile(os.path.join(hf_home, "config.json")):
        model_path = hf_home
        log(f"  Loading model from stage: {model_path}")
    else:
        log(f"  Loading model from HuggingFace: {model_path}")
    log(f"  dtype: bfloat16, device: cuda:0, flash_attn: {use_flash}")
    log_mem()
    model_start = time.time()

    try:
        model_kwargs = dict(
            device_map="cuda:0",
            dtype=torch.bfloat16,
        )
        if use_flash:
            model_kwargs["attn_implementation"] = "flash_attention_2"

        model = Qwen3TTSModel.from_pretrained(
            model_path,
            **model_kwargs,
        )
        log(f"  Model loaded in {time.time()-model_start:.1f}s")
        log_mem()
        log_gpu()
    except Exception as e:
        log(f"FATAL: Model loading failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    log("STEP 7/8: Voice cloning")
    log(f"  Creating voice clone prompt (ref_text={'yes' if ref_text else 'no, x-vector only mode'})")
    clone_start = time.time()

    try:
        prompt = model.create_voice_clone_prompt(
            ref_audio=voice_sample,
            ref_text=ref_text if ref_text else None,
            x_vector_only_mode=not bool(ref_text),
        )
        log(f"  Voice clone prompt created in {time.time()-clone_start:.1f}s")
        log_mem()
    except Exception as e:
        log(f"FATAL: Voice clone prompt failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    total_chars = sum(len(s) for s in segments)
    log(f"  Generating audio for {len(segments)} segments, {total_chars} chars (~{total_chars/15:.0f}s of speech)")
    log(f"  Mode: per-segment generation for continuous progress visibility")

    log(f"  Running warmup generation to stabilize CUDA kernels and model state...")
    warmup_start = time.time()
    try:
        warmup_wavs, _ = model.generate_voice_clone(
            text="This is a short warmup pass.",
            language="English",
            voice_clone_prompt=prompt,
        )
        log(f"  Warmup done in {time.time()-warmup_start:.1f}s (output discarded)")
        del warmup_wavs
    except Exception as e:
        log(f"  Warmup failed (non-fatal): {e}")

    all_audio = []
    sr = None
    gen_start = time.time()

    for i, seg_text in enumerate(segments):
        seg_start = time.time()
        log(f"  [{i+1}/{len(segments)}] Generating: {seg_text[:60]}{'...' if len(seg_text)>60 else ''} ({len(seg_text)} chars)")
        try:
            wavs, seg_sr = model.generate_voice_clone(
                text=seg_text,
                language="English",
                voice_clone_prompt=prompt,
            )
            sr = seg_sr
            seg_duration = len(wavs[0]) / sr if sr > 0 else 0
            seg_time = time.time() - seg_start
            log(f"  [{i+1}/{len(segments)}] Done in {seg_time:.1f}s ({seg_duration:.1f}s audio, RTF={seg_time/seg_duration:.2f}x)" if seg_duration > 0 else f"  [{i+1}/{len(segments)}] Done in {seg_time:.1f}s")
            all_audio.append(wavs[0])
        except Exception as e:
            log(f"  [{i+1}/{len(segments)}] FAILED: {e}")
            traceback.print_exc()
            log(f"  Skipping segment {i+1}, continuing with remaining segments...")

    if not all_audio:
        log("FATAL: All segments failed. No audio generated.")
        sys.exit(1)

    import numpy as np

    def _trim_silence(audio, threshold_db=-40, min_samples=1024):
        amplitude = np.abs(audio).astype(np.float32)
        threshold = 10 ** (threshold_db / 20)
        above = amplitude > threshold
        if not np.any(above):
            return audio
        first = np.argmax(above)
        last = len(above) - 1 - np.argmax(above[::-1])
        first = max(0, first - min_samples)
        last = min(len(audio), last + min_samples)
        return audio[first:last]

    same_section_pause = int(0.4 * sr)
    new_section_pause = int(1.0 * sr)
    tail_pad_samples = int(0.5 * sr)
    combined = []
    for j, chunk in enumerate(all_audio):
        trimmed = _trim_silence(chunk)
        if j > 0:
            is_break = section_breaks[j] if j < len(section_breaks) else False
            gap = new_section_pause if is_break else same_section_pause
            combined.append(np.zeros(gap, dtype=trimmed.dtype))
        combined.append(trimmed)
    combined.append(np.zeros(tail_pad_samples, dtype=all_audio[0].dtype))
    final_audio = np.concatenate(combined)

    gen_time = time.time() - gen_start
    duration = len(final_audio) / sr if sr > 0 else 0
    log(f"  All segments generated in {gen_time:.1f}s")
    log(f"  Final audio: {duration:.1f}s, {len(final_audio)} samples, {sr} Hz")
    log(f"  Overall RTF: {gen_time/duration:.2f}x" if duration > 0 else "")
    log_mem()
    log_gpu()

    log("STEP 8/8: Saving output")
    output_wav = os.path.join(output_dir, "demo_narration_cloned.wav")
    sf.write(output_wav, final_audio, sr)
    size_mb = os.path.getsize(output_wav) / (1024 * 1024)
    log(f"  WAV saved: {output_wav} ({size_mb:.2f} MB)")

    try:
        output_mp3 = os.path.join(output_dir, "demo_narration_cloned.mp3")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", output_wav, "-q:a", "2", output_mp3],
            capture_output=True, text=True, check=True,
        )
        os.remove(output_wav)
        size_mb = os.path.getsize(output_mp3) / (1024 * 1024)
        log(f"  MP3 converted: {output_mp3} ({size_mb:.2f} MB)")
    except Exception as e:
        log(f"  ffmpeg conversion failed ({e}), keeping WAV")

    log("Output files:")
    log_stage_contents(output_dir)

    total_time = time.time() - job_start
    log("=" * 60)
    log(f"JOB COMPLETE in {total_time:.1f}s ({total_time/60:.1f} min)")
    log("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"UNHANDLED EXCEPTION: {e}")
        traceback.print_exc()
        sys.exit(1)
