# podmaster-sonia
High-performance Python pipeline using WebRTC VAD and native FFmpeg complex filters for automated podcast silence removal and professional mastering
podmaster-sonia

An accelerated audio post-production pipeline built for advanced podcast mastering and automated silence removal. podmaster-sonia leverages WebRTC Voice Activity Detection (VAD) for precision speech scanning and unifies heavy audio processing inside native FFmpeg complex filtergraphs to deliver fast, broadcast-standard results without generational quality loss.

✨ Key Features
🚀 Local Runtime Acceleration: Seamlessly mirrors cloud/network drives (like Google Drive) to local high-speed temporary storage to maximize I/O performance.

🎙️ AI-Powered Silence Purging: Uses low-overhead downsampled audio vectors specifically for WebRTC VAD tracking, protecting your original high-fidelity source from processing degradation.

🎛️ Integrated Mastering Chain: Applies a professional production stack natively within a single FFmpeg pass:

High-pass Filtering: Eliminates low-end mic rumble and ambient hum.

Downward Noise Gating (agate): Drops the floor on remaining cross-talk or background hiss.

Dynamic Compression (compand): Smooths out volume inconsistencies between speakers.

Two-Pass Loudness Normalization (loudnorm): Targets strict broadcast profiles (Standard target: -16 LUFS, -1.5 dBTP).

⚡ Filtergraph Optimization: Dynamically streams filter scripts to disk to bypass command-line argument bottlenecks on lengthy episodic recordings.

🛠️ Architecture Overview
The system processes files in an optimized, isolated 4-step loop:

[ Raw Audio Input ] 
       │
       ▼
 1. Local Staging   ──► Copy to fast-access temporary workspace
       │
       ▼
 2. Pass 1 Analysis ──► Linear evaluation of True Peak, I, & LRA metrics
       │
       ▼
 3. VAD Timeline    ──► Chunks audio into 30ms frames to map speech envelopes
       │
       ▼
 4. Native Assembly ──► Executes atomic slice, stitch, gate, compand, & master
       │
       ▼
[ Clean Mastered Output ]
🚀 Quick Start
Dependencies
Ensure you have Python 3.10+ and a system installation of FFmpeg.

Bash
pip install pydub webrtcvad
Usage
Configure your target data environment variables or paths directly inside the configuration block:

Python
drive_input_folder = "/path/to/your/raw_audio"
drive_output_folder = "/path/to/save/mastered_audio"
Run the pipeline:

Bash
python main.py
