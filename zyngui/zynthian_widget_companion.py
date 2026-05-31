#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "Companion Style Player"
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

import tkinter
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base
from zyngine.zynthian_engine_companion import CHORD_GATE_SYNC_START

# ------------------------------------------------------------------------------
# Zynthian Widget Class for "Companion Style Player"
# ------------------------------------------------------------------------------

_NUM_PAD_COLS = 4
_NUM_PAD_ROWS = 2
_NUM_PADS = _NUM_PAD_COLS * _NUM_PAD_ROWS  # 8 fixed slots in a 2×4 grid


class zynthian_widget_companion(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)
        self.refreshing = False
        self.style_name = ""
        self.sections = []
        self.current_section = ""
        self.playing = False
        self.tempo = 120.0
        self.channel_instruments = {}
        self.detected_chord = ""
        self.chord_gate_mode = 0

        # Per-slot data cached by _layout_section_pads() and used by _update_items()
        self._pad_sec_idx = [None] * _NUM_PADS   # logical section index (int) or None
        self._pad_sec_label = [""] * _NUM_PADS   # section name string or ""

        # Main canvas – background matches the global UI background
        self.widget_canvas = tkinter.Canvas(self,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        # Create all permanent canvas items once; geometry applied later in _layout()
        self._create_items()

    # ------------------------------------------------------------------
    # Item creation (called once)
    # ------------------------------------------------------------------

    def _create_items(self):
        cfg = zynthian_gui_config

        # Style / preset title
        self.style_text = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.NW,
            font=(cfg.font_family, 12, "bold"),
            fill=cfg.color_panel_tx,
            text="No style loaded"
        )

        # Status bar background
        self._status_rect = self.widget_canvas.create_rectangle(
            0, 0, 1, 1,
            fill=cfg.color_panel_bg,
            outline=cfg.color_off,
            width=1
        )

        # Playback state indicator (left half of status bar)
        self._status_text = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.CENTER,
            font=(cfg.font_family, 12, "bold"),
            fill=cfg.color_hl,
            text="■ STOPPED"
        )

        # Detected chord (right half of status bar; hidden when no chord)
        self._chord_text = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.CENTER,
            font=(cfg.font_family, 16, "bold"),
            fill=cfg.color_ml,
            text="",
            state=tkinter.HIDDEN
        )

        # Section pad slots: 2 rows × 4 cols, fixed positions
        self._pad_rects = []
        self._pad_texts = []
        for i in range(_NUM_PADS):
            rect = self.widget_canvas.create_rectangle(
                0, 0, 1, 1,
                fill=cfg.color_off,
                outline=cfg.color_off,
                width=2
            )
            text = self.widget_canvas.create_text(
                0, 0,
                anchor=tkinter.CENTER,
                font=(cfg.font_family, 10, "bold"),
                fill=cfg.color_tx,
                text="",
                state=tkinter.HIDDEN
            )
            # Bind once; closure captures slot index i
            self.widget_canvas.tag_bind(rect, "<ButtonPress-1>",
                lambda event, slot=i: self._on_pad_click(slot))
            self.widget_canvas.tag_bind(text, "<ButtonPress-1>",
                lambda event, slot=i: self._on_pad_click(slot))
            self._pad_rects.append(rect)
            self._pad_texts.append(text)

    # ------------------------------------------------------------------
    # Geometry (called on resize or when sections list changes)
    # ------------------------------------------------------------------

    def on_size(self, event):
        if super().on_size(event):
            self._layout()

    def _layout(self):
        """Reposition all canvas items to fit current widget dimensions."""
        w = self.width
        h = self.height
        pad = max(8, min(w, h) // 45)
        fs_title = max(10, w // 30)

        # Style title
        self.widget_canvas.coords(self.style_text, pad, pad)
        self.widget_canvas.itemconfigure(self.style_text,
            font=(zynthian_gui_config.font_family, fs_title),
            width=w - 2 * pad)
        bbox = self.widget_canvas.bbox(self.style_text)
        title_bottom = (bbox[3] + pad) if bbox else (pad + fs_title + pad)

        # Performance area below the title
        self._layout_performance(title_bottom, h - pad, pad, w)

        # Apply current data state to all items
        self._update_items()

    def _layout_performance(self, top, bottom, left, width):
        content_h = max(1, bottom - top)
        gap = max(6, min(width, content_h) // 60)
        fs_status = max(8, width // 50)
        row_h = max(36, (content_h - 2 * gap) // 3)
        inner_gap = max(4, gap // 2)
        available_w = width - 2 * left
        col_w = (available_w - 3 * inner_gap) // 4

        # Status bar spans the full grid width
        sx1 = left
        sx2 = left + 4 * col_w + 3 * inner_gap
        self.widget_canvas.coords(self._status_rect, sx1, top, sx2, top + row_h)
        self.widget_canvas.itemconfigure(self._status_rect,
            fill=zynthian_gui_config.color_panel_bg,
            outline=zynthian_gui_config.color_off)

        mid_x = (sx1 + sx2) // 2
        status_pad = max(10, available_w // 40)
        cy = top + row_h // 2

        left_cx = (sx1 + status_pad + mid_x - status_pad) // 2
        right_cx = (mid_x + status_pad + sx2 - status_pad) // 2

        self.widget_canvas.coords(self._status_text, left_cx, cy)
        self.widget_canvas.itemconfigure(self._status_text,
            font=(zynthian_gui_config.font_family, fs_status + 1, "bold"),
            width=max(12, mid_x - status_pad - sx1 - status_pad))

        self.widget_canvas.coords(self._chord_text, right_cx, cy)
        self.widget_canvas.itemconfigure(self._chord_text,
            font=(zynthian_gui_config.font_family, fs_status + 4, "bold"),
            width=max(12, sx2 - status_pad - mid_x - status_pad))

        pads_top = top + row_h + gap
        self._layout_section_pads(pads_top, bottom, left, width, gap, row_h, inner_gap, col_w)

    def _layout_section_pads(self, top, bottom, left, width, gap, row_h, inner_gap, col_w):
        """Position the 8 pad slots and cache slot→section mappings."""
        fs_pad = max(9, min(width // 48, row_h // 3))
        slots = self._build_slot_map()

        for i, slot in enumerate(slots):
            col_idx = i % _NUM_PAD_COLS
            row_idx = i // _NUM_PAD_COLS
            x1 = left + col_idx * (col_w + inner_gap)
            y1 = top + row_idx * (row_h + inner_gap)
            x2 = x1 + col_w
            y2 = y1 + row_h
            self.widget_canvas.coords(self._pad_rects[i], x1, y1, x2, y2)
            self.widget_canvas.coords(self._pad_texts[i], (x1 + x2) // 2, (y1 + y2) // 2)
            self.widget_canvas.itemconfigure(self._pad_texts[i],
                font=(zynthian_gui_config.font_family, fs_pad, "bold"),
                width=max(12, col_w - 8))

            # Cache slot data for _update_items()
            if slot is not None:
                self._pad_sec_idx[i] = slot[0]
                self._pad_sec_label[i] = slot[1]
            else:
                self._pad_sec_idx[i] = None
                self._pad_sec_label[i] = ""

    def _build_slot_map(self):
        """Return a list of 8 elements (None or (sec_idx, sec_name)).

        Fixed layout:
          Row 0 (top): [Intro] [Ending] [Fill A] [Fill B]
          Row 1 (btm): [Main A] [Main B] [Main C] [Main D]
        """
        indexed = list(enumerate(self.sections))
        intro   = [s for s in indexed if s[1].lower().startswith("intro")]
        ending  = [s for s in indexed if s[1].lower().startswith("ending")]
        fill    = [s for s in indexed if s[1].lower().startswith("fill")]
        main    = [s for s in indexed if not any(
                      s[1].lower().startswith(p) for p in ("intro", "ending", "fill"))]
        row0 = [
            intro[0]  if len(intro)  > 0 else None,
            ending[0] if len(ending) > 0 else None,
            fill[0]   if len(fill)   > 0 else None,
            fill[1]   if len(fill)   > 1 else None,
        ]
        row1 = [
            main[0] if len(main) > 0 else None,
            main[1] if len(main) > 1 else None,
            main[2] if len(main) > 2 else None,
            main[3] if len(main) > 3 else None,
        ]
        return row0 + row1

    # ------------------------------------------------------------------
    # State update (called on data change – NO delete/recreate)
    # ------------------------------------------------------------------

    def _update_items(self):
        """Update text and colours of existing canvas items without touching geometry."""
        cfg = zynthian_gui_config

        # Title
        self.widget_canvas.itemconfigure(self.style_text,
            text=self.style_name if self.style_name else "No style loaded")

        # Playback status
        playing = self.playing
        sync_waiting = (playing
                        and self.chord_gate_mode == CHORD_GATE_SYNC_START
                        and not self.detected_chord)
        if sync_waiting:
            icon  = "⏸"
            word  = "SYNC START"
            color = cfg.color_ml
        elif playing:
            icon  = "▶"
            word  = "PLAYING"
            color = cfg.color_hl
        else:
            icon  = "■"
            word  = "STOPPED"
            color = cfg.color_low_on
        self.widget_canvas.itemconfigure(self._status_text,
            text=f"{icon} {word}", fill=color)

        # Chord display
        if self.detected_chord:
            self.widget_canvas.itemconfigure(self._chord_text,
                text=self.detected_chord,
                fill=cfg.color_ml,
                state=tkinter.NORMAL)
        else:
            self.widget_canvas.itemconfigure(self._chord_text, state=tkinter.HIDDEN)

        # Section pads
        for i in range(_NUM_PADS):
            label = self._pad_sec_label[i]
            if self._pad_sec_idx[i] is None:
                # Empty slot – show a dim placeholder
                self.widget_canvas.itemconfigure(self._pad_rects[i],
                    fill=cfg.color_bg, outline="#303030", width=1)
                self.widget_canvas.itemconfigure(self._pad_texts[i],
                    state=tkinter.HIDDEN)
            else:
                active = (label == self.current_section)
                fill       = cfg.color_ml  if active else cfg.color_off
                text_color = cfg.color_bg  if active else cfg.color_tx
                self.widget_canvas.itemconfigure(self._pad_rects[i],
                    fill=fill, outline=cfg.color_off, width=2)
                self.widget_canvas.itemconfigure(self._pad_texts[i],
                    text=label, fill=text_color, state=tkinter.NORMAL)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_pad_click(self, slot_idx):
        sec_idx = self._pad_sec_idx[slot_idx]
        if sec_idx is not None and self.processor:
            if 0 <= sec_idx < len(self.sections):
                self.processor.engine.select_section(sec_idx)

    def show(self):
        super().show()

    def hide(self):
        super().hide()

    def set_processor(self, processor):
        super().set_processor(processor)
        self._read_state()
        self._layout()

    def update(self):
        if self.shown and self.zyngui_control.shown:
            self.get_monitors()
            self.refresh_gui()

    def refresh_gui(self):
        if self.refreshing or not self.monitors:
            return
        self.refreshing = True
        try:
            changed = False
            sections_changed = False

            new_style = self.monitors.get('style_file', "")
            if new_style != self.style_name:
                self.style_name = new_style
                changed = True

            new_sections = self.monitors.get('sections', [])
            if new_sections != self.sections:
                self.sections = new_sections
                sections_changed = True
                changed = True

            new_current = self.monitors.get('current_section', "")
            if new_current != self.current_section:
                self.current_section = new_current
                changed = True

            new_playing = self.monitors.get('playing', False)
            if new_playing != self.playing:
                self.playing = new_playing
                changed = True

            new_instruments = self.monitors.get('channel_instruments', {})
            if new_instruments != self.channel_instruments:
                self.channel_instruments = new_instruments
                changed = True

            new_chord = self.monitors.get('detected_chord', "")
            if new_chord != self.detected_chord:
                self.detected_chord = new_chord
                changed = True

            new_cgm = self.monitors.get('chord_gate_mode', 0)
            if new_cgm != self.chord_gate_mode:
                self.chord_gate_mode = new_cgm
                changed = True

            new_tempo = self.monitors.get('tempo', self.tempo)
            if new_tempo != self.tempo:
                self.tempo = new_tempo
                changed = True

            if changed:
                if sections_changed:
                    # Sections list changed: re-run geometry to reassign pad slots,
                    # then apply state.  No canvas items are deleted or recreated.
                    self._layout()
                else:
                    # Only text/colour state changed: skip geometry entirely.
                    self._update_items()
        except Exception as e:
            logging.error(f"Companion widget refresh error: {e}")
        finally:
            self.refreshing = False

    def _read_state(self):
        """Read initial state from the engine monitors."""
        if self.processor:
            monitors = self.processor.engine.get_monitors_dict()
            if monitors:
                self.style_name = monitors.get('style_file', "")
                self.sections = monitors.get('sections', [])
                self.current_section = monitors.get('current_section', "")
                self.playing = monitors.get('playing', False)
                self.tempo = monitors.get('tempo', 120.0)
                self.channel_instruments = monitors.get('channel_instruments', {})
                self.detected_chord = monitors.get('detected_chord', "")
                self.chord_gate_mode = monitors.get('chord_gate_mode', 0)

    def switch(self, swi, t='S'):
        if swi == 0 and t == 'S':
            self.zyngui.cuia_bank_preset()
            return True
        return False

    def show_menu(self):
        if not self.processor:
            return
        self.zyngui.screens['processor_options'].processor = self.processor
        self.zyngui.show_screen('processor_options', hmode=self.zyngui.SCREEN_HMODE_ADD)

    def on_play_click(self, event):
        if self.processor:
            self.processor.engine.start_playing()

    def on_stop_click(self, event):
        if self.processor:
            self.processor.engine.stop_playing()

    def on_section_click(self, section_idx):
        """Select a section when clicked."""
        if self.processor and 0 <= section_idx < len(self.sections):
            self.processor.engine.select_section(section_idx)

# ------------------------------------------------------------------------------
