# YouTube Channel Video Processor Master App

A robust, automated web application designed to streamline the post-production pipeline for YouTube channels. This tool provides a local web interface to handle heavy video processing tasks, including subtitle extraction, upscaling, and hardcoding, significantly reducing manual editing time.

## Core Features
* **Automated Processing Pipeline:** Chain multiple video processing tasks sequentially to prepare content for YouTube upload with minimal user intervention.
* **AI-Driven Transcription:** Integrates machine learning models to automatically extract or translate audio into accurate SRT subtitle files.
* **High-Quality Upscaling:** Utilizes FFmpeg for video scaling and enhancement, ensuring optimal playback quality on YouTube.
* **Dynamic Subtitle Burning:** Hardcodes subtitles directly into the video stream with custom styling and mathematical time-syncing for altered playback speeds.
* **Hardware Acceleration:** Intelligently routes heavy processing tasks to available NVIDIA GPUs (CUDA) to drastically reduce render times.

## Installation and Setup
This application is designed for Windows environments and requires Python 3.8+ and FFmpeg.

1. Clone the repository to your local machine.
2. Execute the `run_app.bat` script.
3. The script will automatically build a Python virtual environment, install necessary dependencies (including PyTorch and Flask), and launch the server.
4. The WebUI will open automatically in your default browser at `http://127.0.0.1:5000`.

## Technical Architecture
* **Frontend:** HTML5, Bootstrap 5, JavaScript
* **Backend:** Python, Flask, Waitress
* **Media Engine:** FFmpeg, Subprocess
* **Machine Learning:** PyTorch, OpenAI Whisper
