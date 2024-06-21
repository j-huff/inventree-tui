import numpy as np
from abc import ABC, abstractmethod

import wave
import numpy as np
import tempfile
import os
import hashlib

from textual.events import Event
import logging
import io

class ADSREnvelope:
    def __init__(self, attack_ms, decay_ms, sustain_level, release_ms):
        self.attack_ms = attack_ms
        self.decay_ms = decay_ms
        self.sustain_level = sustain_level
        self.release_ms = release_ms

    def apply(self, signal, sample_rate, duration_ms):
        total_samples = len(signal)
        attack_samples = int(self.attack_ms * sample_rate / 1000)
        decay_samples = int(self.decay_ms * sample_rate / 1000)
        release_samples = int(self.release_ms * sample_rate / 1000)
        
        # Calculate sustain samples based on the duration
        sustain_samples = total_samples - attack_samples - decay_samples - release_samples
        
        # Ensure sustain is not negative
        sustain_samples = max(0, sustain_samples)

        envelope = np.zeros(total_samples)
        
        # Attack
        attack_end = min(attack_samples, total_samples)
        envelope[:attack_end] = np.linspace(0, 1, attack_end)
        
        if attack_end < total_samples:
            # Decay
            decay_end = min(attack_samples + decay_samples, total_samples)
            envelope[attack_end:decay_end] = np.linspace(1, self.sustain_level, decay_end - attack_end)
            
            if decay_end < total_samples:
                # Sustain
                sustain_end = min(attack_samples + decay_samples + sustain_samples, total_samples)
                envelope[decay_end:sustain_end] = self.sustain_level
                
                # Release
                if sustain_end < total_samples:
                    envelope[sustain_end:] = np.linspace(self.sustain_level, 0, total_samples - sustain_end)

        return signal * envelope

class WaveGenerator(ABC):
    @abstractmethod
    def generate(self, frequency, duration_ms, sample_rate):
        pass

class SineGenerator(WaveGenerator):
    def generate(self, frequency, duration_ms, sample_rate):
        t = np.linspace(0, duration_ms / 1000, int(sample_rate * duration_ms / 1000), False)
        return np.sin(2 * np.pi * frequency * t)

class SquareGenerator(WaveGenerator):
    def __init__(self, duty_cycle=0.5):
        self.duty_cycle = duty_cycle

    def generate(self, frequency, duration_ms, sample_rate):
        t = np.linspace(0, duration_ms / 1000, int(sample_rate * duration_ms / 1000), False)
        
        # Generate a square wave using np.sign of a sine wave
        wave = np.sign(np.sin(2 * np.pi * frequency * t) - (2 * self.duty_cycle - 1))
        
        # Normalize to range [-1, 1]
        wave = wave / 2
        
        return wave

class Note:
    def __init__(self, frequency, duration_ms, adsr, generator):
        self.frequency = frequency
        self.duration_ms = duration_ms
        self.adsr = adsr
        self.generator = generator

    def generate(self, sample_rate):
        # Include release time in the total duration
        total_duration_ms = self.duration_ms + self.adsr.release_ms
        wave = self.generator.generate(self.frequency, total_duration_ms, sample_rate)
        return self.adsr.apply(wave, sample_rate, self.duration_ms)

class Melody:
    def __init__(self, sample_rate=44100):
        self.notes = []
        self.sample_rate = sample_rate

    def add_note(self, note, start_time_ms):
        self.notes.append((note, start_time_ms))

    def generate(self):
        if not self.notes:
            return np.array([])

        # Find the end time of the last note, including release time
        end_time_ms = max(start_time + note.duration_ms + note.adsr.release_ms 
                          for note, start_time in self.notes)
        total_samples = int(end_time_ms * self.sample_rate / 1000)
        
        melody = np.zeros(total_samples)

        for note, start_time_ms in self.notes:
            start_sample = int(start_time_ms * self.sample_rate / 1000)
            end_sample = start_sample + int((note.duration_ms + note.adsr.release_ms) * self.sample_rate / 1000)
            note_samples = note.generate(self.sample_rate)
            melody[start_sample:end_sample] += note_samples[:end_sample-start_sample]

        # Normalize to prevent clipping
        max_amplitude = np.max(np.abs(melody))
        if max_amplitude > 1:
            melody /= max_amplitude

        return melody

# Generates a temporary WAV file from the melody.
# If a temporary file with the same id_string and hash already exists
# then the name of the existing file will be returned
def melody_to_temp_wav(melody, id_string, sample_width=2):
    # Generate the melody
    samples = melody.generate()

    # Normalize to 16-bit range
    samples = (samples * 32767).astype(np.int16)

    # Create the /tmp/inventree-tui directory if it doesn't exist
    temp_dir = '/tmp/inventree-tui'
    os.makedirs(temp_dir, exist_ok=True)

    # Create a byte buffer and encode the WAV file
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(sample_width)  # 2 bytes per sample
        wav_file.setframerate(melody.sample_rate)
        wav_file.writeframes(samples.tobytes())

    # Get the encoded WAV data
    wav_data = buffer.getvalue()

    # Generate a hash of the encoded WAV data
    wav_hash = hashlib.md5(wav_data).hexdigest()

    # Check for existing files with the same id_string
    existing_files = [f for f in os.listdir(temp_dir) if f.startswith(id_string) and f.endswith('.wav')]
    
    for existing_file in existing_files:
        full_path = os.path.join(temp_dir, existing_file)
        with open(full_path, 'rb') as f:
            existing_hash = hashlib.md5(f.read()).hexdigest()
        if existing_hash == wav_hash:
            return full_path

    # Create a new temporary file
    temp_file = tempfile.NamedTemporaryFile(prefix=f"{id_string}_", suffix=".wav", dir=temp_dir, delete=False)

    try:
        # Write the WAV data to the file
        with open(temp_file.name, 'wb') as f:
            f.write(wav_data)

        return temp_file.name
    except Exception as e:
        # If an error occurs, close and remove the temporary file
        temp_file.close()
        os.unlink(temp_file.name)
        raise e

def generate_success():
# Create a sine wave generator
    sine_gen = SineGenerator()

# Create some ADSR envelopes
    short_env = ADSREnvelope(attack_ms=20, decay_ms=30, sustain_level=0.9, release_ms=80)
    long_env = ADSREnvelope(attack_ms=30, decay_ms=100, sustain_level=0.8, release_ms=200)

    tune = 1.3

# Create some notes
    note_c = Note(frequency=261.63*tune, duration_ms=80, adsr=short_env, generator=sine_gen)  # C4
    note_e = Note(frequency=329.63*tune, duration_ms=80, adsr=short_env, generator=sine_gen)  # E4
    note_g = Note(frequency=392.00*tune, duration_ms=300, adsr=long_env, generator=sine_gen)   # G4

# Create a melody
    melody = Melody()
    melody.add_note(note_c, start_time_ms=0)
    melody.add_note(note_e, start_time_ms=80)  # Overlaps with C
    melody.add_note(note_g, start_time_ms=160)  # Starts when C and E end


# Create a temporary WAV file
    temp_wav_path = melody_to_temp_wav(melody, "success")
    return temp_wav_path

def generate_reverse_success():
# Create a sine wave generator
    sine_gen = SineGenerator()

# Create some ADSR envelopes
    short_env = ADSREnvelope(attack_ms=20, decay_ms=30, sustain_level=0.9, release_ms=80)
    long_env = ADSREnvelope(attack_ms=30, decay_ms=100, sustain_level=0.8, release_ms=200)

    tune = 1.3

# Create some notes
    note_g = Note(frequency=392.00*tune, duration_ms=80, adsr=short_env, generator=sine_gen)   # G4
    note_e = Note(frequency=329.63*tune, duration_ms=80, adsr=short_env, generator=sine_gen)  # E4
    note_c = Note(frequency=261.63*tune, duration_ms=300, adsr=long_env, generator=sine_gen)  # C4

# Create a melody
    melody = Melody()
    melody.add_note(note_g, start_time_ms=0)
    melody.add_note(note_e, start_time_ms=80)
    melody.add_note(note_c, start_time_ms=160)


# Create a temporary WAV file
    temp_wav_path = melody_to_temp_wav(melody, "reverse-success")
    return temp_wav_path

def generate_failure():
# Create a sine wave generator
    square_gen = SquareGenerator()
    sine_gen = SineGenerator()

# Create some ADSR envelopes
    short_env = ADSREnvelope(attack_ms=20, decay_ms=30, sustain_level=0.9, release_ms=20)

    tune = 1

# Create some notes
    note_g = Note(frequency=392.00*tune, duration_ms=100, adsr=short_env, generator=sine_gen)   # G4
    note_g_sharp = Note(frequency=415.30*tune, duration_ms=100, adsr=short_env, generator=square_gen)  # G4 Sharp

# Create a melody
    melody = Melody()
    melody.add_note(note_g, start_time_ms=0)
    melody.add_note(note_g_sharp, start_time_ms=0)
    melody.add_note(note_g, start_time_ms=160)
    melody.add_note(note_g_sharp, start_time_ms=160)


# Create a temporary WAV file
    temp_wav_path = melody_to_temp_wav(melody, "failure")
    return temp_wav_path

def play_wav(file_path):
    os.system(f"paplay {file_path}")

# Create a temporary WAV file
success_temp_file = generate_success()

# Create a temporary WAV file
failure_temp_file = generate_failure()

def success_chime():
    play_wav(success_temp_file)

def failure_chime():
    play_wav(failure_temp_file)

def play_sound(sound_name: str):
    if sound_name == "success":
        success_chime()
    elif sound_name == "failure":
        failure_chime()

class Sound(Event):
    def __init__(self, sender, name: str):
        super().__init__()
        self.sender = sender
        self.name = name
