import curses
import threading
import queue
import sys
import time
from audio_config import select_audio_sources_and_languages
from audio_processing import capture_audio, load_models, process_audio_streaming
from terminal_interface import writer_thread, cleanup, display_intro
from concurrent.futures import ThreadPoolExecutor
from transformers import logging
import torch

def setup_model_output_to_ncurses(stdscr: curses.window, sources):
    """
    Load models and display progress in real-time.
    """
    try:
        logging.set_verbosity_error()
        # Determine the main device for hardware acceleration (GPU if available)
        device = torch.device(torch.device("cudu") if torch.cuda.is_available() else torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu"))
        stdscr.addstr(f"Using device: {device}\n")
        stdscr.refresh()

        models = {}
        for i, source in enumerate(sources):
            stdscr.addstr(f"Setting up models for {source['source_name']} (from {source['source_language']} to {source['destination_language']})...\n")
            stdscr.refresh()

            # Load models and store them in the dictionary using the correct index
            transcription_model, processor, translation_pipeline = load_models(
                source["source_language"], source["destination_language"], device=device
            )
            models[source['index']] = {
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

def curses_main(stdscr: curses.window, models, sources, error_queue):
    """
    Main curses loop, handling the interface and real-time processing.
    """
    message_queue = queue.Queue()

    writer = threading.Thread(target=writer_thread, args=(stdscr, message_queue))
    writer.daemon = True
    writer.start()

    threads = []
    try:
        with ThreadPoolExecutor() as executor:
            for source in sources:
                model_info = models.get(source['index'])  # Use get() to avoid KeyError
                if model_info:
                    thread = threading.Thread(
                        target=capture_audio,
                        args=(
                            source['index'],
                            source['source_name'],
                            source['source_language'],
                            source['destination_language'],
                            lambda audio_data, name, src_lang, dest_lang: executor.submit(
                                process_audio_streaming,
                                audio_data,
                                name,
                                src_lang,
                                dest_lang,
                                model_info['transcription_model'],
                                model_info['processor'],
                                model_info['translation_pipeline'],
                                message_queue
                            ),
                            error_queue,
                            executor
                        )
                    )
                    thread.start()
                    threads.append(thread)
                else:
                    stdscr.addstr(0, 0, f"No model found for source index: {source['index']}")
                    stdscr.refresh()

            # Ensure the main loop keeps running until all threads have completed
            while any(thread.is_alive() for thread in threads):
                try:
                    error = error_queue.get(timeout=1)
                    if error:
                        raise error
                except queue.Empty:
                    pass  # Continue checking thread statuses

            # Ensure all threads are joined before exiting
            for thread in threads:
                thread.join()

    except Exception as e:
        cleanup(stdscr)
        print(f"Error occurred: {e}")
        sys.exit(1)

def main(stdscr):
    """
    The main function wrapped by curses.wrapper.
    """
    # Start ncurses and display introductory message
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    display_intro(stdscr)

    # Displaying a prompt message before running the prompt
    stdscr.addstr("Loading languages...\n")
    stdscr.refresh()

    # Allow prompts to work within the ncurses interface
    sources = select_audio_sources_and_languages()

    # Resume normal ncurses display after prompts
    stdscr.clear()
    stdscr.refresh()

    # Setup models and display progress in real-time
    models = setup_model_output_to_ncurses(stdscr, sources)

    # Create a queue for handling errors
    error_queue = queue.Queue()

    # Start the main interface
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
