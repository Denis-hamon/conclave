# Recording the demo GIF

The demo (`examples/demo.py`) is designed for terminal recording. It paces
output with `time.sleep(0.35)` between agent turns so it reads well at real-time
playback.

## Recommended tool: `vhs`

[vhs](https://github.com/charmbracelet/vhs) records a `.tape` script to GIF
deterministically — no live recording required.

### Install

```bash
brew install vhs
# or: go install github.com/charmbracelet/vhs@latest
```

### Record

```bash
cd conclave
vhs examples/demo.tape
# → outputs examples/demo.gif
```

## Alternative: `asciinema`

```bash
asciinema rec demo.cast -c "python examples/demo.py"
# convert to GIF with https://github.com/asciinema/agg
agg demo.cast examples/demo.gif
```

## Terminal settings

- Size: **120 × 35**
- Font: JetBrains Mono, Fira Code, or similar monospaced
- Theme: any dark theme with good contrast (Catppuccin Mocha recommended)
- Keep the prompt minimal so the banner panel fits cleanly

## Tips

- Re-run once before recording to warm caches and confirm output fits.
- If capturing live (asciinema), use `--idle-time-limit=2` to trim pauses.
- Commit the resulting GIF as `examples/demo.gif` — it is referenced by README.
