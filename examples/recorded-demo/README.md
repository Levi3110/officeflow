# Recorded native demonstration

After the Screen Recording grant on 2026-10-17, all three privacy checks passed and real
screenshots were captured. A subsequent complete native run was recorded on display 1 with
Chrome and LibreOffice on that display.

The recorded workflow passed **22 actions, 5 expertise handoffs and all 7 activity checks**.
Twenty Calc cells, three recalculated formulas and the Writer report passed independent file
and source checks. Four corrections were independently recorded; input coverage has no gaps,
errors or drops. This is a functional demonstration, not a human-authenticity score.

The full video is **189.998 seconds, 1920×1080**, with no requested audio capture. Actual frames
were inspected at 19.06s (browser), 76.62s (Calc), 121.55s (Writer typing) and 174.93s (completed
report). The MP4 export preserves the recording's complete duration. The final static hold is
part of the fixed 190-second capture, rather than additional agent work.

Local artifacts, intentionally excluded from Git:

- `dist/synthetic-human-agent-demo.mp4`: playable MP4, about 27.4 MB.
- `runs/recorded-native-demo-final/demo.mov`: original uncut native recording.
- `runs/recorded-native-demo-final/video-qa/`: sampled frames and export metadata.
- The same run directory retains the full SQLite journal, audit, input/OS traces and screenshots.

This selected bundle includes the actual output files, measured metrics, settings, current
permission preflight, 7/7 assessment and video metadata/digests. It does not include video or
screenshot pixels. `chapters.json` derives approximate video offsets from recorded action
timestamps; it is not a frame-accurate annotation. Review and submit the local MP4 separately.

To reproduce, follow `docs/DEMO.md`. `scripts/record_demo.py` records a fresh workflow and
waits for the recorder's duration timer to finalize the movie. `scripts/video_artifact.swift`
exports MP4 and samples frames using AVFoundation. An earlier recorded workflow completed
correctly, but sending SIGINT to its recorder discarded the movie; the timed recording above
fixed that delivery issue. Failed capture attempts remain in local run folders.

These resource numbers include an active screen recorder and screenshots, so they should not
be compared directly to the original unrecorded run or the simulation core benchmark.
