import sys
import pyaudio
import requests
from InquirerPy import prompt

def list_audio_sources():
    """
    List available audio input devices.

    Returns:
        list: A list of dictionaries, each containing the name and index of an audio input device.
    """
    p = pyaudio.PyAudio()
    sources = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            device_name = f"{info['name']} (Index: {i})"
            sources.append({"name": device_name, "index": i})
    p.terminate()
    return sources

def fetch_opus_mt_models():
    """
    Fetch the list of available OPUS-MT models from Hugging Face.

    Returns:
        list: A list of models from the Hugging Face API.
    """
    try:
        response = requests.get('https://huggingface.co/api/models?search=opus-mt')
        response.raise_for_status()
        models = response.json()
        return models
    except requests.RequestException as e:
        print(f"Error fetching OPUS-MT models: {e}")
        sys.exit(1)

def extract_languages(models):
    """
    Extract source and destination languages from the OPUS-MT models.

    Args:
        models (list): A list of models from the Hugging Face API.

    Returns:
        tuple: A sorted list of source languages and a dictionary mapping source languages to sets of destination languages.
    """
    source_languages = set()
    destination_languages = {}

    for model in models:
        model_id = model['modelId']
        if model_id.startswith('Helsinki-NLP/opus-mt'):
            parts = model_id.split('-')
            if len(parts) == 5:  # Ensure the format Helsinki-NLP/opus-mt-{source}-{destination}
                source = parts[3]
                destination = parts[4]
                source_languages.add(source)
                if source not in destination_languages:
                    destination_languages[source] = set()
                destination_languages[source].add(destination)

    return sorted(source_languages), destination_languages

def select_audio_sources_and_languages():
    """
    Prompt the user to select audio input devices and their corresponding source and destination languages.

    Returns:
        list: A list of selected audio sources with their respective languages.
    """
    models = fetch_opus_mt_models()
    source_languages, destination_languages = extract_languages(models)
    
    if not source_languages:
        print("No valid source languages found.")
        sys.exit(1)
    
    sources = list_audio_sources()

    if not sources:
        print("No audio input devices found.")
        sys.exit(1)

    choices = [{"name": source["name"], "value": source["index"]} for source in sources]

    questions = [
        {
            "type": "checkbox",
            "message": "Select the audio input devices you want to use:",
            "choices": choices,
            "name": "audio_sources",
            "instruction": "Use space to select and enter to confirm.",
        }
    ]

    answers = prompt(questions)
    selected_sources = []

    if "audio_sources" in answers and answers["audio_sources"]:
        for idx in answers["audio_sources"]:
            source_name = next(source["name"] for source in sources if source["index"] == idx)

            language_question = [
                {
                    "type": "fuzzy",
                    "message": f"Select the source language for audio source '{source_name}':",
                    "name": "source_language",
                    "choices": source_languages,
                }
            ]

            source_answer = prompt(language_question)
            selected_source_language = source_answer["source_language"]

            if not destination_languages[selected_source_language]:
                print(f"No valid destination languages found for source language '{selected_source_language}'.")
                sys.exit(1)

            destination_question = [
                {
                    "type": "fuzzy",
                    "message": f"Select the destination language for translation for '{source_name}':",
                    "name": "destination_language",
                    "choices": sorted(destination_languages[selected_source_language]),
                }
            ]

            destination_answer = prompt(destination_question)
            selected_destination_language = destination_answer["destination_language"]

            selected_sources.append({
                "index": idx,
                "source_name": source_name,
                "source_language": selected_source_language,
                "destination_language": selected_destination_language
            })

    if not selected_sources:
        print("No valid audio sources selected.")
        sys.exit(1)

    return selected_sources
