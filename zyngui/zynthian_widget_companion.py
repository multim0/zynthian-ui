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

# ------------------------------------------------------------------------------
# Zynthian Widget Class for "Companion Style Player"
# ------------------------------------------------------------------------------


class zynthian_widget_companion(zynthian_widget_base.zynthian_widget_base):

    # Colors
    COLOR_VIEW_BG = "#1A1A1A"

    COLOR_PLAYING = "#00C000"
    COLOR_STOPPED = "#C04040"
    COLOR_BUTTON_BG = "#3A3A3A"
    COLOR_BUTTON_BORDER = "#7A7A7A"
    COLOR_BUTTON_TEXT = "#F0F0F0"

    COLOR_SECTION_ACTIVE = "#FFD040"
    COLOR_SECTION_NORMAL = "#646464"

    COLOR_STATUS_BOX = "#1F2C1F"
    COLOR_STATUS_TEXT = "#D8FFD8"

    COLOR_CHANNEL_BG = "#212121"
    COLOR_CHANNEL_TEXT = "#D8D8D8"
    COLOR_INSTRUMENT_TEXT = "#E0E0E0"

    COLOR_CHORD_BOX = "#2E3E2E"
    COLOR_CHORD_TEXT = "#E8FF9E"

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

        # Main canvas
        self.widget_canvas = tkinter.Canvas(self,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg=self.COLOR_VIEW_BG)
        self.widget_canvas.grid(sticky='news')

        # Style name display
        self.style_text = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.NW,
            font=(zynthian_gui_config.font_family, 12, "bold"),
            fill=zynthian_gui_config.color_panel_tx,
            text="No style loaded"
        )

    def on_size(self, event):
        if super().on_size(event):
            self._layout()

    def _layout(self):
        """Recalculate positions and sizes of all UI elements."""
        w = self.width
        h = self.height
        pad = max(8, min(w, h) // 45)
        fs_title = max(10, w // 30)

        self.widget_canvas.delete("dynamic")

        # Style title (always visible)
        y = pad
        self.widget_canvas.coords(self.style_text, pad, y)
        self.widget_canvas.itemconfigure(self.style_text,
            font=(zynthian_gui_config.font_family, fs_title),
            width=w - 2 * pad)
        title_bbox = self.widget_canvas.bbox(self.style_text)
        if title_bbox:
            y = title_bbox[3] + pad
        else:
            y += fs_title + pad

        self._layout_performance(y, h - pad, pad, w)

    def _layout_performance(self, top, bottom, left, width):
        content_h = max(1, bottom - top)
        gap = max(6, min(width, content_h) // 60)
        fs_status = max(8, width // 50)

        # Three equal-height rows: status, sections row 1, sections row 2.
        row_h = max(36, (content_h - 2 * gap) // 3)

        # Match section grid geometry exactly: 4 cols, inner_gap between each.
        inner_gap = max(4, gap // 2)
        available_w = width - 2 * left
        col_w = (available_w - 3 * inner_gap) // 4

        # Status box spans full width. Transport is controlled by the hardware knob.
        status_x1 = left
        status_x2 = left + (4 * col_w) + (3 * inner_gap)
        self.widget_canvas.create_rectangle(
            status_x1, top, status_x2, top + row_h,
            fill=self.COLOR_STATUS_BOX,
            outline=self.COLOR_BUTTON_BORDER,
            width=1,
            tags="dynamic"
        )
        status_icon = "▶" if self.playing else "■"
        status_text = "PLAYING" if self.playing else "STOPPED"
        status_color = self.COLOR_PLAYING if self.playing else self.COLOR_STOPPED
        chord = self.detected_chord if self.detected_chord else None
        mid_x = (status_x1 + status_x2) // 2
        status_pad = max(10, available_w // 40)
        left_x1 = status_x1 + status_pad
        left_x2 = mid_x - status_pad
        right_x1 = mid_x + status_pad
        right_x2 = status_x2 - status_pad

        # Left region: playback state with symmetric horizontal margins.
        self.widget_canvas.create_text(
            (left_x1 + left_x2) // 2,
            top + row_h // 2,
            anchor=tkinter.CENTER,
            font=(zynthian_gui_config.font_family, fs_status + 1, "bold"),
            fill=status_color,
            text=f"{status_icon} {status_text}",
            width=max(12, left_x2 - left_x1),
            tags="dynamic"
        )

        # Right region: chord name with symmetric horizontal margins.
        if chord:
            self.widget_canvas.create_text(
                (right_x1 + right_x2) // 2,
                top + row_h // 2,
                anchor=tkinter.CENTER,
                font=(zynthian_gui_config.font_family, fs_status + 4, "bold"),
                fill=self.COLOR_CHORD_TEXT,
                text=chord,
                width=max(12, right_x2 - right_x1),
                tags="dynamic"
            )

        y = top + row_h + gap
        self._layout_section_pads(y, bottom, left, width, gap, row_h)

    def _layout_section_pads(self, top, bottom, left, width, gap, row_h=None):
        sections = [(i, s) for i, s in enumerate(self.sections)]

        available_w = max(1, width - 2 * left)
        inner_gap = max(4, gap // 2)

        # Partition sections by type.
        intro_sec = [s for s in sections if s[1].lower().startswith("intro")]
        ending_sec = [s for s in sections if s[1].lower().startswith("ending")]
        fill_sec = [s for s in sections if s[1].lower().startswith("fill")]
        main_sec = [s for s in sections if not any(s[1].lower().startswith(x) for x in ["intro", "ending", "fill"])]

        # Fixed 2x4 grid for muscle-memory: slot positions never change.
        # Row 1: [Intro] [Ending] [Fill A] [Fill B]
        # Row 2: [Main A] [Main B] [Main C] [Main D]
        row1 = [
            intro_sec[0] if len(intro_sec) > 0 else None,
            ending_sec[0] if len(ending_sec) > 0 else None,
            fill_sec[0] if len(fill_sec) > 0 else None,
            fill_sec[1] if len(fill_sec) > 1 else None,
        ]
        row2 = [
            main_sec[0] if len(main_sec) > 0 else None,
            main_sec[1] if len(main_sec) > 1 else None,
            main_sec[2] if len(main_sec) > 2 else None,
            main_sec[3] if len(main_sec) > 3 else None,
        ]

        cols = 4
        col_w = (available_w - (cols - 1) * inner_gap) // cols
        # Use provided row_h for equal rows; fall back to half of available.
        if row_h is None:
            row_h = (max(1, bottom - top) - inner_gap) // 2
        fs_pad = max(9, min(width // 48, row_h // 3))

        for row_idx, row in enumerate([row1, row2]):
            y1 = top + row_idx * (row_h + inner_gap)
            y2 = y1 + row_h
            for col_idx, slot in enumerate(row):
                x1 = left + col_idx * (col_w + inner_gap)
                x2 = x1 + col_w
                if slot is None:
                    self.widget_canvas.create_rectangle(
                        x1, y1, x2, y2,
                        fill="#1A1A1A",
                        outline="#303030",
                        width=1,
                        tags="dynamic"
                    )
                    continue
                idx, section = slot
                active = (section == self.current_section)
                fill = self.COLOR_SECTION_ACTIVE if active else self.COLOR_SECTION_NORMAL
                text_color = "#202020" if active else self.COLOR_BUTTON_TEXT
                rect = self.widget_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=fill,
                    outline=self.COLOR_BUTTON_BORDER,
                    width=2,
                    tags="dynamic"
                )
                text = self.widget_canvas.create_text(
                    (x1 + x2) // 2,
                    (y1 + y2) // 2,
                    anchor=tkinter.CENTER,
                    font=(zynthian_gui_config.font_family, fs_pad, "bold"),
                    fill=text_color,
                    text=section,
                    width=max(12, col_w - 8),
                    tags="dynamic"
                )
                self.widget_canvas.tag_bind(rect, "<ButtonPress-1>", lambda event, i=idx: self.on_section_click(i))
                self.widget_canvas.tag_bind(text, "<ButtonPress-1>", lambda event, i=idx: self.on_section_click(i))

    def _draw_action_button(self, x, y, width, height, label, color, callback, font_size):
        rect = self.widget_canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill=color,
            outline=self.COLOR_BUTTON_BORDER,
            width=2,
            tags="dynamic"
        )
        text = self.widget_canvas.create_text(
            x + width // 2,
            y + height // 2,
            anchor=tkinter.CENTER,
            font=(zynthian_gui_config.font_family, font_size, "bold"),
            fill="#101010",
            text=label,
            tags="dynamic"
        )
        self.widget_canvas.tag_bind(rect, "<ButtonPress-1>", callback)
        self.widget_canvas.tag_bind(text, "<ButtonPress-1>", callback)

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

            new_style = self.monitors.get('style_file', "")
            if new_style != self.style_name:
                self.style_name = new_style
                changed = True

            new_sections = self.monitors.get('sections', [])
            if new_sections != self.sections:
                self.sections = new_sections
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

            new_tempo = self.monitors.get('tempo', self.tempo)
            if new_tempo != self.tempo:
                self.tempo = new_tempo
                changed = True

            if changed:
                self._update_display()
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

    def _update_display(self):
        """Update displayed text and indicators."""
        # Update style name
        display_name = self.style_name if self.style_name else "No style loaded"
        self.widget_canvas.itemconfigure(self.style_text, text=display_name)

        # Rebuild active view
        self._layout()

    def switch(self, swi, t='S'):
        # Handle admin/option button: open presets/instruments browser
        # Similar flow to step-sequencer piano roll opening its options menu
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
