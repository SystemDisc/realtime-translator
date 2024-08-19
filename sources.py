import pyaudio

# Initialize PyAudio
p = pyaudio.PyAudio()

# List all audio devices
info = p.get_host_api_info_by_index(0)
num_devices = info.get('deviceCount')

for i in range(num_devices):
    device_info = p.get_device_info_by_host_api_device_index(0, i)
    if device_info.get('maxInputChannels') > 0:
        print(f"Input Device Index {i}: {device_info.get('name')}")
    if device_info.get('maxOutputChannels') > 0:
        print(f"Output Device Index {i}: {device_info.get('name')}")

# Terminate PyAudio
p.terminate()
