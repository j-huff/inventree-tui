from .generation import *

def success():
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

def reverse_success():
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

def failure():
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
