import numpy as np
from abc import ABC, abstractmethod

import wave
import numpy as np
import tempfile
import os
import hashlib

from textual.events import Event
import logging
from io import BytesIO
import functools
import pickle
from pathlib import Path

# Yes it seems a bit silly to use pygame just for sound,
# but it's the most well supported cross-platform package
# for playing sound, without being *too* large
from pygame import mixer, sndarray
from gtts import gTTS

# Define the cache directory
# kwd_mark = object()     # sentinel for separating args from kwargs

def persistent_sound_cache(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Create the cache directory if it doesn't exist
        cache_dir = Path(tempfile.gettempdir()) / "inventree-tui" / "sounds"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Create a unique key for the function call
        kwd_mark = object()
        key = args + tuple(sorted(kwargs.items()))

        # Path for the pickle file that tracks the cache
        cache_index_path = cache_dir / "sound_cache_index.pkl"

        # Load the cache index
        if cache_index_path.exists():
            with open(cache_index_path, "rb") as f:
                cache_index = pickle.load(f)
        else:
            cache_index = {}

        # Check if the result is in the cache
        if str(key) in cache_index:
            sound_path = cache_index[str(key)]
            return mixer.Sound(sound_path)

        # If not in cache, call the original function
        sound = func(*args, **kwargs)

        # Save the sound to a temporary WAV file
        temp_path = cache_dir / f"sound_{os.urandom(8).hex()}.wav"

        # Get sound array and properties
        array_sample = sndarray.array(sound)
        n_channels = 1 if len(array_sample.shape) == 1 else array_sample.shape[1]
        sample_width = array_sample.dtype.itemsize
        frame_rate = mixer.get_init()[0]

        # Open a new wave file
        with wave.open(str(temp_path), "wb") as wav_file:
            # Set parameters
            wav_file.setnchannels(n_channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(frame_rate)

            # Write data
            wav_file.writeframes(array_sample.tobytes())

        # Update the cache index
        cache_index[str(key)] = str(temp_path)
        with open(cache_index_path, "wb") as f:
            pickle.dump(cache_index, f)

        return sound

    return wrapper

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

    def generate_sound(self):
        # Generate the melody
        samples = self.generate()
        # Normalize to 16-bit range
        samples = (samples * 32767).astype(np.int16)

        return sndarray.make_sound(samples)

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

    return melody.generate_sound()

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

    return melody.generate_sound()

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

    return melody.generate_sound()

@persistent_sound_cache
def tts(text, lang='en'):
    # Use gTTS to generate speech
    tts = gTTS(text=text, lang='en')
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)

    # Create an in-memory file-like object
    in_memory_file = BytesIO(mp3_fp.getvalue())

    # Load the in-memory file as a Pygame sound object
    sound = mixer.Sound(in_memory_file)
    return sound

# Generate the sounds
mixer.init(frequency=44100, size=-16, channels=1)

success = generate_success()
failure = generate_failure()

def play_sound(sound_name: str):
    if sound_name == "success":
        success.play()
        tts("success").play()
    elif sound_name == "failure":
        failure.play()
        tts("You fucked up").play()

class Sound(Event):
    def __init__(self, sender, name: str):
        super().__init__()
        self.sender = sender
        self.name = name
