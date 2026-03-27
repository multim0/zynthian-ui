# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_companion)
#
# zynthian_engine implementation for Companion Style Player
#
# Copyright (C) 2024-2026 Zynthian Community
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import os
import logging

from zyngine.zynthian_engine import zynthian_engine
from zynlibs.zyncompanion import zyncompanion

# LV2 plugin URI
COMPANION_LV2_URI = "http://zynthian-companion.local/accompaniment-engine#lv2"

# LV2 control port values
PLAY_STOP = 0
PLAY_PAUSE = 1
PLAY_PLAY = 2

SECTION_INTRO = 0
SECTION_MAIN_A = 1
SECTION_MAIN_B = 2
SECTION_FILL = 3
SECTION_ENDING = 4

# Map section names to LV2 section_select port values
SECTION_VALUES = {
    "Intro": SECTION_INTRO,
    "Main A": SECTION_MAIN_A,
    "Main B": SECTION_MAIN_B,
    "Fill": SECTION_FILL,
    "Ending": SECTION_ENDING,
}

# Path file for file-load trigger (plugin reads this on trigger change)
LOAD_FILE_PATH = "/tmp/.companion_style_path"

# ------------------------------------------------------------------------------
# Companion Style Player Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_companion(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Config variables
    # ---------------------------------------------------------------------------

    # File extensions for style preset files
    preset_fexts = ["sty", "sff"]

    # Root directories for style file catalogs
    root_bank_dirs = [
        ('User Styles', zynthian_engine.my_data_dir + "/styles"),
        ('System Styles', zynthian_engine.data_dir + "/styles")
    ]

    # Standard MIDI Controllers
    _ctrls = []

    # Controller Screens
    _ctrl_screens = []

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None, jackname=None):
        super().__init__(state_manager)
        self.name = "CompanionStylePlayer"
        self.nickname = "CP"
        self.type = "MIDI Tool"
        self.jackname = "zynthian-accompaniment"
        self.custom_gui_fpath = os.environ.get(
            'ZYNTHIAN_UI_DIR',
            "/zynthian/zynthian-ui"
        ) + "/zyngui/zynthian_widget_companion.py"

        self.options['replace'] = False

        # jalv subprocess setup
        self.command = "jalv -n {} {}".format(self.jackname, COMPANION_LV2_URI)
        self.command_prompt = ">"

        # Current style state
        self.style_file = None
        self.sections = []
        self.current_section = None
        self.playing = False
        self.current_tempo = 120.0

        # GM instruments per channel (populated after loading a style)
        self.channel_instruments = {}

        # File-load trigger counter (bumped to signal plugin)
        self.load_file_trigger = 0

        # Monitors dict for widget updates
        self.monitors_dict = {}
        self._update_monitors()

        # Start jalv hosting the LV2 plugin
        self.start()

    def proc_cmd(self, cmd):
        """Send command to jalv without waiting for prompt response.

        The base class uses pexpect.expect(">") which falsely matches
        on jalv monitor lines like '#MON> symbol=value', causing prompt
        desynchronization and timeouts. Since companion set commands are
        fire-and-forget, we just write and move on.
        """
        if self.proc:
            if not self.proc.isalive():
                logging.error("Companion: jalv process has died, attempting restart")
                self.proc = None
                self.start()
                if not self.proc:
                    return
            try:
                self.proc.sendline(cmd)
            except Exception as err:
                logging.error(f"Can't exec engine command: {cmd} => {err}")

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def get_path(self, processor=None):
        return self.name

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        banks = []
        for source_name, root_dir in self.root_bank_dirs:
            if not os.path.isdir(root_dir):
                continue
            source_banks = []
            # Check if root dir itself has style files
            has_root_files = self.find_some_preset_file(root_dir, self.preset_fexts, recursion=0)
            if has_root_files:
                source_banks.append([root_dir, None, source_name, None, os.path.basename(root_dir)])
            # Also add subdirectories that contain style files
            try:
                for d in sorted(os.listdir(root_dir)):
                    dpath = os.path.join(root_dir, d)
                    if os.path.isdir(dpath) and self.find_some_preset_file(dpath, self.preset_fexts, recursion=1):
                        source_banks.append([dpath, None, d, None, d])
            except OSError:
                pass
            banks.extend(source_banks)
        return banks

    def set_bank(self, processor, bank):
        return True

    # ---------------------------------------------------------------------------
    # Preset Management (Style Files)
    # ---------------------------------------------------------------------------

    def get_preset_list(self, bank, processor=None):
        if bank[0] is None or bank[0] == "":
            return []
        return self.get_filelist(
            bank[0],
            self.preset_fexts,
            include_dirs=True,
            exclude_empty_dirs=True
        )

    def set_preset(self, processor, preset, preload=False):
        if preset[0] is None or not os.path.isfile(str(preset[0])):
            if os.path.isdir(str(preset[0])):
                return None
            return False

        fpath = preset[0]
        if self.style_file == fpath:
            return False

        self.style_file = fpath
        logging.info(f"Companion: Loading style file '{fpath}'")

        # Stop playback before changing files
        if self.playing:
            self.stop_playing()

        # Parse sections using zyncompanion library (ctypes, for metadata only)
        self._parse_sections(fpath)

        # Load style file into the LV2 plugin via file-trigger mechanism:
        # Write path to tmpfs file, then bump load_file_trigger control port
        try:
            with open(LOAD_FILE_PATH, 'w') as f:
                f.write(fpath)
        except OSError as err:
            logging.error(f"Companion: Can't write style path file: {err}")
            return False
        self.load_file_trigger = (self.load_file_trigger + 1) % 9999
        self.proc_cmd("set load_file_trigger {}".format(self.load_file_trigger))

        # Build dynamic controllers after loading
        self._build_controllers()
        if processor:
            processor.refresh_controllers()

        self._update_monitors()
        return True

    def cmp_presets(self, preset1, preset2):
        try:
            return preset1[0] == preset2[0]
        except Exception:
            return False

    # ---------------------------------------------------------------------------
    # Controllers Management
    # ---------------------------------------------------------------------------

    def get_controllers_dict(self, processor=None, ctrl_list=None):
        if not self._ctrls:
            self._build_controllers()

        return super().get_controllers_dict(processor)

    def send_controller_value(self, zctrl):
        if zctrl.symbol == "transport":
            if zctrl.value == 1:
                self.start_playing()
            else:
                self.stop_playing()
        elif zctrl.symbol == "section":
            section_idx = int(zctrl.value)
            self.select_section(section_idx)
        elif zctrl.symbol == "tempo":
            self._set_tempo(float(zctrl.value))
            self._update_monitors()

    # ---------------------------------------------------------------------------
    # Transport Controls (via jalv LV2 control ports)
    # ---------------------------------------------------------------------------

    def start_playing(self):
        if not self.proc or not self.style_file:
            logging.warning("Companion: No style file loaded or process not running")
            return
        self.proc_cmd("set play {}".format(PLAY_PLAY))
        self.playing = True
        logging.info("Companion: Start playing")
        self._update_monitors()

    def stop_playing(self):
        if not self.proc:
            return
        self.proc_cmd("set play {}".format(PLAY_STOP))
        self.playing = False
        logging.info("Companion: Stop playing")
        self._update_monitors()

    def select_section(self, section_idx):
        if not self.proc:
            return
        if 0 <= section_idx < len(self.sections):
            section_name = self.sections[section_idx]
            value = SECTION_VALUES.get(section_name)
            if value is not None:
                self.proc_cmd("set section_select {}".format(value))
                self.current_section = section_name
                logging.info(f"Companion: Selected section '{section_name}'")
            else:
                logging.warning(f"Companion: Unknown section '{section_name}'")
            self._update_monitors()

    def _set_tempo(self, bpm):
        if not self.proc:
            return
        bpm = max(40.0, min(240.0, float(bpm)))
        self.proc_cmd("set tempo {:.1f}".format(bpm))
        self.current_tempo = bpm

    # ---------------------------------------------------------------------------
    # Style Parsing
    # ---------------------------------------------------------------------------

    def _parse_sections(self, fpath):
        """Parse available sections from the loaded style file.

        Uses the zyncompanion ctypes library to detect which arranger
        sections are present, without needing JACK output.
        """
        self.sections = []
        # Use zyncompanion for metadata parsing
        temp_handle = zyncompanion.create_engine()
        if not temp_handle:
            self.sections = ["Pattern"]
            self.current_section = self.sections[0]
            return

        result, file_handle = zyncompanion.load_file(temp_handle, fpath)
        if result != zyncompanion.RESULT_OK:
            zyncompanion.destroy_engine(temp_handle)
            self.sections = ["Pattern"]
            self.current_section = self.sections[0]
            return

        roles = [
            (zyncompanion.SECTION_INTRO, "Intro"),
            (zyncompanion.SECTION_MAIN_A, "Main A"),
            (zyncompanion.SECTION_MAIN_B, "Main B"),
            (zyncompanion.SECTION_FILL, "Fill"),
            (zyncompanion.SECTION_ENDING, "Ending"),
        ]
        for role, label in roles:
            idx = zyncompanion.find_section_by_role(file_handle, role)
            if idx >= 0:
                self.sections.append(label)

        # Get tempo from the file
        self.current_tempo = zyncompanion.get_tempo(temp_handle)
        if self.current_tempo <= 0:
            self.current_tempo = 120.0

        zyncompanion.unload_file(file_handle)
        zyncompanion.destroy_engine(temp_handle)

        if not self.sections:
            self.sections = ["Pattern"]
        self.current_section = self.sections[0]

    # ---------------------------------------------------------------------------
    # Controller Building
    # ---------------------------------------------------------------------------

    def _build_controllers(self):
        """Build controllers based on current style state."""
        section_labels = self.sections if self.sections else ["---"]

        self._ctrls = [
            ['transport', None, 0, ['stopped', 'playing']],
            ['section', None, 0, [str(i) + ": " + s for i, s in enumerate(section_labels)]],
            ['tempo', {'value': int(self.current_tempo), 'value_min': 40, 'value_max': 240, 'is_integer': True}],
        ]

        self._ctrl_screens = [
            ['Style', ['transport', 'section', 'tempo']]
        ]

    # ---------------------------------------------------------------------------
    # Monitors
    # ---------------------------------------------------------------------------

    def _update_monitors(self):
        """Update the monitors dict for the custom GUI widget."""
        self.monitors_dict = {
            'style_file': os.path.basename(self.style_file) if self.style_file else "",
            'sections': list(self.sections),
            'current_section': self.current_section or "",
            'playing': self.playing,
            'channel_instruments': dict(self.channel_instruments),
            'tempo': self.current_tempo,
            'position': 0,
        }

    def get_monitors_dict(self):
        self.monitors_dict['playing'] = self.playing
        self.monitors_dict['tempo'] = self.current_tempo
        return self.monitors_dict

    # ---------------------------------------------------------------------------
    # GM Program Names
    # ---------------------------------------------------------------------------

    # General MIDI Level 1 instrument names (programs 0-127)
    GM_INSTRUMENTS = [
        "Acoustic Grand Piano", "Bright Acoustic Piano",
        "Electric Grand Piano", "Honky-tonk Piano",
        "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavi",
        "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
        "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
        "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
        "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
        "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)",
        "Electric Guitar (jazz)", "Electric Guitar (clean)",
        "Electric Guitar (muted)", "Overdriven Guitar",
        "Distortion Guitar", "Guitar harmonics",
        "Acoustic Bass", "Electric Bass (finger)",
        "Electric Bass (pick)", "Fretless Bass",
        "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
        "Violin", "Viola", "Cello", "Contrabass",
        "Tremolo Strings", "Pizzicato Strings",
        "Orchestral Harp", "Timpani",
        "String Ensemble 1", "String Ensemble 2",
        "SynthStrings 1", "SynthStrings 2",
        "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
        "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
        "French Horn", "Brass Section", "SynthBrass 1", "SynthBrass 2",
        "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
        "Oboe", "English Horn", "Bassoon", "Clarinet",
        "Piccolo", "Flute", "Recorder", "Pan Flute",
        "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
        "Lead 1 (square)", "Lead 2 (sawtooth)",
        "Lead 3 (calliope)", "Lead 4 (chiff)",
        "Lead 5 (charang)", "Lead 6 (voice)",
        "Lead 7 (fifths)", "Lead 8 (bass + lead)",
        "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)",
        "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)",
        "Pad 7 (halo)", "Pad 8 (sweep)",
        "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)",
        "FX 4 (atmosphere)", "FX 5 (brightness)", "FX 6 (goblins)",
        "FX 7 (echoes)", "FX 8 (sci-fi)",
        "Sitar", "Banjo", "Shamisen", "Koto",
        "Kalimba", "Bag pipe", "Fiddle", "Shanai",
        "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
        "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
        "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
        "Telephone Ring", "Helicopter", "Applause", "Gunshot",
    ]

    @classmethod
    def gm_program_name(cls, program):
        """Return GM instrument name for a given program number (0-127)."""
        if 0 <= program < len(cls.GM_INSTRUMENTS):
            return cls.GM_INSTRUMENTS[program]
        return f"Program {program}"

# ******************************************************************************
