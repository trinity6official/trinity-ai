# Trinity Android Pre-Hardware Test

This profile lets you test Trinity on the **Samsung S24 Ultra before the M6 arrives**. It does not replace the production macOS/Ollama design.

## What this test proves

You can test now:

- local conversation through `llama.cpp`
- Trinity identity/personality prompt
- SQLite + Markdown durable memory
- memory recall after restarting the test harness
- Android speech-to-text through Termux:API
- Android text-to-speech through Termux:API
- local-only operation with API and Presence disabled

The phone model is temporary. Do not use a 3B-4B phone model to judge the final intelligence of the M6 version.

## 1. Install Termux

Use Termux and Termux:API from the **same distribution/signing family**. Grant Termux microphone permission when Android asks.

## 2. Put Trinity in Termux home

Android shared storage is not a good place to execute project scripts. Keep the project under Termux home, for example:

```bash
termux-setup-storage
cd ~
unzip ~/storage/downloads/trinity-ai-android-test.zip
cd trinity-ai-android-test
```

If your downloaded ZIP has a different filename, substitute that name.

## 3. Install the phone-test prerequisites

```bash
./scripts/install_android_test.sh
```

The installer uses the local Termux Python environment and prepares `llama-server`. If a Termux `llama-cpp` package is unavailable, it builds the official `llama.cpp` server locally.

## 4. Add a small GGUF model

Use a small instruct/chat model first—roughly **3B-4B Q4** is a sensible phone-test class. Put the `.gguf` under your Termux home directory.

Do not start with a large M6-target model on the phone.

## 5. Start the local model

In Termux session 1:

```bash
cd ~/trinity-ai-android-test
./scripts/start_android_model.sh ~/YOUR_MODEL.gguf
```

The script exposes only `127.0.0.1:8080` and aliases the model as `trinity-phone`.

## 6. Check readiness

Open a second Termux session:

```bash
cd ~/trinity-ai-android-test
./scripts/android_doctor.sh
```

The required checks are Termux, Python, `llama-server`, the Android profile, writable Trinity memory, and a reachable local model. Voice checks are optional warnings until Termux:API is installed and permitted.

## 7. Start Trinity test mode

```bash
./scripts/run_android_test.sh
```

Commands inside the console:

```text
/voice          capture one spoken utterance through Android STT
/speak          speak Trinity's last reply through Android TTS
/status         show model/voice readiness
/memory QUERY   inspect matching durable memory
/help           show commands
/quit           exit cleanly
```

## First acceptance test

Tell Trinity:

> Remember that my Samsung phone is only the temporary Trinity test device.

Then exit:

```text
/quit
```

Restart:

```bash
./scripts/run_android_test.sh
```

Ask:

> What did I tell you about this phone?

A correct answer validates the local model, Trinity conversation layer, SQLite memory write, persistent storage, and memory recall together.

## Voice test

Inside Trinity:

```text
/voice
```

Speak normally. After Trinity replies, run:

```text
/speak
```

This verifies Android STT → Trinity → local model → Android TTS.

## Vision

The current first-stage phone harness focuses on conversation, memory, and voice. Trinity's production vision/screen-awareness path remains targeted at the Mac. A phone multimodal profile can be added after the text/voice acceptance test is stable; `llama-server` itself supports multimodal input, but the model/projector choice should be tested separately because phone RAM is limited.

## What remains for the M6

The M6 commissioning still needs to verify final model quality/speed, Whisper/TTS choices, screen awareness, Accessibility control, macOS computer actions, launchd, and long-duration stability.
