import soundcard as sc
import numpy as np
import time

def test_loopback():
    print("Default speaker:", sc.default_speaker().name)
    mics = sc.all_microphones(include_loopback=True)
    
    # Try to find the loopback device corresponding to the default speaker
    loopback_mic = None
    default_name = sc.default_speaker().name
    for m in mics:
        if default_name in m.name and "Loopback" in m.name:
            loopback_mic = m
            break
            
    if not loopback_mic:
        print("Explicit loopback not found, trying default speaker loopback method...")
        try:
            loopback_mic = sc.get_microphone(id=str(default_name), include_loopback=True)
        except Exception as e:
            print("Failed:", e)
            print("Available mics:", [m.name for m in mics])
            return

    print("Chosen loopback mic:", loopback_mic.name)
    
    try:
        with loopback_mic.recorder(samplerate=44100) as mic:
            print("Recording started. Play some audio now...")
            for i in range(10):
                data = mic.record(numframes=1024)
                max_val = np.max(np.abs(data))
                print(f"Frame {i}: max amplitude {max_val:.4f}")
                time.sleep(0.1)
    except Exception as e:
        print("Recording error:", e)

if __name__ == "__main__":
    test_loopback()
