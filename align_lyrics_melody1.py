import os
import copy
from music21 import converter, stream, note, midi, metadata, tempo, chord, instrument
import music21

# Try to set FluidSynth DLL path
try:
    # Windows-specific path for FluidSynth DLL
    if os.path.exists("C:\\ProgramData\\chocolatey\\bin"):
        os.add_dll_directory("C:\\ProgramData\\chocolatey\\bin")
    print("✅ FluidSynth DLL directory added")
except Exception as e:
    print(f"⚠️ Note: Could not set FluidSynth DLL path: {e}")
    print("This is normal on non-Windows systems or if FluidSynth is installed differently")

# ✅ File Paths
MIDI_FILE = "output/generated_melody.mid"        # Instrumental file
LYRICS_FILE = "output/generated_lyrics.txt"      # Generated lyrics file
OUTPUT_FILE = "output/final_song_with_lyrics.mid"  # Final unified MIDI file
XML_OUTPUT_FILE = "output/aligned_song.musicxml"  # MusicXML for score view
KARAOKE_OUTPUT_FILE = "output/karaoke_song.kar"   # Karaoke MIDI file
SOUNDFONT_PATH = "C:\\Users\\ajeet\\Downloads\\GeneralUser_GS_1.472\\GeneralUser GS 1.472\\GeneralUser GS v1.472.sf2"  # SoundFont Path

def load_midi_file(filename):
    """Load the generated melody MIDI file into a music21 stream."""
    if not os.path.exists(filename):
        print(f"❌ ERROR: MIDI file '{filename}' not found!")
        exit()
    print(f"Loading MIDI file: {filename}")
    return converter.parse(filename)

def load_generated_lyrics(filename):
    """Load generated lyrics from a text file."""
    if not os.path.exists(filename):
        print(f"❌ ERROR: Lyrics file '{filename}' not found!")
        exit()
   
    with open(filename, "r", encoding="utf-8") as f:
        lyrics = f.read().strip().split()  # Split into words
        if not lyrics:
            print("❌ ERROR: Lyrics file is empty!")
            exit()
    
    print(f"Loaded {len(lyrics)} words from lyrics file")
    return lyrics

def debug_midi_file(midi_file):
    """Analyze a MIDI file for debugging purposes."""
    print(f"\n🔍 Debugging MIDI file: {midi_file}")
    
    if not os.path.exists(midi_file):
        print(f"❌ ERROR: MIDI file not found: {midi_file}")
        return
        
    try:
        # Try using mido for low-level MIDI checking
        import mido
        midi = mido.MidiFile(midi_file)
        
        print(f"MIDI format: {midi.type}")
        print(f"Number of tracks: {len(midi.tracks)}")
        
        for i, track in enumerate(midi.tracks):
            print(f"\nTrack {i}: {track.name}")
            
            # Count different message types
            note_on = 0
            note_off = 0
            program_change = 0
            lyrics = 0
            
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    note_on += 1
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    note_off += 1
                elif msg.type == 'program_change':
                    program_change += 1
                    print(f"  Program change: channel={msg.channel}, program={msg.program}")
                elif msg.type == 'lyrics':
                    lyrics += 1
                    
            print(f"  Note on: {note_on}, Note off: {note_off}")
            print(f"  Program changes: {program_change}, Lyrics: {lyrics}")
            
    except ImportError:
        print("mido package not installed. Install with: pip install mido")
    except Exception as e:
        print(f"Error analyzing MIDI with mido: {e}")
    
    # Also try with music21
    try:
        midi_data = converter.parse(midi_file)
        print(f"\nMusic21 analysis:")
        print(f"Parts: {len(midi_data.parts)}")
        
        for i, part in enumerate(midi_data.parts):
            print(f"Part {i}: {part.partName if part.partName else 'Unnamed'}")
            print(f"  Instrument: {part.getInstrument()}")
            print(f"  Elements: {len(part.elements)}")
            
            # Count notes and lyrics
            notes = 0
            notes_with_lyrics = 0
            
            for elem in part.flatten():
                if isinstance(elem, note.Note):
                    notes += 1
                    if elem.lyric:
                        notes_with_lyrics += 1
            
            print(f"  Notes: {notes}, Notes with lyrics: {notes_with_lyrics}")
            
    except Exception as e:
        print(f"Error analyzing MIDI with music21: {e}")

def align_lyrics_with_melody(melody_stream, lyrics):
    """
    Create a new score with separate parts for melody and vocals.
    """
    print("🔄 Creating aligned score with vocals...")
    
    # Start with a fresh score
    new_score = stream.Score()
    
    # Create melody part
    melody_part = stream.Part()
    melody_part.partName = "Piano"  # Name it explicitly
    melody_part.id = 'piano'
    
    # Add piano instrument
    piano_inst = instrument.Piano()
    melody_part.insert(0, piano_inst)
    
    # Create vocal part
    vocal_part = stream.Part()
    vocal_part.partName = "Vocals"  # Name it explicitly
    vocal_part.id = 'vocals'
    
    # Add choir instrument
    choir_inst = instrument.Choir()
    vocal_part.insert(0, choir_inst)
    
    # Find all playable notes
    notes_and_chords = [n for n in melody_stream.flatten() if isinstance(n, (note.Note, chord.Chord))]
    
    if not notes_and_chords:
        print("❌ ERROR: No notes or chords found in the melody!")
        exit()
    
    # Copy all non-note elements (time signatures, key signatures, etc.)
    for element in melody_stream.flatten():
        if not isinstance(element, (note.Note, chord.Chord, note.Rest)):
            melody_part.insert(element.offset, copy.deepcopy(element))
            vocal_part.insert(element.offset, copy.deepcopy(element))
    
    # Handle lyrics length mismatch
    if len(notes_and_chords) > len(lyrics):
        print(f"⚠️ Melody has more notes ({len(notes_and_chords)}) than words ({len(lyrics)}). Repeating words!")
        repeat_count = (len(notes_and_chords) // len(lyrics)) + 1
        extended_lyrics = lyrics * repeat_count
        lyrics = extended_lyrics[: len(notes_and_chords)]
    elif len(lyrics) > len(notes_and_chords):
        print(f"⚠️ Lyrics have more words ({len(lyrics)}) than notes ({len(notes_and_chords)}). Trimming extra words!")
        lyrics = lyrics[: len(notes_and_chords)]
    
    # Add instrumental notes to the melody part
    for element in notes_and_chords:
        melody_part.insert(element.offset, copy.deepcopy(element))
    
    # Create vocal notes with lyrics
    for i, musical_element in enumerate(notes_and_chords):
        if i < len(lyrics):
            # Create vocal note
            if isinstance(musical_element, note.Note):
                vocal_note = note.Note(musical_element.pitch)
            else:  # chord
                vocal_note = note.Note(musical_element.pitches[-1])  # Use highest note
            
            # Copy duration and timing
            vocal_note.duration = copy.deepcopy(musical_element.duration)
            
            # Set lyrics and max volume
            vocal_note.lyric = lyrics[i]
            vocal_note.volume = music21.volume.Volume(velocity=127)  # Max volume
            
            # Add to vocal part at correct offset
            vocal_part.insert(musical_element.offset, vocal_note)
    
    # Verify parts have content
    if len(melody_part.elements) == 0:
        print("⚠️ WARNING: Melody part is empty!")
    if len(vocal_part.elements) == 0:
        print("⚠️ WARNING: Vocal part is empty!")
    else:
        print(f"✅ Added {sum(1 for n in vocal_part.flatten() if isinstance(n, note.Note) and n.lyric)} notes with lyrics")
    
    # Add both parts to the score
    new_score.insert(0, melody_part)
    new_score.insert(0, vocal_part)
    
    # Add metadata
    md = metadata.Metadata()
    md.title = "Song with Vocals"
    new_score.insert(0, md)
    
    return new_score

def verify_midi_parts(midi_file):
    """Check if the MIDI file contains the expected parts."""
    print("🔍 Verifying MIDI file structure...")
    
    try:
        from music21 import converter
        midi_data = converter.parse(midi_file)
        
        print(f"📊 MIDI file contains {len(midi_data.parts)} parts:")
        has_vocal_part = False
        
        for i, part in enumerate(midi_data.parts):
            part_name = part.partName if part.partName else f"Part {i}"
            print(f"  - Part {i}: {part_name}")
            
            # Safer check for part.id
            if hasattr(part, 'id') and isinstance(part.id, str) and 'vocal' in part.id.lower():
                has_vocal_part = True
                print(f"    ✅ Vocal part identified by ID: {part.id}")
            
            # Check instrument
            instr = part.getInstrument()
            if instr:
                print(f"    Instrument: {instr}")
                if isinstance(instr, instrument.Choir) or isinstance(instr, instrument.Voice):
                    has_vocal_part = True
                    print(f"    ✅ Vocal instrument found: {instr}")
            
            # Check for lyrics
            notes_with_lyrics = 0
            total_notes = 0
            for n in part.flatten().notes:
                total_notes += 1
                if hasattr(n, 'lyric') and n.lyric:
                    notes_with_lyrics += 1
            
            if total_notes > 0:
                print(f"    Notes: {total_notes}, Notes with lyrics: {notes_with_lyrics}")
                if notes_with_lyrics > 0:
                    has_vocal_part = True
                    print(f"    ✅ Found {notes_with_lyrics} notes with lyrics")
        
        if has_vocal_part:
            print("✅ Vocal part detected in the MIDI file")
        else:
            print("⚠️ No vocal part detected! Vocals may not play!")
        
        return True
    except Exception as e:
        print(f"❌ ERROR checking MIDI structure: {e}")
        import traceback
        traceback.print_exc()
        return False

def save_midi_with_lyrics(midi_stream, midi_filename, xml_filename, karaoke_filename):
    """Save the score in multiple formats."""
    try:
        # Save as MIDI
        midi_stream.write("midi", fp=midi_filename)
        print(f"✅ Aligned song saved as {midi_filename}")
        
        # Save as MusicXML
        midi_stream.write("musicxml", fp=xml_filename)
        print(f"✅ Aligned song also saved as {xml_filename} (for clearer lyric display)")
        
        # Save as Karaoke MIDI
        midi_stream.write("midi", fp=karaoke_filename)
        print(f"✅ Karaoke version saved as {karaoke_filename} (for lyric playback)")
        
        # Verify the MIDI file was created successfully
        if not os.path.exists(midi_filename):
            print(f"❌ ERROR: MIDI file not created at {midi_filename}")
        else:
            print(f"✅ MIDI file verified: {os.path.getsize(midi_filename)} bytes")
            
    except Exception as e:
        print(f"❌ ERROR: Could not save files: {e}")
        import traceback
        traceback.print_exc()

def play_final_song(midi_file):
    """Play the MIDI file with multiple fallback options."""
    # Check if file exists
    if not os.path.exists(midi_file):
        print(f"❌ ERROR: MIDI file not found: {midi_file}")
        return
    
    print(f"🎵 File size: {os.path.getsize(midi_file)} bytes")
    
    # Try FluidSynth first
    try_fluidsynth = True
    try_pygame = True
    
    if try_fluidsynth:
        try:
            import fluidsynth
            print("Using FluidSynth for playback...")
            
            fs = fluidsynth.Synth()
            
            # Try different audio drivers
            drivers = ["dsound", "alsa", "coreaudio", "portaudio"]
            success = False
            
            for driver in drivers:
                try:
                    print(f"Trying FluidSynth with {driver} driver...")
                    fs.start(driver=driver)
                    success = True
                    print(f"✅ FluidSynth started with {driver} driver")
                    break
                except Exception as e:
                    print(f"Driver {driver} failed: {e}")
            
            if not success:
                try:
                    print("Trying FluidSynth with default driver...")
                    fs.start()
                    success = True
                    print("✅ FluidSynth started with default driver")
                except Exception as e:
                    print(f"Default driver failed: {e}")
            
            if not success:
                print("❌ Could not start FluidSynth with any audio driver")
                fs.delete()
                raise Exception("No working audio driver")
            
            # Load SoundFont
            if not os.path.exists(SOUNDFONT_PATH):
                print(f"❌ SoundFont not found: {SOUNDFONT_PATH}")
                fs.delete()
                raise Exception("SoundFont not found")
            
            print(f"Loading SoundFont: {SOUNDFONT_PATH}")
            sfid = fs.sfload(SOUNDFONT_PATH)
            
            if sfid == -1:
                print("❌ Failed to load SoundFont")
                fs.delete()
                raise Exception("SoundFont loading failed")
            
            print("✅ SoundFont loaded successfully")
            
            # Configure multiple channels to ensure vocals are heard
            # Try different instruments for vocals
            print("Setting up instruments on all channels...")
            fs.program_select(0, sfid, 0, 0)     # Piano (channel 0)
            fs.program_select(1, sfid, 0, 52)    # Choir Aahs (channel 1)
            fs.program_select(2, sfid, 0, 54)    # Synth Voice (channel 2)
            fs.program_select(3, sfid, 0, 53)    # Voice Oohs (channel 3)
            fs.program_select(4, sfid, 0, 85)    # Lead 5 (charang) (channel 4)
            
            # Play the MIDI file
            print(f"Playing MIDI file: {midi_file}")
            fs.play_midi_file(midi_file)
            
            print("MIDI file is playing. Press Enter to stop.")
            input("🎵 Press Enter to stop playback...")
            fs.delete()
            return True
            
        except ImportError:
            print("⚠️ FluidSynth Python module not installed")
            print("Install with: pip install pyfluidsynth")
        except Exception as e:
            print(f"❌ FluidSynth playback failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Try PyGame as fallback
    if try_pygame:
        try:
            import pygame
            print("\nTrying PyGame for playback...")
            
            pygame.mixer.init()
            pygame.init()
            
            # Load and play the MIDI file
            pygame.mixer.music.load(midi_file)
            pygame.mixer.music.play()
            
            print("MIDI file is playing with PyGame. Press Enter to stop.")
            input("🎵 Press Enter to stop playback...")
            
            pygame.mixer.music.stop()
            pygame.quit()
            return True
            
        except ImportError:
            print("⚠️ PyGame not installed")
            print("Install with: pip install pygame")
        except Exception as e:
            print(f"❌ PyGame playback failed: {e}")
            import traceback
            traceback.print_exc()
    
    # If all methods failed
    print("\n❌ All playback methods failed")
    print("Please try opening the MIDI file in an external player")
    print("Recommended external players:")
    print("  - VLC Media Player")
    print("  - Windows Media Player")
    print("  - GarageBand (Mac)")
    print("  - MuseScore (for visualization with lyrics)")
    return False

if __name__ == "__main__":
    print("🚀 Running Lyrics-Melody Alignment Script...")
   
    # Step 1: Load the melody and lyrics.
    melody = load_midi_file(MIDI_FILE)
    lyrics = load_generated_lyrics(LYRICS_FILE)
   
    # Step 2: Align lyrics with melody and assign vocal instrument.
    aligned_score = align_lyrics_with_melody(melody, lyrics)
   
    # Step 3: Save the final score in multiple formats.
    save_midi_with_lyrics(aligned_score, OUTPUT_FILE, XML_OUTPUT_FILE, KARAOKE_OUTPUT_FILE)
   
    # ✅ Step 4: Verify the structure of the MIDI file
    verify_midi_parts(OUTPUT_FILE)
   
    print("\n🎵 ✅ Lyrics successfully aligned with melody!")
    print("\n📝 PLAYBACK OPTIONS:")
    print("1. Open the MusicXML file in MuseScore to see lyrics clearly.")
    print("2. Use the .KAR file with a karaoke player for synchronized lyric playback.")
    print("3. Load the final MIDI file in a DAW for full instrumental + vocal playback.")
    print("4. Play the song directly in Python!")
   
    # ✅ Step 5: Play the final song in Python with proper vocal support
    play_final_song(OUTPUT_FILE)
