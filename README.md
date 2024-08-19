# Real-Time Audio Translator

## Overview

The Real-Time Audio Translator is a Python application that captures audio from selected input devices, transcribes the audio using the Whisper model, and then translates the transcription into a specified target language in real-time. The terminal interface is managed using `ncurses`, providing a user-friendly display of both the transcription and the translation.

## Features

- **Real-Time Audio Capture:** Capture audio from selected input devices.
- **Transcription:** Transcribe audio using the Whisper model.
- **Translation:** Translate the transcribed text using the OPUS-MT models.
- **Terminal Interface:** Display transcriptions and translations in a user-friendly terminal interface using `ncurses`.
- **Multi-language Support:** Supports multiple languages for both transcription and translation.

## Installation

### Prerequisites

- Python 3.10 or higher
- A working installation of `PyAudio`
- Other Python dependencies listed in `requirements.txt`

### Steps

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd realtime-translator
   ```
2. Create a virtual environment and activate it:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python main.py
   ```

## Usage

When you run the application, you will be prompted to:

1. **Select Audio Input Devices:** Choose the audio input devices you want to use.
2. **Specify Languages:** Choose the source language for transcription and the destination language for translation.

The terminal interface will display the real-time transcription and translation.

## File Descriptions

### `audio_config.py`

Handles audio source selection and language configuration. It prompts the user to select audio input devices and specify the source and destination languages.

### `audio_processing.py`

Manages the audio capture, transcription, and translation processes. It also handles the queuing of audio data to ensure only one process runs at a time.

### `main.py`

The entry point of the application. It manages the initialization of the terminal interface, the setup of models, and the main loop for processing audio.

### `sources.py`

Run this directly to view your audio interfaces.

### `terminal_interface.py`

Manages the terminal interface using `ncurses`. It displays transcriptions and translations in real-time and handles cleanup of terminal resources.

### `utils.py`

Provides utility functions such as error message formatting.

### `.editorconfig`

Configures coding styles such as indentation, charset, end-of-line characters, etc.

### `.gitignore`

Specifies files and directories to be ignored by Git.

### `requirements.txt`

Lists the Python packages required to run the application.

## Contributing

Contributions are welcome! Please fork this repository and submit a pull request with your improvements.

## License

This project is licensed under the MIT License.

## Acknowledgements

This project leverages the Whisper model for transcription and the OPUS-MT models for translation. Special thanks to the Hugging Face community for their contributions to these models.
