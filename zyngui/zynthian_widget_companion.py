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
    COLOR_TAB_ACTIVE = "#396A96"
    COLOR_TAB_INACTIVE = "#2A2A2A"
    COLOR_TAB_TEXT = "#F0F0F0"

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

    VIEW_PERFORMANCE = "performance"
    VIEW_PRESETS = "presets"
    VIEW_INSTRUMENTS = "instruments"

    INSTRUMENTS_PAGE_SIZE = 8

    def __init__(self, parent):
        super().__init__(parent)
        self.refreshing = False
        self.active_view = self.VIEW_PERFORMANCE
        self.style_name = ""
        self.sections = []
        self.current_section = ""
        self.playing = False
        self.tempo = 120.0
        self.channel_instruments = {}
        self.detected_chord = ""
        self.instrument_scroll = 0

        self.tab_items = []
        self.performance_items = []
        self.preset_items = []
        self.instrument_items = []

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

        nav_bottom = self._draw_top_navigation(pad, y, w)
        content_top = nav_bottom + pad

        if self.active_view == self.VIEW_PERFORMANCE:
            self._layout_performance(content_top, h - pad, pad, w)
        elif self.active_view == self.VIEW_PRESETS:
            self._layout_presets(content_top, h - pad, pad, w)
        else:
            self._layout_instruments(content_top, h - pad, pad, w)

    def _draw_top_navigation(self, left, top, width):
        tabs = [
            (self.VIEW_PERFORMANCE, "PERFORMANCE"),
            (self.VIEW_PRESETS, "PRESETS"),
            (self.VIEW_INSTRUMENTS, "INSTRUMENTS"),
        ]
        gap = max(4, width // 120)
        tab_h = max(32, self.height // 12)
        tab_w = (width - (2 * left) - (2 * gap)) // 3

        x = left
        for view_name, label in tabs:
            active = (view_name == self.active_view)
            fill = self.COLOR_TAB_ACTIVE if active else self.COLOR_TAB_INACTIVE
            rect = self.widget_canvas.create_rectangle(
                x, top, x + tab_w, top + tab_h,
                fill=fill,
                outline=self.COLOR_BUTTON_BORDER,
                width=2,
                tags="dynamic"
            )
            text = self.widget_canvas.create_text(
                x + tab_w // 2,
                top + tab_h // 2,
                anchor=tkinter.CENTER,
                font=(zynthian_gui_config.font_family, max(9, width // 55), "bold"),
                fill=self.COLOR_TAB_TEXT,
                text=label,
                tags="dynamic"
            )
            self.widget_canvas.tag_bind(rect, "<ButtonPress-1>", lambda event, v=view_name: self.on_view_select(v))
            self.widget_canvas.tag_bind(text, "<ButtonPress-1>", lambda event, v=view_name: self.on_view_select(v))
            x += tab_w + gap

        return top + tab_h

    def _layout_performance(self, top, bottom, left, width):
        content_h = max(1, bottom - top)
        gap = max(6, min(width, content_h) // 60)
        fs_status = max(8, width // 50)

        # Three equal-height rows: controls, sections row 1, sections row 2.
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

    def _layout_presets(self, top, bottom, left, width):
        fs_header = max(10, width // 38)
        fs_text = max(9, width // 48)
        fs_button = max(11, width // 36)

        self.widget_canvas.create_text(
            left,
            top,
            anchor=tkinter.NW,
            font=(zynthian_gui_config.font_family, fs_header, "bold"),
            fill=zynthian_gui_config.color_panel_tx,
            text="PRESET LIST",
            tags="dynamic"
        )

        message = "Open the standard preset selection screen to browse and load styles."
        self.widget_canvas.create_text(
            left,
            top + fs_header + 8,
            anchor=tkinter.NW,
            font=(zynthian_gui_config.font_family, fs_text),
            fill=self.COLOR_INSTRUMENT_TEXT,
            text=message,
            width=width - (2 * left),
            tags="dynamic"
        )

        btn_w = max(140, width - (2 * left))
        btn_h = max(54, (bottom - top) // 5)
        btn_x = left
        btn_y = top + max(70, (bottom - top) // 3)

        rect = self.widget_canvas.create_rectangle(
            btn_x, btn_y, btn_x + btn_w, btn_y + btn_h,
            fill=self.COLOR_BUTTON_BG,
            outline=self.COLOR_BUTTON_BORDER,
            width=2,
            tags="dynamic"
        )
        text = self.widget_canvas.create_text(
            btn_x + btn_w // 2,
            btn_y + btn_h // 2,
            anchor=tkinter.CENTER,
            font=(zynthian_gui_config.font_family, fs_button, "bold"),
            fill=self.COLOR_BUTTON_TEXT,
            text="OPEN PRESET SELECTOR",
            tags="dynamic"
        )
        self.widget_canvas.tag_bind(rect, "<ButtonPress-1>", self.on_open_preset_list)
        self.widget_canvas.tag_bind(text, "<ButtonPress-1>", self.on_open_preset_list)

    def _layout_instruments(self, top, bottom, left, width):
        fs_header = max(10, width // 40)
        fs_row = max(9, width // 50)
        fs_hint = max(8, width // 56)
        gap = max(4, self.height // 110)

        self.widget_canvas.create_text(
            left,
            top,
            anchor=tkinter.NW,
            font=(zynthian_gui_config.font_family, fs_header, "bold"),
            fill=zynthian_gui_config.color_panel_tx,
            text="AVAILABLE INSTRUMENTS",
            tags="dynamic"
        )

        y = top + fs_header + 6
        instruments = [(ch, self.channel_instruments[ch]) for ch in sorted(self.channel_instruments.keys())]

        if not instruments:
            self.widget_canvas.create_text(
                left,
                y,
                anchor=tkinter.NW,
                font=(zynthian_gui_config.font_family, fs_row),
                fill=zynthian_gui_config.color_tx_off,
                text="No instruments loaded",
                tags="dynamic"
            )
            return

        total = len(instruments)
        self.instrument_scroll = max(0, min(self.instrument_scroll, max(0, total - self.INSTRUMENTS_PAGE_SIZE)))
        visible = instruments[self.instrument_scroll:self.instrument_scroll + self.INSTRUMENTS_PAGE_SIZE]

        list_h = max(1, bottom - y - 44)
        row_h = max(28, (list_h - (len(visible) - 1) * gap) // max(1, len(visible)))

        for i, (channel, name) in enumerate(visible):
            y1 = y + i * (row_h + gap)
            y2 = y1 + row_h
            self.widget_canvas.create_rectangle(
                left, y1, width - left, y2,
                fill=self.COLOR_CHANNEL_BG,
                outline=self.COLOR_BUTTON_BORDER,
                width=1,
                tags="dynamic"
            )
            self.widget_canvas.create_text(
                left + 8,
                y1 + row_h // 2,
                anchor=tkinter.W,
                font=(zynthian_gui_config.font_family, fs_row, "bold"),
                fill=self.COLOR_CHANNEL_TEXT,
                text=f"Ch {channel + 1}",
                tags="dynamic"
            )
            self.widget_canvas.create_text(
                left + max(58, width // 8),
                y1 + row_h // 2,
                anchor=tkinter.W,
                font=(zynthian_gui_config.font_family, fs_row),
                fill=self.COLOR_INSTRUMENT_TEXT,
                text=name,
                width=width - left * 2 - max(68, width // 8),
                tags="dynamic"
            )

        range_text = f"{self.instrument_scroll + 1}-{self.instrument_scroll + len(visible)} of {total}"
        hint_y = bottom - 36
        self.widget_canvas.create_text(
            left,
            hint_y,
            anchor=tkinter.NW,
            font=(zynthian_gui_config.font_family, fs_hint),
            fill=zynthian_gui_config.color_tx_off,
            text=range_text,
            tags="dynamic"
        )

        if total > self.INSTRUMENTS_PAGE_SIZE:
            btn_w = max(54, width // 7)
            btn_h = max(28, self.height // 16)
            right = width - left

            prev_rect = self.widget_canvas.create_rectangle(
                right - 2 * btn_w - 6,
                hint_y - 4,
                right - btn_w - 6,
                hint_y - 4 + btn_h,
                fill=self.COLOR_BUTTON_BG,
                outline=self.COLOR_BUTTON_BORDER,
                width=1,
                tags="dynamic"
            )
            prev_text = self.widget_canvas.create_text(
                right - int(1.5 * btn_w) - 6,
                hint_y - 4 + btn_h // 2,
                anchor=tkinter.CENTER,
                font=(zynthian_gui_config.font_family, fs_hint + 1, "bold"),
                fill=self.COLOR_BUTTON_TEXT,
                text="UP",
                tags="dynamic"
            )
            self.widget_canvas.tag_bind(prev_rect, "<ButtonPress-1>", lambda event: self.on_instrument_scroll(-1))
            self.widget_canvas.tag_bind(prev_text, "<ButtonPress-1>", lambda event: self.on_instrument_scroll(-1))

            next_rect = self.widget_canvas.create_rectangle(
                right - btn_w,
                hint_y - 4,
                right,
                hint_y - 4 + btn_h,
                fill=self.COLOR_BUTTON_BG,
                outline=self.COLOR_BUTTON_BORDER,
                width=1,
                tags="dynamic"
            )
            next_text = self.widget_canvas.create_text(
                right - btn_w // 2,
                hint_y - 4 + btn_h // 2,
                anchor=tkinter.CENTER,
                font=(zynthian_gui_config.font_family, fs_hint + 1, "bold"),
                fill=self.COLOR_BUTTON_TEXT,
                text="DOWN",
                tags="dynamic"
            )
            self.widget_canvas.tag_bind(next_rect, "<ButtonPress-1>", lambda event: self.on_instrument_scroll(1))
            self.widget_canvas.tag_bind(next_text, "<ButtonPress-1>", lambda event: self.on_instrument_scroll(1))

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
                self.instrument_scroll = 0

    def _update_display(self):
        """Update displayed text and indicators."""
        # Update style name
        display_name = self.style_name if self.style_name else "No style loaded"
        self.widget_canvas.itemconfigure(self.style_text, text=display_name)

        # Rebuild active view
        self._layout()

    def on_view_select(self, view_name):
        if view_name not in (self.VIEW_PERFORMANCE, self.VIEW_PRESETS, self.VIEW_INSTRUMENTS):
            return
        if view_name != self.active_view:
            self.active_view = view_name
            self._layout()

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

    def on_open_preset_list(self, event):
        if not self.processor:
            return
        try:
            self.processor.load_preset_list()
            self.zyngui.show_screen('preset')
        except Exception as err:
            logging.error(f"Companion widget: can't open preset list => {err}")

    def on_instrument_scroll(self, direction):
        total = len(self.channel_instruments)
        max_scroll = max(0, total - self.INSTRUMENTS_PAGE_SIZE)
        self.instrument_scroll = max(0, min(max_scroll, self.instrument_scroll + direction))
        self._layout()

# ------------------------------------------------------------------------------
