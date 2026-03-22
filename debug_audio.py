import soundcard as sc
import numpy as np
import time

def debug_loopback():
    print("Listing all loopback devices...")
    try:
        mics = sc.all_microphones(include_loopback=True)
    except Exception as e:
        print(f"Error: {e}")
        return
        
    print(f"Found {len(mics)} loopback devices.")
    for i, m in enumerate(mics):
        name = m.name
        print(f"\n--- Testing Device [{i}]: {name} ---")
        try:
            with m.recorder(samplerate=44100) as mic:
                max_amp = 0.0
                print("  Listening for 5 seconds...")
                for _ in range(50): # 5 seconds
                    data = mic.record(numframes=4410)
                    chunk_max = np.max(np.abs(data))
                    max_amp = max(max_amp, chunk_max)
                print(f"  Max amplitude: {max_amp:.4f}")
        except Exception as e:
             print(f"  Error reading: {e}")

if __name__ == "__main__":
    debug_loopback()
