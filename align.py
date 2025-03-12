import os
import copy
from music21 import converter, stream, note, metadata, instrument, midi, meter

# ✅ Ensure FluidSynth DLL path is set (Windows users only)
try:
    os.add_dll_directory("C:\\ProgramData\\chocolatey\\bin")
    print("✅ FluidSynth DLL directory added")
except Exception as e:
    print(f"⚠️ Could not set FluidSynth DLL path: {e}")

# ✅ File Paths
INSTRUMENTAL_MIDI = "output/full_multi_instrument_song.mid"  # Full-length instrumental
LYRICS_FILE = "output/generated_lyrics.txt"  # AI-generated lyrics
FINAL_MIDI = "output/final_song_with_lyrics.mid"  # Final merged song
XML_OUTPUT_FILE = "output/final_song_with_lyrics.musicxml"  # For MuseScore visualization
SOUNDFONT_PATH = "C:\\Users\\ajeet\\Downloads\\GeneralUser_GS_1.472\\GeneralUser GS 1.472\\GeneralUser GS v1.472.sf2"  # Correct SoundFont

# ✅ Load MIDI file
def load_midi_file(filename):
    if not os.path.exists(filename):
        print(f"❌ ERROR: MIDI file '{filename}' not found!")
        exit()
    print(f"🎵 Loading MIDI file: {filename}")
    return converter.parse(filename)

# ✅ Load Lyrics
def load_generated_lyrics(filename):
    if not os.path.exists(filename):
        print(f"❌ ERROR: Lyrics file '{filename}' not found!")
        exit()
    with open(filename, "r", encoding="utf-8") as f:
        lyrics = f.read().strip().split()
    if not lyrics:
        print("❌ ERROR: Lyrics file is empty!")
        exit()
    print(f"📜 Loaded {len(lyrics)} words from lyrics file")
    return lyrics

# ✅ Create a vocal track with lyrics properly embedded
def create_vocal_track(instrumental_score, lyrics):
    print("🔄 Generating vocal track...")

    # Create a new track for vocals
    vocal_part = stream.Part()
    vocal_part.partName = "Vocals"
    vocal_part.insert(0, instrument.Choir())  # ✅ Corrected Instrument Name
    
    # Add time signature and measures to vocal part (fixing the "cannot process repeats" error)
    ts = meter.TimeSignature('4/4')
    vocal_part.insert(0, ts)

    # Extract the melody notes
    melody_notes = [n for n in instrumental_score.flatten().notes if isinstance(n, note.Note)]

    # Match lyrics with melody length
    if len(melody_notes) > len(lyrics):
        print(f"⚠️ Melody has more notes ({len(melody_notes)}) than lyrics ({len(lyrics)}). Repeating words!")
        lyrics = (lyrics * (len(melody_notes) // len(lyrics) + 1))[:len(melody_notes)]
    elif len(lyrics) > len(melody_notes):
        print(f"⚠️ Lyrics have more words ({len(lyrics)}) than notes ({len(melody_notes)}). Trimming extra words!")
        lyrics = lyrics[: len(melody_notes)]

    # Attach lyrics to notes and add to vocal part
    for i, n in enumerate(melody_notes):
        new_note = copy.deepcopy(n)  # Create a copy of the note
        new_note.lyric = lyrics[i]
        vocal_part.append(new_note)

    # Organize into measures (fixing the "cannot process repeats" error)
    vocal_part_with_measures = vocal_part.makeMeasures()
    
    return vocal_part_with_measures

# ✅ Merge the vocal track with the instrumental
def merge_tracks(instrumental_score, vocal_part):
    print("🎶 Merging vocals with instrumental track...")
    final_score = stream.Score()
    
    # Extract all parts from the instrumental score
    for part in instrumental_score.parts:
        final_score.insert(0, part)
    
    # Add vocal part
    final_score.insert(0, vocal_part)
    
    return final_score

# ✅ Save the final MIDI file properly
def save_final_midi(score, midi_filename, xml_filename):
    try:
        score.write("midi", fp=midi_filename)
        score.write("musicxml", fp=xml_filename)
        print(f"✅ Final song saved as: {midi_filename}")
        print(f"✅ MusicXML saved for MuseScore: {xml_filename}")
    except Exception as e:
        print(f"❌ ERROR: Could not save MIDI file: {e}")
        raise  # Re-raise to see full traceback

# ✅ Play the final song in Python using FluidSynth
def play_final_song(midi_file):
    if not os.path.exists(midi_file):
        print(f"❌ ERROR: MIDI file not found: {midi_file}")
        return

    print("🎶 Playing final song with vocals + instruments...")

    try:
        # Alternative approach using music21's built-in MIDI playback
        print("🎵 Opening MIDI file with your default MIDI player...")
        s = converter.parse(midi_file)
        s.show('midi')
        print("🎵 If playback doesn't start automatically, please open the MIDI file manually.")
        
    except Exception as e:
        print(f"❌ ERROR: Playback failed: {e}")
        print("Please open the MIDI file manually using your preferred MIDI player.")

# ✅ Main Execution
if __name__ == "__main__":
    print("🚀 Running Full-Length Song Generation Script...")

    # Step 1: Load MIDI and Lyrics
    instrumental = load_midi_file(INSTRUMENTAL_MIDI)
    lyrics = load_generated_lyrics(LYRICS_FILE)

    # Step 2: Generate Vocal Track
    vocal_track = create_vocal_track(instrumental, lyrics)

    # Step 3: Merge Vocal Track with Instrumental
    final_song = merge_tracks(instrumental, vocal_track)

    # Step 4: Save the Final MIDI File
    save_final_midi(final_song, FINAL_MIDI, XML_OUTPUT_FILE)

    # Step 5: Play the Final Song
    play_final_song(FINAL_MIDI)
