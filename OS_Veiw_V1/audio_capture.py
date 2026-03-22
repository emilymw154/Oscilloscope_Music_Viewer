import soundcard as sc
import numpy as np
import threading

def get_audio_devices():
    """Returns a list of available microphones and loopback devices."""
    try:
        mics = sc.all_microphones(include_loopback=True)
        return [{"id": m.id, "name": m.name} for m in mics]
    except Exception as e:
        print(f"Error enumerating devices: {e}")
        return []

class AudioCaptureThread(threading.Thread):
    def __init__(self, device_id=None, buffer_size=4096, sample_rate=44100):
        super().__init__()
        self.device_id = device_id
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.running = False
        self.data_buffer = np.zeros((self.buffer_size, 2))  # Left, Right channels
        self.lock = threading.Lock()
        self.mic = None

    def run(self):
        self.running = True
        
        try:
            if self.device_id:
                self.mic = sc.get_microphone(id=self.device_id, include_loopback=True)
            else:
                default_speaker = sc.default_speaker()
                mics = sc.all_microphones(include_loopback=True)
                for m in mics:
                    if default_speaker.name in m.name and "Loopback" in m.name:
                        self.mic = m
                        break
                if not self.mic:
                    self.mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
        except Exception as e:
            print(f"Error finding audio device: {e}")
            try:
                self.mic = sc.default_microphone()
            except:
                pass

        if not self.mic:
            print("Could not initialize any audio capture device.")
            self.running = False
            return

        print(f"Started audio capture on: {self.mic.name}")

        try:
            with self.mic.recorder(samplerate=self.sample_rate) as recorder:
                while self.running:
                    # Read frames. Blocks until frames are available
                    frames = recorder.record(numframes=1024)
                    
                    if len(frames.shape) == 1:
                        frames = np.column_stack((frames, frames))
                    elif frames.shape[1] > 2:
                        frames = frames[:, :2]
                    elif frames.shape[1] < 2:
                        frames = np.column_stack((frames, frames))
                        
                    with self.lock:
                        n = len(frames)
                        self.data_buffer = np.roll(self.data_buffer, -n, axis=0)
                        self.data_buffer[-n:] = frames
        except Exception as e:
            print(f"Audio stream stopped or errored: {e}")
        finally:
            self.running = False

    def get_data(self):
        with self.lock:
            return self.data_buffer.copy()

    def stop(self):
        self.running = False
        self.join(timeout=2.0)
