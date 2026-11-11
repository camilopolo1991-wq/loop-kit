---
name: local-llm-low-vram
description: "Fit a local LLM on a small GPU; wire editor FIM."
version: 1.0.1
author: Hephaestus
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [llm, ollama, vram, gpu, autocomplete, fim, continue, benchmark]
    related_skills: [measuring-before-claiming, verifying-measurements]
---

# Local LLM on a low-VRAM machine

## When to Use

- Choosing a local model for a GPU with 8 GB of VRAM or less.
- Someone asks "what can my machine run" or "what local model for coding".
- Wiring local autocomplete (FIM) into an editor such as VS Code + Continue.
- A local model is slow and you need to know whether it spilled to CPU.

Do NOT use for multi-GPU or server-class deployments; the budgeting here assumes
one consumer card and a laptop's RAM.

Free VRAM is the only constraint that matters. Measure it before naming a model.
Everything else (RAM, CPU, disk) decides how badly you fail, not whether you fit.

## Measure first, always

```bash
nvidia-smi --query-gpu=name,memory.total,memory.free,compute_cap --format=csv
```

`memory.free`, not `memory.total`. The desktop compositor holds 300-500 MB before
you start. A "4 GB" card gives ~3.5 GB.

`compute_cap` gates the quant formats:

| cap | arch | consequence |
|---|---|---|
| 8.6 | Ampere | no FP8, no NVFP4. Those tags are dead weight |
| 8.9 | Ada | FP8 |
| 9.0+ | Hopper/Blackwell | FP8, NVFP4 |

**MLX tags are Apple Silicon only.** They appear in the Ollama library at tempting
sizes next to CUDA tags. They will not run on an NVIDIA card.

## Budget the VRAM

Model weights must leave room for KV cache. Rule: weights <= free VRAM minus 25%.
On 3.5 GB free, a 3.2 GB model loads but strands you at ~4K context.

**A model's advertised context is a capability, not an allocation.** A 256K-context
model on a 4 GB card runs at 4-16K. Say so instead of quoting the spec sheet.

Verify the split after loading, never assume:

```bash
ollama ps   # PROCESSOR column must say 100% GPU
```

Anything less than 100% means part of the model runs at system RAM bandwidth
(~51 GB/s on DDR4-3200 dual channel vs ~192 GB/s on a 3050). That is a 4x cliff,
not a gentle slope.

## Coding: two jobs, two answers

The question "what can I run for coding" hides two different problems.

**Autocomplete (FIM)** genuinely fits in 4 GB and is not a compromise. Continue's
own docs: beyond 10B params autocomplete does not improve, and thinking models are
worse because they blow the ~500 ms latency budget.

**Use the `-base` tag, never `-instruct`.** The instruct model rewrites the whole
file and wraps it in markdown fences. The base model fills the hole and stops.

**Agentic coding does not fit.** The smallest agentic coder is ~5.6 GB and they run
to 52 GB. Quantizing below q4 breaks syntax, which is the one thing code needs.
The correct architecture is local autocomplete + cloud agent, and it is what you
would build on a 24 GB card too: autocomplete fires 100x/minute and cannot pay
network latency; the agent runs 3x/hour and needs a big model.

## Keep-alive: measure the cold load

Cold model load is tens of seconds. The default 5-minute keep-alive means every
coffee break costs that again on the next keystroke. Measure it, then fix it:

```bash
# Windows, user level so it survives reboot
powershell -NoProfile -Command "[Environment]::SetEnvironmentVariable('OLLAMA_KEEP_ALIVE','8h','User')"
```

**The running server will not pick up a newly-written user env var.** Its parent
shell captured the old environment. Restart the server from a shell that sets the
var in-process, then confirm with `ollama ps` (UNTIL column), or you will report a
fix that did not land.

## Windows gotchas

| symptom | cause | fix |
|---|---|---|
| `code --install-extension` fails with `./Code.exe: No such file` | MSYS bash wrapper mangles the path | call `code.cmd` via `powershell -NoProfile -Command "& 'C:\...\code.cmd' ..."` |
| `cmd //c "..."` opens an interactive prompt | MSYS quote mangling | use powershell, not cmd |
| Ollama installer appears to hang | it is 1.6 GB and Inno Setup | `./OllamaSetup.exe /VERYSILENT /NORESTART /SUPPRESSMSGBOXES`, per-user, no admin |
| model pull killed by tool timeout | pulls run minutes | background it with notify, then `ollama list` to confirm |

Delete the installer afterwards. It is 1.6 GB on a disk that is probably full.

## Benchmark before claiming

Never quote tok/s from memory or a blog. Run it. Discard the first call: it includes
model load and will read as 1.5 tok/s next to a real 106.

```python
# POST /api/generate with stream=False returns nanosecond timings:
#   eval_count / (eval_duration/1e9)               -> generation tok/s
#   prompt_eval_count / (prompt_eval_duration/1e9) -> prompt tok/s
#   load_duration/1e9                              -> cold load, first call only
```

For autocomplete, measure **wall-clock latency over 5 runs** against the 500 ms
budget, not tok/s. Use a real FIM prompt (prefix + suffix of actual code) and check
the completion is correct AND that it stopped early. A 14-token answer that compiles
beats a 200-token one that rewrites the file.

## What you cannot verify yourself

The API path is verifiable end to end. **The completion popup rendering in the
editor is not.** Say that plainly and hand that check to the user rather than
reporting the integration as done.
