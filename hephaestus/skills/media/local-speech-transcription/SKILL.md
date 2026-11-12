---
name: local-speech-transcription
description: "Transcribe voice notes/audio locally with faster-whisper."
version: 1.0.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [audio, transcription, whisper, voice, speech-to-text]
---

# Local speech transcription

## When to Use

Load when a voice message arrives with "could not be transcribed automatically",
or when any local audio file (`.ogg`, `.m4a`, `.mp3`, `.wav`) needs turning into
text. Runs entirely on the host: the audio never leaves the machine, which is the
default expectation for a user's own voice notes and for anything work-related.

Never ask the user to retype a voice note. Transcribe it.

## Procedure

1. Probe what is present before installing anything:

       for c in whisper whisper-cli ffmpeg python3; do printf '%s: ' "$c"; command -v $c || echo MISSING; done
       python3 -c "import importlib.util as u; print({m: bool(u.find_spec(m)) for m in ['faster_whisper','whisper','torch']})"

2. If nothing is installed, `faster-whisper` is the cheapest working path — pure
   CTranslate2, no torch, CPU int8 is enough. **Install it into a dedicated venv
   rather than a shared interpreter**, so a later unrelated environment change
   cannot remove it:

       uv venv --python 3.12 ~/.hermes/venvs/whisper
       uv pip install --python ~/.hermes/venvs/whisper/bin/python faster-whisper

   `uv` needs no root and creates a working venv on hosts where
   `python3 -m venv` fails for lack of the system venv/ensurepip package — reach
   for it first rather than escalating to a package install. Give the install a
   generous timeout; it pulls a sizeable wheel set on first run.

   Model weights live in the shared HuggingFace cache and survive the package
   disappearing, so a reinstall is usually fast even when it looks like a fresh
   start — check the cache before assuming a long download.

3. Decode the audio yourself with `ffmpeg` and hand `transcribe()` a float array,
   rather than passing a path. faster-whisper's own path-decoding goes through
   PyAV, whose API drifts between major versions and raises an unexpected-keyword
   `TypeError` on a version mismatch that has nothing to do with the audio; the
   pinned-down older PyAV frequently will not build from source either. ffmpeg
   sidesteps the whole dependency and keeps the audio local:

       import subprocess, numpy as np
       raw = subprocess.run(
           [FFMPEG, '-nostdin', '-i', PATH, '-f', 's16le', '-ac', '1',
            '-acodec', 'pcm_s16le', '-ar', '16000', '-'],
           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
       audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0

4. Transcribe. `base` is the fast triage pass; go straight to `small` when the
   audio contains product names, hostnames or jargon:

       from faster_whisper import WhisperModel
       m = WhisperModel('small', device='cpu', compute_type='int8')
       segs, info = m.transcribe(audio, vad_filter=True, beam_size=5,
                                 initial_prompt='<domain nouns, comma separated>')
       for s in segs: print(f'[{s.start:6.1f}-{s.end:6.1f}] {s.text.strip()}')

   The model downloads on first use and is cached; later runs are much faster.
   Keep the whole thing in a script file rather than a shell one-liner — the
   domain prompt is long, and re-typing it per call is how it drifts.

5. Print `info.language` and `language_probability` alongside the text. A low
   probability means the transcript is a guess and must be flagged as one.

   **A misdetected LANGUAGE is the loudest available warning — on any low probability,
   re-run with the language forced, in each plausible language, and compare.** Auto-detect
   on short or quiet audio picks a language the speaker does not use, and the resulting
   text is fluent, confident and unrelated to what was said: one 4-second note detected as
   Indonesian at p=0.39 produced three mutually incompatible readings under auto, forced
   English and forced Spanish. Forcing the language is one extra argument
   (`m.transcribe(audio, language='en', ...)`) and the three readings together tell you
   whether any of them is trustworthy. Report the disagreement and ask, rather than
   shipping the one that reads best — for a bilingual speaker the plausible-sounding
   rendering is exactly the trap, because both languages produce grammatical output.

   Print `rms = float(np.sqrt((audio**2).mean()))` beside the duration while you are
   there. A quiet or clipped note explains a low probability and tells the speaker what to
   change; a normal level with a low probability means something else is wrong.

   **On a low RMS (roughly below 0.03), normalise with ffmpeg before transcribing rather
   than reaching for a bigger model.** Add `-af loudnorm=I=-16:TP=-1.5:LRA=11` to the
   decode in step 3: a quiet note transcribes as a few intelligible seconds followed by
   confabulation, and gain is the cheap fix for the cause. Report the pre- and
   post-normalisation RMS so the speaker learns their recording level is the problem.

6a. **Treat a repeated identical clause as the model confabulating over non-speech, and
   never quote it.** The signature is one phrase restated verbatim many times in a single
   segment ("I'm going to do a little bit of the same thing, but...") or a stray "Thanks
   for watching" — both are training-data filler emitted when the decoder is handed audio
   it cannot resolve, not a transcription of anything. Bucket the RMS per second to see
   where the real energy is; where the loop sits over a span that does carry energy, the
   audio is too degraded to read and the honest answer is that the span is unreadable.

6b. **A LARGER model that returns less text is more trustworthy than a smaller one that
   fills the gap.** Where `small` emits a long loop for a span and `medium` returns
   nothing for it, the silence is the correct reading: the bigger model declined to guess.
   Take the shorter transcript, state how many seconds went unresolved, and ask for the
   missing part to be restated rather than acting on the fuller-looking output.

6. Restate your reading of the instruction back to the user in one line and invite
   a correction before acting on it. A voice note is the least reliable input
   channel there is, and acting on a misheard instruction costs more than the
   confirmation. When one note contains several unrelated asks, enumerate them
   separately — a single restated paragraph routinely drops the second request.

## Pitfalls

- `initial_prompt` is the single highest-leverage knob for domain audio: without
  it, whisper renders unfamiliar proper nouns as common words ("cloud code" for
  "Claude Code", "e-herbors" for "Hermes"). Seed it with the product, host, and
  tool names the speaker is likely to use before blaming the model size.
- Bumping `base` to `small` on the same file is a cheap disambiguation pass, not
  a last resort. Run it whenever the `base` output contains a phrase that does not
  parse as English — that is almost always a mangled proper noun, not a mumble.
- Segment timestamps are load-bearing for a long note: quote the timestamp beside
  any instruction you act on, so a misheard span can be pointed at directly.
- Do not upload the audio to a hosted API to "check" a local transcript. A voice
  note may contain names, credentials read aloud, or client detail; the local pass
  plus a restated reading is the correct verification.
- `vad_filter=True` drops silence and lead-in noise. Keep it on by default, but
  **check the returned segments actually span `info.duration` before trusting the
  text**: VAD can classify quiet or low-energy speech as silence and drop whole
  spans, yielding a transcript that reads as complete while a chunk is missing.
  The tell is a gap between one segment's end and the next one's start, or a last
  segment ending well short of the duration. On any gap, re-run the same file with
  `vad_filter=False, condition_on_previous_text=False` and compare.
- Print `s.start` **and** `s.end` per segment, not just the start. Coverage gaps
  are invisible when only start times are shown.
- When two runs disagree on a span, report that span as CANNOT DETERMINE and ask
  for it again. Do not silently pick the more plausible-sounding rendering — a
  confident transcript of audio the model never heard is the worst failure here.
- **When only the opening seconds of a long note resolve, do the work the readable part
  asks for and flag the rest as lost in the same message.** A 100-second note whose first
  15 seconds name a deliverable is enough to act on; waiting for a re-record stalls, and
  silently producing the deliverable without saying that most of the note was unreadable
  hides the fact that any specifics in it — a format, an audience, a comparison — were
  never received. Deliver, then state the unresolved span and invite the missing detail.
- Run one model per call. Looping over two model sizes in a single foreground
  call routinely exceeds the tool timeout and loses both results; transcribe with
  one model, and background the run when the file is long.
- **Detach a backgrounded transcribe from the session, or lifecycle cleanup kills
  it mid-run.** A plain background job is a child of the agent's shell and dies
  with SIGTERM when the session ends, compacts, or recovers from an error —
  leaving a zero-byte output file that reads as a failed decode rather than an
  interrupted one. Launch it with `setsid nohup <python> <script> > out 2> err &`
  and, where the tool supports it, the persist-across-cleanup flag; then poll the
  output file rather than holding a foreground call open. A minutes-long model
  run is exactly the case where the session is most likely to be interrupted
  underneath it.
- Redirect stdout and stderr to **separate** files. Whisper's progress and
  library warnings go to stderr, so merging them means grepping the transcript
  out of noise; a clean stdout file can be read as the result directly.
- **Keep the transcriber script outside a scratch or cache directory — those are pruned
  on an idle timer and the script disappears mid-conversation.** A helper under a
  TMPDIR-style scratch path works all day and then fails with `can't open file` on the
  next voice note, which reads as a broken environment rather than a swept file. Store it
  beside the venv it needs, and when it does go missing, rewrite it rather than asking the
  user to retype the note — it is a dozen lines, and the domain `initial_prompt` is the
  only part worth preserving carefully.
- **Check what the instruction asks for against the current state before acting
  on it.** A spoken instruction describes what the speaker believes is true, and
  part of it is often already done — acting on the whole thing then re-applies a
  change or reports work that was not needed. Measure first, say which part is
  already satisfied, and act only on the remainder.
- **An empty transcript on a very short note is usually correct, not a tooling failure.**
  A helper that prints the decode line and the detected language but no text reads like a
  broken decoder, and the reflex is to retry with a bigger model and a different decode
  path. Check the duration and RMS first: a 3-second note at normal level carrying one
  short phrase is a complete reading, and VAD plus a low language probability can suppress
  it entirely. Re-run once with `vad_filter=False` and a forced language before touching
  anything else — that recovers the phrase in one call, where re-deriving the decode
  pipeline costs several.
- **Pass the decoded ARRAY, never a path or a `.wav` you just wrote — the PyAV mismatch
  is in faster-whisper's decoder, so converting the file first does not avoid it.** The
  reflex on `TypeError: open() got an unexpected keyword argument 'metadata_errors'` is to
  re-encode to a friendlier format and retry, which fails identically because the same
  decoder runs on the new file. Step 3's ffmpeg-to-numpy path is the fix; a helper script
  that already does it is the thing to copy rather than re-deriving the call inline, since
  the inline version is where this trap gets re-introduced. Writing a 16k mono `.wav` is
  still fine as an intermediate as long as YOU read it into an array (`wave` + `numpy`)
  and hand that to `transcribe()`.
- **A recollection in a voice note is evidence to test, not a claim to correct.** When
  the speaker says a thing used to work, or used to be stable, or was already decided,
  check the stored record before answering from your own fresh measurement — they have
  watched the system for months and their memory frequently beats a harness you built
  this hour. One such aside pointed directly at a defect in the current test fixture that
  the fresh numbers had attributed to the system under test.
- **Act on the instruction in the same turn you transcribe it, and keep the restatement
  to one line.** A wait on a long-running job is not a reason to defer: when the note
  says go, the expected response is the next concrete step plus a one-line reading of
  what was asked, not a summary of status the speaker can already see. Repeated status
  recaps in place of progress read as stalling.
