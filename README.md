<div align="center">
  

  # Video Processing Pipeline Web Server
  
  A robust, local, web-based video processing pipeline powered by PyTorch, OpenAI's Whisper, and Flask.
  
  ![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)
  ![PyTorch](https://img.shields.io/badge/PyTorch-CUDA_12.1-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
  ![Flask](https://img.shields.io/badge/Flask-Web_UI-black?style=for-the-badge&logo=flask&logoColor=white)
  ![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)
  ![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
</div>

---

## Overview

This repository contains an end-to-end local web application designed to automate heavy video processing tasks. Featuring a web-based user interface, the system allows users to extract audio, generate transcriptions using Whisper, mathematically adjust SRT timings, upscale video resolution, and hardcode (burn) subtitles directly into media files. The architecture inherently supports multi-threaded job queues and intelligent hardware delegation across multiple GPUs and CPUs, providing real-time feedback via a Flask-served frontend.

## Key Features

* **AI-Powered Subtitling:** Utilizes OpenAI's Whisper models for high-accuracy audio extraction and transcription generation.
* **Intelligent Hardware Delegation:** Workloads can be distributed explicitly across available hardware resources (`cuda:0`, `cuda:1`) or fall back to system processors (`cpu`).
* **Automated Task Chaining:** Operations can be executed sequentially. Enabling the "Automate" parameter allows the pipeline to execute extraction, upscaling, and burning workflows automatically without manual intervention.
* **Mathematical SRT Synchronization:** Incorporates a custom processing engine to calculate and adjust subtitle timings, maintaining synchronization when source media playback speed is modified.
* **Asynchronous Processing:** Long-running processes are managed via Python's `threading` and `queue` modules, ensuring the Flask application remains responsive.
* **Real-Time State Management:** A dynamic frontend polls the server to provide live terminal logs, a dynamic progress bar, and precise Estimated Time of Arrival (ETA) calculations based on processing duration.
* **Automated Environment Initialization:** A dedicated batch script automates the creation of isolated virtual environments, deployment of CUDA-optimized dependencies, and server initialization.

## Architecture and Stack

* **Backend:** Python, Flask, Waitress (Production WSGI server).
* **Machine Learning:** PyTorch (CUDA 12.1), OpenAI Whisper.
* **Media Processing:** FFmpeg (Subprocess bindings for `ffprobe` and rendering).
* **Frontend:** HTML5, CSS3, JavaScript (Vanilla polling), Bootstrap 5.

## Prerequisites

Ensure the host system meets the following functional requirements:

1.  **Operating System:** Windows 10 or 11 (Required for the `run_app.bat` execution script).
2.  **Python:** Python 3.8 or higher installed and explicitly added to the system `PATH`.
3.  **FFmpeg:** FFmpeg binaries must be downloaded and the `bin` directory added to the system `PATH`. This is critical for `ffprobe` duration calculations and media stream manipulation.
4.  **Hardware:** An NVIDIA GPU supporting CUDA 12.1 is highly recommended for PyTorch hardware acceleration. CPU fallback is fully supported but will result in significantly increased processing times.

## Installation and Setup

Deployment is streamlined via a completely automated script. No manual virtual environment configuration is necessary.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/video-processing-pipeline.git
    cd video-processing-pipeline
    ```

2.  **Execute the Automated Setup:**
    Execute the `run_app.bat` file located in the root directory.
    
    The script will execute the following operations:
    * Detect or create a dedicated Python virtual environment (`venv`).
    * Upgrade the package installer (`pip`).
    * Install core web server dependencies (`Flask`, `Waitress`).
    * Install machine learning libraries natively linked to CUDA 12.1 (`torch`, `torchvision`, `torchaudio`).
    * Install the transcription engine (`openai-whisper`).
    * Initialize the Waitress production server and automatically launch the default web browser to the application's local network address.

    *Note: The initial deployment sequence requires downloading large dependencies (e.g., PyTorch). Subsequent initializations will execute rapidly.*

## Usage Guidelines

The application is accessible via the web interface, typically served at `http://127.0.0.1:5000`.

### 1. File Configuration
* **Input Path:** Define the absolute system path pointing to the source media file or a directory containing multiple media files.
* **Output Destination:** Select "Same as Input" to output adjacent to the source, or define a specific "Output Folder" path.

### 2. Workflow Selection
Select the initial operational phase using the provided navigation tabs:
* **Extract:** Initiates Whisper-based audio extraction and transcription. If "Automate" is enabled, the pipeline proceeds to Upscale, followed by Burn.
* **Upscale:** Initiates video upscaling algorithms. If "Automate" is enabled, the pipeline proceeds to Burn.
* **Burn:** Directly hardcodes existing SRT files into the corresponding media files.

### 3. Hardware Allocation
Select the specific computational hardware to allocate to the task queue. The background worker daemon will distribute the processing load across selected devices (`GPU 0`, `GPU 1`, `CPU`).

### 4. Process Control and Monitoring
* Initialize the queue by selecting **Start Processing**.
* The **Logs** interface provides raw standard output directly from the background thread.
* The **Progress Bar** and **ETA** metrics update continuously based on completion ratios.
* To safely terminate an active job without crashing the server, select **Cancel Process**. This triggers an asynchronous event flag recognized by the worker thread.

## Troubleshooting

* **Immediate Script Termination:** Verify that Python is correctly registered in the Windows `PATH` variable. Execute `python --version` within a standard command prompt to confirm.
* **FFmpeg/FFprobe Exceptions:** The application strictly requires FFmpeg. Ensure the binaries are installed and accessible globally via Environment Variables.
* **Degraded Performance:** Verify that GPU allocation is selected within the interface and that the host NVIDIA drivers are compatible with CUDA 12.1.
* **Static Interface Elements:** The frontend interface utilizes a 1000ms polling interval via JavaScript. Ensure JavaScript execution is permitted within the browser environment.

## License

This project is distributed under the MIT License. See the `LICENSE` file for detailed information.
