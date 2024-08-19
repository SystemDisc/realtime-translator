import math
import time
import torch
import numpy as np
from transformers import WhisperForConditionalGeneration, WhisperProcessor, pipeline
import webrtcvad
import queue
import threading
import pyaudio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple

from utils import format_error_message

p = None

def load_models(source_language: str, destination_language: str, device: torch.device) -> Tuple[WhisperForConditionalGeneration, WhisperProcessor, pipeline]:
    transcription_model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-base").to(device)
    transcription_model.config.forced_decoder_ids = None
    processor = WhisperProcessor.from_pretrained("openai/whisper-base", clean_up_tokenization_spaces=False)

    translation_pipeline = pipeline("translation", model=f"Helsinki-NLP/opus-mt-{source_language}-{destination_language}", device=device, clean_up_tokenization_spaces=False)

    return transcription_model, processor, translation_pipeline

def capture_audio(source_index: int, source_name: str, source_language: str, destination_language: str, callback, error_callback, executor: ThreadPoolExecutor) -> None:
    global p
    try:
        p = pyaudio.PyAudio()
        vad = webrtcvad.Vad()
        vad.set_mode(1)  # Aggressiveness level

        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        input_device_index=source_index,
                        frames_per_buffer=160)  # Small chunks

        buffer = []
        silent_time = 0
        speaking_time = 0
        min_silent_duration = 0.1  # seconds
        min_duration = 30  # seconds for Whisper model
        time_threshold = 1
        is_speaking = False

        while True:
            data = stream.read(160, exception_on_overflow=False)
            is_speech = vad.is_speech(data, 16000)

            if is_speech:
                silent_time = 0
                is_speaking = True
            elif is_speaking:
                silent_time += 160 / 16000.0

            if is_speaking:
                buffer.append(data)
                speaking_time += 160 / 16000.0
                if silent_time >= min_silent_duration:
                    audio_data = np.frombuffer(b''.join(buffer), dtype=np.int16).astype(np.float32) / np.iinfo(np.int16).max
                    if len(audio_data) < 16000 * min_duration:
                        padding = np.zeros(16000 * min_duration - len(audio_data), dtype=np.float32)
                        audio_data = np.concatenate([audio_data, padding])

                    # Submit final chunk with a finalization flag
                    callback((source_name, audio_data, source_language, destination_language, True))

                    buffer = []
                    is_speaking = False
                elif speaking_time >= time_threshold:
                    audio_data = np.frombuffer(b''.join(buffer), dtype=np.int16).astype(np.float32) / np.iinfo(np.int16).max
                    callback((source_name, audio_data, source_language, destination_language, False))
            else:
                speaking_time = 0

    except Exception as e:
        error_callback(e)

    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

def process_audio_streaming(
    audio_data: np.ndarray,
    source_name: str,
    source_language: str,
    destination_language: str,
    transcription_model: WhisperForConditionalGeneration,
    processor: WhisperProcessor,
    translation_pipeline,
    message_queue: queue.Queue,
    final: bool = False
) -> None:
    """
    Process the captured audio stream, including transcription and translation.
    """
    try:
        inputs = processor(
            audio_data,
            return_tensors="pt",
            sampling_rate=16000,
            return_attention_mask=True,
            language=source_language
        )

        input_features = inputs.input_features.to(transcription_model.device)
        attention_mask = inputs.attention_mask.to(transcription_model.device)

        generated_ids = transcription_model.generate(
            input_features=input_features,
            attention_mask=attention_mask,
            task='transcribe',
            language=source_language
        )

        transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        translation = translation_pipeline(transcription)[0]['translation_text']

        message_queue.put((source_name, "Transcription", transcription, "left", final))
        message_queue.put((source_name, "Translation", translation, "right", final))

    except Exception as e:
        error_message = f"Error processing audio: {format_error_message(e)}"
        message_queue.put((source_name, None, error_message, "left", True))

def process_queue(
    executor: ThreadPoolExecutor,
    models: Dict[int, Dict[str, object]],
    processing_queue: queue.Queue,
    message_queue: queue.Queue
) -> None:
    processing_threads = {}
    while True:
        try:
            # Get the next message, blocking until one is available
            source_name, audio_data, source_language, destination_language, final = processing_queue.get()

            model_info = models[source_name]

            # If a thread is currently processing for this source, check for other messages
            if source_name in processing_threads and processing_threads[source_name].is_alive():
                found_final = final
                next_message = None
                current_message = (source_name, audio_data, source_language, destination_language, final)
                for _ in range(processing_queue.qsize()):
                    next_source_name, next_audio_data, next_source_language, next_destination_language, next_final = processing_queue.get()
                    if next_source_name != source_name or found_final:
                        if next_source_name in processing_threads and processing_threads[next_source_name].is_alive():
                            processing_queue.put((next_source_name, next_audio_data, next_source_language, next_destination_language, next_final))
                        else:
                            next_message = (next_source_name, next_audio_data, next_source_language, next_destination_language, next_final)
                    else:
                        if next_final:
                            found_final = True
                        current_message = (next_source_name, next_audio_data, next_source_language, next_destination_language, next_final)

                processing_queue.queue.appendleft(current_message)
                if next_message is not None:
                    processing_queue.queue.appendleft(next_message)

                time.sleep(0.001)
                continue

            processing_threads[source_name] = threading.Thread(
                target=process_audio_streaming,
                args=(
                    audio_data,
                    source_name,
                    source_language,
                    destination_language,
                    model_info['transcription_model'],
                    model_info['processor'],
                    model_info['translation_pipeline'],
                    message_queue,
                    final
                )
            )
            processing_threads[source_name].start()

        except Exception as e:
            print(f"Error in process_queue: {e}")
