import curses
import threading
import queue
import sys
import time
from typing import Dict, List
from audio_config import select_audio_sources_and_languages
from audio_processing import capture_audio, load_models, process_queue
from terminal_interface import writer_thread, cleanup, display_intro
from concurrent.futures import ThreadPoolExecutor
from transformers import logging
import torch

def setup_model_output_to_ncurses(stdscr: curses.window, sources: List[Dict]) -> Dict[int, Dict[str, object]]:
    """
    Load models and display progress in real-time.

    Args:
        stdscr (curses.window): The ncurses window object.
        sources (List[Dict]): The list of audio sources and languages.

    Returns:
        Dict[int, Dict[str, object]]: A dictionary of loaded models keyed by source index.
    """
    try:
        logging.set_verbosity_error()
        # Determine the main device for hardware acceleration (GPU if available)
        device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        stdscr.addstr(f"Using device: {device}\n")
        stdscr.refresh()

        models = {}
        for source in sources:
            stdscr.addstr(f"Setting up models for {source['source_name']} (from {source['source_language']} to {source['destination_language']})...\n")
            stdscr.refresh()

            # Load models and store them in the dictionary using the correct index
            transcription_model, processor, translation_pipeline = load_models(
                source["source_language"], source["destination_language"], device=device
            )
            models[source['source_name']] = {
                "transcription_model": transcription_model,
                "processor": processor,
                "translation_pipeline": translation_pipeline
            }
            stdscr.addstr(f"Models for {source['source_name']} are ready.\n")
            stdscr.refresh()

            # Add a short delay to ensure output is visible
            time.sleep(1)
            stdscr.clear()
            stdscr.refresh()

        return models

    except Exception as e:
        cleanup(stdscr)
        print(f"An error occurred during model setup: {str(e)}")
        sys.exit(1)

def curses_main(stdscr: curses.window, models: Dict[int, Dict[str, object]], sources: List[Dict], error_queue: queue.Queue) -> None:
    """
    Main curses loop, handling the interface and real-time processing.

    Args:
        stdscr (curses.window): The ncurses window object.
        models (Dict[int, Dict[str, object]]): The dictionary of loaded models keyed by source index.
        sources (List[Dict]): The list of audio sources and languages.
        error_queue (queue.Queue): The queue for handling errors.
    """
    message_queue = queue.Queue()
    processing_queue = queue.Queue()

    writer = threading.Thread(target=writer_thread, args=(stdscr, message_queue))
    writer.daemon = True
    writer.start()

    threads = []
    try:
        with ThreadPoolExecutor() as executor:
            processing_thread = threading.Thread(target=process_queue, args=(executor, models, processing_queue, message_queue))
            processing_thread.start()

            for source in sources:
                model_info = models.get(source['source_name'])
                if model_info:
                    thread = threading.Thread(
                        target=capture_audio,
                        args=(
                            source['index'],
                            source['source_name'],
                            source['source_language'],
                            source['destination_language'],
                            processing_queue.put,
                            lambda e: error_queue.put(e),
                            executor
                        )
                    )
                    thread.start()
                    threads.append(thread)
                else:
                    stdscr.addstr(0, 0, f"No model found for source index: {source['index']}")
                    stdscr.refresh()

            while any(thread.is_alive() for thread in threads):
                try:
                    error = error_queue.get()
                    if error:
                        raise error
                except queue.Empty:
                    pass  # Continue checking thread statuses

            for thread in threads:
                thread.join()

            processing_thread.join()

    except Exception as e:
        cleanup(stdscr)
        print(f"Error occurred: {e}")
        sys.exit(1)

def main(stdscr: curses.window) -> None:
    """
    The main function wrapped by curses.wrapper.

    Args:
        stdscr (curses.window): The ncurses window object.
    """
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    display_intro(stdscr)

    stdscr.addstr("Loading languages...\n")
    stdscr.refresh()

    sources = select_audio_sources_and_languages()

    stdscr.clear()
    stdscr.refresh()

    models = setup_model_output_to_ncurses(stdscr, sources)

    error_queue = queue.Queue()

    curses_main(stdscr, models, sources, error_queue)

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, exiting.")
        sys.exit(0)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
