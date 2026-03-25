#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ********************************************************************
# ZYNTHIAN PROJECT: Zyncompanion Python Wrapper
#
# A Python wrapper for the Zynthian Accompaniment Engine library
#
# Copyright (C) 2024-2026 Zynthian Community
#
# ********************************************************************
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
# ********************************************************************

import ctypes
import json
import logging
from os.path import dirname, realpath

# ---------------------------------------------------------------------------
# Constants — Engine states
# ---------------------------------------------------------------------------

STATE_STOPPED = 0
STATE_PLAYING = 1
STATE_PAUSED = 2

# ---------------------------------------------------------------------------
# Constants — Result codes from accompaniment_file_load / operations
# ---------------------------------------------------------------------------

RESULT_OK = 0
RESULT_INVALID_FILE = 1
RESULT_UNSUPPORTED_FORMAT = 2
RESULT_MEMORY_FAILURE = 3
RESULT_IO_ERROR = 4
RESULT_INVALID_STATE = 5
RESULT_NOT_INITIALISED = 6

# ---------------------------------------------------------------------------
# Constants — Section roles
# ---------------------------------------------------------------------------

SECTION_NONE = 0
SECTION_INTRO = 1
SECTION_MAIN_A = 2
SECTION_MAIN_B = 3
SECTION_FILL = 4
SECTION_ENDING = 5

SECTION_ROLE_NAMES = {
    SECTION_NONE: "None",
    SECTION_INTRO: "Intro",
    SECTION_MAIN_A: "Main A",
    SECTION_MAIN_B: "Main B",
    SECTION_FILL: "Fill",
    SECTION_ENDING: "Ending",
}

# ---------------------------------------------------------------------------
# Library handle
# ---------------------------------------------------------------------------

_lib = None

# Path to the accompaniment shared library
_LIB_PATH = "/zynthian/zynthian-plugins/lv2/zynthian-companion.lv2/accompaniment_lv2.so"


def init():
    """Load the accompaniment shared library and declare function signatures."""
    global _lib
    try:
        _lib = ctypes.cdll.LoadLibrary(_LIB_PATH)
    except Exception as e:
        _lib = None
        logging.error(f"Can't initialise zyncompanion library: {e}")
        return

    # --- Engine lifecycle ---
    _lib.accompaniment_engine_create.restype = ctypes.c_void_p

    _lib.accompaniment_engine_destroy.argtypes = [ctypes.c_void_p]
    _lib.accompaniment_engine_destroy.restype = None

    # --- File management ---
    _lib.accompaniment_file_load.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p]
    _lib.accompaniment_file_load.restype = ctypes.c_int

    _lib.accompaniment_file_unload.argtypes = [ctypes.c_void_p]
    _lib.accompaniment_file_unload.restype = None

    # --- Transport ---
    _lib.accompaniment_play.argtypes = [ctypes.c_void_p]
    _lib.accompaniment_play.restype = ctypes.c_int

    _lib.accompaniment_pause.argtypes = [ctypes.c_void_p]
    _lib.accompaniment_pause.restype = ctypes.c_int

    _lib.accompaniment_stop.argtypes = [ctypes.c_void_p]
    _lib.accompaniment_stop.restype = ctypes.c_int

    # --- Tempo ---
    _lib.accompaniment_set_tempo.argtypes = [
        ctypes.c_void_p, ctypes.c_float]
    _lib.accompaniment_set_tempo.restype = ctypes.c_int

    _lib.accompaniment_get_tempo.argtypes = [ctypes.c_void_p]
    _lib.accompaniment_get_tempo.restype = ctypes.c_float

    # --- Seek / Position ---
    _lib.accompaniment_seek.argtypes = [
        ctypes.c_void_p, ctypes.c_float]
    _lib.accompaniment_seek.restype = ctypes.c_int

    _lib.accompaniment_get_position.argtypes = [ctypes.c_void_p]
    _lib.accompaniment_get_position.restype = ctypes.c_float

    # --- State ---
    _lib.accompaniment_get_state.argtypes = [ctypes.c_void_p]
    _lib.accompaniment_get_state.restype = ctypes.c_int

    # --- String helpers ---
    _lib.accompaniment_result_string.argtypes = [ctypes.c_int]
    _lib.accompaniment_result_string.restype = ctypes.c_char_p

    _lib.accompaniment_section_role_string.argtypes = [ctypes.c_int]
    _lib.accompaniment_section_role_string.restype = ctypes.c_char_p

    # --- Arranger ---
    _lib.accompaniment_validate_arranger_sections.argtypes = [
        ctypes.c_void_p]
    _lib.accompaniment_validate_arranger_sections.restype = ctypes.c_int

    _lib.arranger_queue_section.argtypes = [
        ctypes.c_void_p, ctypes.c_uint]
    _lib.arranger_queue_section.restype = ctypes.c_int

    _lib.arranger_request_ending.argtypes = [ctypes.c_void_p]
    _lib.arranger_request_ending.restype = ctypes.c_int

    _lib.arranger_find_section_by_role.argtypes = [
        ctypes.c_void_p, ctypes.c_int]
    _lib.arranger_find_section_by_role.restype = ctypes.c_int

    # --- Parser (file format detection) ---
    _lib.parser_detect_format.argtypes = [ctypes.c_char_p]
    _lib.parser_detect_format.restype = ctypes.c_int

    logging.info("zyncompanion library initialised")


def destroy():
    """Unload the shared library."""
    global _lib
    if _lib:
        from _ctypes import dlclose
        dlclose(_lib._handle)
    _lib = None


# ---------------------------------------------------------------------------
# Engine lifecycle
# ---------------------------------------------------------------------------

def create_engine():
    """Create an accompaniment engine instance.

    Returns the opaque handle (c_void_p) or None on failure.
    """
    if not _lib:
        return None
    handle = _lib.accompaniment_engine_create()
    if not handle:
        logging.error("zyncompanion: failed to create engine")
        return None
    return handle


def destroy_engine(handle):
    """Destroy an accompaniment engine instance."""
    if _lib and handle:
        _lib.accompaniment_engine_destroy(handle)


# ---------------------------------------------------------------------------
# File management
# ---------------------------------------------------------------------------

def load_file(handle, filepath):
    """Load a style file (.sty or .sff).

    Returns RESULT_OK (0) on success, or an error code.
    """
    if not _lib or not handle:
        return RESULT_NOT_INITIALISED
    result = _lib.accompaniment_file_load(
        handle, filepath.encode("utf-8"))
    if result != RESULT_OK:
        msg = result_string(result)
        logging.warning(f"zyncompanion: load_file failed: {msg}")
    return result


def unload_file(handle):
    """Unload the currently loaded style file."""
    if _lib and handle:
        _lib.accompaniment_file_unload(handle)


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def play(handle):
    """Start playback. Returns result code."""
    if not _lib or not handle:
        return RESULT_NOT_INITIALISED
    return _lib.accompaniment_play(handle)


def pause(handle):
    """Pause playback. Returns result code."""
    if not _lib or not handle:
        return RESULT_NOT_INITIALISED
    return _lib.accompaniment_pause(handle)


def stop(handle):
    """Stop playback. Returns result code."""
    if not _lib or not handle:
        return RESULT_NOT_INITIALISED
    return _lib.accompaniment_stop(handle)


# ---------------------------------------------------------------------------
# Tempo
# ---------------------------------------------------------------------------

def set_tempo(handle, bpm):
    """Set the tempo in BPM (40.0–240.0). Returns result code."""
    if not _lib or not handle:
        return RESULT_NOT_INITIALISED
    return _lib.accompaniment_set_tempo(handle, ctypes.c_float(bpm))


def get_tempo(handle):
    """Get the current tempo in BPM."""
    if not _lib or not handle:
        return 120.0
    return _lib.accompaniment_get_tempo(handle)


# ---------------------------------------------------------------------------
# Seek / Position
# ---------------------------------------------------------------------------

def seek(handle, beat):
    """Seek to a beat position. Returns result code."""
    if not _lib or not handle:
        return RESULT_NOT_INITIALISED
    return _lib.accompaniment_seek(handle, ctypes.c_float(beat))


def get_position(handle):
    """Get the current playback position in beats."""
    if not _lib or not handle:
        return 0.0
    return _lib.accompaniment_get_position(handle)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def get_state(handle):
    """Get the engine state (STATE_STOPPED, STATE_PLAYING, STATE_PAUSED)."""
    if not _lib or not handle:
        return STATE_STOPPED
    return _lib.accompaniment_get_state(handle)


def is_playing(handle):
    """Return True if the engine is currently playing."""
    return get_state(handle) == STATE_PLAYING


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def result_string(code):
    """Return a human-readable string for a result code."""
    if not _lib:
        return "library not loaded"
    val = _lib.accompaniment_result_string(code)
    return val.decode("utf-8") if val else "unknown"


def section_role_string(role):
    """Return a human-readable string for a section role."""
    if not _lib:
        return SECTION_ROLE_NAMES.get(role, "Unknown")
    val = _lib.accompaniment_section_role_string(role)
    return val.decode("utf-8") if val else "Unknown"


# ---------------------------------------------------------------------------
# Arranger
# ---------------------------------------------------------------------------

def validate_arranger_sections(handle):
    """Validate that the loaded file has the required arranger sections.

    Returns RESULT_OK if valid, or an error code.
    """
    if not _lib or not handle:
        return RESULT_NOT_INITIALISED
    return _lib.accompaniment_validate_arranger_sections(handle)


def queue_section(handle, section_index):
    """Queue a section by index for the arranger to transition to."""
    if not _lib or not handle:
        return RESULT_NOT_INITIALISED
    return _lib.arranger_queue_section(handle, section_index)


def request_ending(handle):
    """Request the arranger to transition to the ending section."""
    if not _lib or not handle:
        return RESULT_NOT_INITIALISED
    return _lib.arranger_request_ending(handle)


def find_section_by_role(handle, role):
    """Find a section index by its role (SECTION_INTRO, SECTION_MAIN_A, etc.).

    Returns the section index or -1 if not found.
    """
    if not _lib or not handle:
        return -1
    return _lib.arranger_find_section_by_role(handle, role)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def detect_format(filepath):
    """Detect the file format of a style file.

    Returns a format code (implementation-specific).
    """
    if not _lib:
        return -1
    return _lib.parser_detect_format(filepath.encode("utf-8"))
