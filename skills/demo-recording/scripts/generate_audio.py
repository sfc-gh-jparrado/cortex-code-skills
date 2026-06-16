#!/usr/bin/env python3
"""
generate_audio.py - Generate MP3 narration from a recording script using edge-tts.

Extracts all quoted lines ("...") from a markdown recording script,
joins them with pauses, and synthesizes speech using Microsoft Edge Neural TTS.

Also supports listing available voices to discover new/updated options.

Usage:
    # List all available voices
    uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/generate_audio.py --list-voices

    # List en-US voices only
    uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/generate_audio.py --list-voices --locale en-US

    # Generate narration
    uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/generate_audio.py \
        --script RECORDING_SCRIPT.md \
        --output-dir ./output \
        --voices en-US-AndrewMultilingualNeural \
        --rate "+0%" --pitch "+0Hz"
"""

import argparse
import asyncio
import os
import sys


async def list_available_voices(locale_filter: str = None):
    import edge_tts

    voices = await edge_tts.list_voices()

    if locale_filter:
        voices = [v for v in voices if v.get("Locale", "").startswith(locale_filter)]

    voices.sort(key=lambda v: (v.get("Locale", ""), v.get("Gender", ""), v.get("ShortName", "")))

    current_locale = None
    for v in voices:
        loc = v.get("Locale", "")
        if loc != current_locale:
            current_locale = loc
            print(f"\n--- {loc} ---")
        tag = ""
        name = v["ShortName"]
        if "Multilingual" in name:
            tag = " [MULTILINGUAL - higher quality]"
        print(f"  {name:<45} {v.get('Gender', ''):<8}{tag}")

    print(f"\nTotal: {len(voices)} voices")
    if not locale_filter:
        print("Tip: Use --locale en-US to filter by locale")


async def generate(voice: str, text: str, output_file: str, rate: str, pitch: str):
    import edge_tts

    print(f"Generating: {voice} -> {output_file}")
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_file)
    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  Done: {output_file} ({size_mb:.2f} MB)")


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


async def main():
    parser = argparse.ArgumentParser(description="Generate MP3 narration or list available TTS voices")
    parser.add_argument("--list-voices", action="store_true", help="List all available edge-tts voices")
    parser.add_argument("--locale", default=None, help="Filter voices by locale (e.g., en-US, en-GB)")
    parser.add_argument("--script", help="Path to RECORDING_SCRIPT.md")
    parser.add_argument("--output-dir", help="Directory for output MP3 files")
    parser.add_argument("--voices", nargs="+", help="Edge-tts voice name(s)")
    parser.add_argument("--rate", default="+0%", help="Speech rate (default: +0%%)")
    parser.add_argument("--pitch", default="+0Hz", help="Pitch adjustment (default: +0Hz)")
    args = parser.parse_args()

    if args.list_voices:
        await list_available_voices(args.locale)
        return

    if not args.script or not args.output_dir or not args.voices:
        parser.error("--script, --output-dir, and --voices are required for audio generation")

    if not os.path.isfile(args.script):
        print(f"ERROR: Script not found: {args.script}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    full_narration = extract_narration(args.script)

    for voice in args.voices:
        safe_name = voice.replace("-", "_").lower()
        output_file = os.path.join(args.output_dir, f"demo_narration_{safe_name}.mp3")
        await generate(voice, full_narration, output_file, args.rate, args.pitch)

    print("\nAll done.")


if __name__ == "__main__":
    asyncio.run(main())
