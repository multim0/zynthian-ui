# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_companion)
#
# zynthian_engine implementation for Companion Style Player LV2 plugin
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
from zyngine.zynthian_controller import zynthian_controller
from zynlibs.zyncompanion import zyncompanion

COMPANION_LV2_URI = "http://zynthian-companion.local/accompaniment-engine#lv2"

# Number of style channels supported by the companion plugin
# Most styles use only 8 channels + 10th channel for drums, but some may use more. Set to 16 for safety.
COMPANION_NUM_CHANNELS = 16

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
        self.custom_gui_fpath = os.environ.get(
            'ZYNTHIAN_UI_DIR',
            "/zynthian/zynthian-ui"
        ) + "/zyngui/zynthian_widget_companion.py"

        self.options['replace'] = False

        # Current style state
        self.style_file = None
        self.sections = []
        self.current_section = None
        self.playing = False

        # GM instruments per channel (populated after loading a style)
        # comment
        self.channel_instruments = {}

        # Monitors dict for widget updates
        self.monitors_dict = {}
        self._update_monitors()

        # Create the accompaniment engine instance
        self.companion_handle = zyncompanion.create_engine()
        if not self.companion_handle:
            logging.error("Companion: Failed to create accompaniment engine")

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def get_path(self, processor=None):
        return self.name

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        return self.get_bank_dirlist(
            self.preset_fexts,
            self.root_bank_dirs
        )

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

        # Load the style file via the accompaniment engine
        result = zyncompanion.load_file(self.companion_handle, fpath)
        if result != zyncompanion.RESULT_OK:
            logging.error(f"Companion: Failed to load style file: {zyncompanion.result_string(result)}")
            self.style_file = None
            return False

        # Parse sections from the style file
        self._parse_sections(fpath)

        # Read GM instrument assignments per channel
        self._read_channel_instruments()

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
            zyncompanion.set_tempo(self.companion_handle, float(zctrl.value))
            self._update_monitors()

    # ---------------------------------------------------------------------------
    # Transport Controls
    # ---------------------------------------------------------------------------

    def start_playing(self):
        """Start playing the current style section."""
        if not self.style_file:
            logging.warning("Companion: No style file loaded")
            return
        result = zyncompanion.play(self.companion_handle)
        if result == zyncompanion.RESULT_OK:
            self.playing = True
            logging.info("Companion: Start playing")
        else:
            logging.warning(f"Companion: Play failed: {zyncompanion.result_string(result)}")
        self._update_monitors()

    def stop_playing(self):
        """Stop playing the current style."""
        zyncompanion.stop(self.companion_handle)
        self.playing = False
        logging.info("Companion: Stop playing")
        self._update_monitors()

    def select_section(self, section_idx):
        """Select a section of the current style to play."""
        if 0 <= section_idx < len(self.sections):
            self.current_section = self.sections[section_idx]
            logging.info(f"Companion: Selected section '{self.current_section}'")
            zyncompanion.queue_section(self.companion_handle, section_idx)
            self._update_monitors()

    # ---------------------------------------------------------------------------
    # Style Parsing
    # ---------------------------------------------------------------------------

    def _parse_sections(self, fpath):
        """Parse available sections from the loaded style file.

        Queries the engine for which standard arranger roles are present
        and builds the sections list from those found.
        """
        self.sections = []
        roles = [
            (zyncompanion.SECTION_INTRO, "Intro"),
            (zyncompanion.SECTION_MAIN_A, "Main A"),
            (zyncompanion.SECTION_MAIN_B, "Main B"),
            (zyncompanion.SECTION_FILL, "Fill"),
            (zyncompanion.SECTION_ENDING, "Ending"),
        ]
        for role, label in roles:
            idx = zyncompanion.find_section_by_role(
                self.companion_handle, role)
            if idx >= 0:
                self.sections.append(label)
        if not self.sections:
            # Fallback: file may have patterns but no arranger roles
            self.sections = ["Pattern"]
        self.current_section = self.sections[0]

    def _read_channel_instruments(self):
        """Read GM instrument assignments per style channel.

        Note: The current accompaniment engine library does not expose
        per-channel program queries. This is a placeholder for when
        that API becomes available.
        """
        self.channel_instruments = {}

    # ---------------------------------------------------------------------------
    # Controller Building
    # ---------------------------------------------------------------------------

    def _build_controllers(self):
        """Build controllers based on current style state."""
        section_labels = self.sections if self.sections else ["---"]

        current_tempo = zyncompanion.get_tempo(self.companion_handle)

        self._ctrls = [
            ['transport', None, 0, ['stopped', 'playing']],
            ['section', None, 0, [str(i) + ": " + s for i, s in enumerate(section_labels)]],
            ['tempo', None, int(current_tempo), [40, 240, int(current_tempo)]],
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
        }

    def get_monitors_dict(self):
        # Sync playback state from the engine
        self.playing = zyncompanion.is_playing(self.companion_handle)
        self.monitors_dict['playing'] = self.playing
        self.monitors_dict['position'] = zyncompanion.get_position(
            self.companion_handle)
        self.monitors_dict['tempo'] = zyncompanion.get_tempo(
            self.companion_handle)
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
