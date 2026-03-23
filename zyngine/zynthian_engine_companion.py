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

# ACTION REQUIRED: Import the companion LV2 library bindings once available
# from zynlibs.zyncompanion import zyncompanion

# ACTION REQUIRED: Confirm the exact LV2 plugin URI from multim0/zynthian-companion
COMPANION_LV2_URI = "http://zynthian.org/plugins/companion-style-player"

# Number of style channels supported by the companion plugin
# ACTION REQUIRED: Confirm actual number of channels from the LV2 plugin spec
COMPANION_NUM_CHANNELS = 16

# ------------------------------------------------------------------------------
# Companion Style Player Engine Class
# ------------------------------------------------------------------------------


class zynthian_engine_companion(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Config variables
    # ---------------------------------------------------------------------------

    # File extensions for style preset files
    # ACTION REQUIRED: Confirm the actual file extension(s) used by companion style files
    preset_fexts = ["sty", "mid"]

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
        self.type = "MIDI Synth"
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
        self.channel_instruments = {}

        # Monitors dict for widget updates
        self.monitors_dict = {}
        self._update_monitors()

        # ACTION REQUIRED: Initialize the companion LV2 plugin instance
        # This depends on how the LV2 plugin is hosted (jalv or native binding)
        # Example: self.companion = zyncompanion.create_instance()

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

        # ACTION REQUIRED: Call the LV2 plugin to load the style file
        # Example: zyncompanion.load_style(self.companion_handle, fpath)

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
        # ACTION REQUIRED: Handle additional controller parameters
        # based on the LV2 plugin's port definitions

    # ---------------------------------------------------------------------------
    # Transport Controls
    # ---------------------------------------------------------------------------

    def start_playing(self):
        """Start playing the current style section."""
        if not self.style_file:
            logging.warning("Companion: No style file loaded")
            return
        self.playing = True
        logging.info("Companion: Start playing")
        # ACTION REQUIRED: Send play command to the LV2 plugin
        # Example: zyncompanion.play(self.companion_handle)
        self._update_monitors()

    def stop_playing(self):
        """Stop playing the current style."""
        self.playing = False
        logging.info("Companion: Stop playing")
        # ACTION REQUIRED: Send stop command to the LV2 plugin
        # Example: zyncompanion.stop(self.companion_handle)
        self._update_monitors()

    def select_section(self, section_idx):
        """Select a section of the current style to play."""
        if 0 <= section_idx < len(self.sections):
            self.current_section = self.sections[section_idx]
            logging.info(f"Companion: Selected section '{self.current_section}'")
            # ACTION REQUIRED: Send section change to the LV2 plugin
            # Example: zyncompanion.set_section(self.companion_handle, section_idx)
            self._update_monitors()

    # ---------------------------------------------------------------------------
    # Style Parsing
    # ---------------------------------------------------------------------------

    def _parse_sections(self, fpath):
        """Parse available sections from the style file.

        ACTION REQUIRED: Implement actual parsing logic based on the
        companion style file format. The current implementation provides
        placeholder section names.
        """
        # ACTION REQUIRED: Replace with real parsing from the LV2 plugin
        # Example: self.sections = zyncompanion.get_sections(self.companion_handle)
        self.sections = ["Intro", "Main A", "Main B", "Fill A", "Fill B", "Ending"]
        self.current_section = self.sections[0] if self.sections else None

    def _read_channel_instruments(self):
        """Read GM instrument assignments per style channel.

        ACTION REQUIRED: Implement reading of GM instrument names from
        the LV2 plugin after loading a style file.
        """
        self.channel_instruments = {}
        # ACTION REQUIRED: Query the LV2 plugin for instrument assignments
        # Example:
        # for ch in range(COMPANION_NUM_CHANNELS):
        #     prog = zyncompanion.get_channel_program(self.companion_handle, ch)
        #     if prog >= 0:
        #         self.channel_instruments[ch] = self.gm_program_name(prog)

    # ---------------------------------------------------------------------------
    # Controller Building
    # ---------------------------------------------------------------------------

    def _build_controllers(self):
        """Build controllers based on current style state."""
        section_labels = self.sections if self.sections else ["---"]

        self._ctrls = [
            ['transport', None, 0, ['stopped', 'playing']],
            ['section', None, 0, [str(i) + ": " + s for i, s in enumerate(section_labels)]],
        ]

        self._ctrl_screens = [
            ['Style', ['transport', 'section']]
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
        # ACTION REQUIRED: If the LV2 plugin provides real-time monitor
        # ports, read them here to update playing state, position, etc.
        # Example:
        # self.monitors_dict['playing'] = zyncompanion.is_playing(self.companion_handle)
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
