#!/usr/bin/env python3
"""Transcribe a voice note locally. Audio never leaves this box.

PyAV in this venv rejects faster_whisper's decoder call (metadata_errors kwarg),
so decode with ffmpeg to 16k mono s16le and hand numpy straight to the model.
"""
import subprocess, sys, os, numpy as np

import shutil
FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or os.path.join(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"), "tools", "ffmpeg")

def decode(path):
    p = subprocess.run(
        [FFMPEG, "-nostdin", "-loglevel", "error", "-i", path,
         "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-"],
        capture_output=True, timeout=300)
    if p.returncode != 0:
        raise SystemExit(f"ffmpeg failed: {p.stderr.decode()[:300]}")
    pcm = np.frombuffer(p.stdout, dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0

def main():
    src = sys.argv[1]
    audio = decode(src)
    print(f"[decoded {len(audio)/16000:.1f}s]", file=sys.stderr)

    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8",
                         download_root=os.path.join(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"), "models", "whisper"))

    prompt = ("Hermes, Claude Code, n8n, Postgres, PostgREST, Obsidian, Telegram, "
              "VPS, Docker, rubric, dimension, scoring, vault, skill, hook, "
              "transcript, <OWNER>, calibration, stability, "
              "deploy, container, hardening, migration, backup, snapshot.")

    segments, info = model.transcribe(
        audio, beam_size=5, vad_filter=True, initial_prompt=prompt)
    print(f"[lang={info.language} p={info.language_probability:.2f}]", file=sys.stderr)
    for s in segments:
        print(f"[{s.start:6.1f}s] {s.text.strip()}", flush=True)

if __name__ == "__main__":
    main()
