import math
import torch
import numpy as np
from transformers import WhisperForConditionalGeneration, WhisperProcessor, pipeline
import webrtcvad
import queue
import threading
import pyaudio

from utils import format_error_message

p = None

def load_models(source_language, destination_language, device):
    """
    Load the transcription model and the translation pipeline.
    """
    # Load the Whisper transcription model and processor
    transcription_model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-base").to(device)
    transcription_model.config.forced_decoder_ids = None
    processor = WhisperProcessor.from_pretrained("openai/whisper-base", clean_up_tokenization_spaces=False)

    # Load translation pipeline
    translation_pipeline = pipeline("translation", model=f"Helsinki-NLP/opus-mt-{source_language}-{destination_language}", device=device, clean_up_tokenization_spaces=False)

    return transcription_model, processor, translation_pipeline

def capture_audio(source_index, source_name, source_language, destination_language, callback, error_callback, executor):
    """
    Capture audio from the specified input device and send it for processing in real-time.
    """
    global p
    try:
        p = pyaudio.PyAudio()
        vad = webrtcvad.Vad()
        vad.set_mode(1)  # Set aggressiveness mode for VAD: 0 to 3 (3 is most aggressive)
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        input_device_index=source_index,
                        frames_per_buffer=160)  # Small chunks for responsiveness

        frames = []
        min_duration = 250 # in ms
        silence_threshold = 25  # Adjust based on desired sensitivity
        silent_time = float(0)
        speaking = False
        audio_queue = queue.Queue()

        def process_queue():
            while True:
                audio_data = audio_queue.get()
                if audio_data is None:  # Exit signal
                    break
                executor.submit(callback, audio_data, source_name, source_language, destination_language)
                audio_queue.task_done()

        # Start a thread to process the audio queue
        threading.Thread(target=process_queue, daemon=True).start()

        while True:
            data = stream.read(160, exception_on_overflow=False)

            # Detect speech
            is_speech = vad.is_speech(data, 16000)

            if is_speech:
                silent_time = float(0)
                speaking = True
            else:
                audio_data = np.frombuffer(data, dtype=np.int16)
                silent_time += audio_data.shape[-1] / float(16)

            # Accumulate speech frames until sufficient silence is detected
            if speaking:
                frames.append(data)
                audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
                if silent_time >= silence_threshold and audio_data.shape[-1] / float(16) >= min_duration:
                    audio_queue.put(audio_data.astype(np.float32) / np.iinfo(np.int16).max)
                    frames = []
                    speaking = False

    except Exception as e:
        error_callback(e)

    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        audio_queue.put(None)  # Signal the processing thread to exit

def process_audio_streaming(audio_data: np.ndarray, source_name: str, source_language: str, destination_language: str, transcription_model: WhisperForConditionalGeneration, processor: WhisperProcessor, translation_pipeline, message_queue):
    """
    Process the captured audio stream, including transcription and translation.
    """
    try:
        # Ensure the audio data is of sufficient length for STFT processing
        min_length = 30
        input = None
        # Process audio data with WhisperProcessor
        if audio_data.shape[-1] / 16000 < min_length:
            audio_data = np.pad(audio_data, (0, max(0, int(math.ceil((float(min_length) - audio_data.shape[-1] / float(16000)) * float(16000))))), 'constant')
            input = processor(
                audio_data,
                return_tensors="pt",
                return_attention_mask=True,
                sampling_rate=16000,
                language=source_language,
                device=transcription_model.device
            )
        else:
            input = processor(
                audio_data,
                return_tensors="pt",
                truncation=False,
                padding="longest",
                return_attention_mask=True,
                sampling_rate=16000,
                language=source_language,
                device=transcription_model.device
            )

        input_features = input.input_features.to(transcription_model.device)
        attention_mask = input.attention_mask.to(transcription_model.device)

        # Generate transcription IDs from input features using input_features argument
        generated_ids = transcription_model.generate(
            input_features=input_features,
            attention_mask=attention_mask,
            task='transcribe',
            language=source_language
        )

        # Decode the generated transcription IDs into text in the source language
        transcriptions = processor.batch_decode(generated_ids, skip_special_tokens=True)

        # Translate the transcription if needed
        translation = translation_pipeline(transcriptions[0])[0]['translation_text']

        # Send transcription and translation to the message queue
        message_queue.put((source_name, transcriptions[0], "left"))
        message_queue.put((source_name, translation, "right"))

    except Exception as e:
        # Handle errors and send error message to the queue
        error_message = f"Error processing audio: {format_error_message(e)}"
        message_queue.put((source_name, error_message, "left"))
