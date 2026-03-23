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
    COLOR_PLAYING = "#00C000"
    COLOR_STOPPED = "#C04040"
    COLOR_SECTION_ACTIVE = "#FFD040"
    COLOR_SECTION_NORMAL = "#808080"
    COLOR_CHANNEL_TEXT = "#B0B0B0"
    COLOR_INSTRUMENT_TEXT = "#E0E0E0"

    def __init__(self, parent):
        super().__init__(parent)
        self.refreshing = False
        self.style_name = ""
        self.sections = []
        self.current_section = ""
        self.playing = False
        self.channel_instruments = {}
        self.section_items = []
        self.channel_items = []

        # Main canvas
        self.widget_canvas = tkinter.Canvas(self,
            bd=0,
            highlightthickness=0,
            relief='flat',
            bg=zynthian_gui_config.color_panel_bg)
        self.widget_canvas.grid(sticky='news')

        # Style name display
        self.style_text = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.NW,
            font=(zynthian_gui_config.font_family, 10),
            fill=zynthian_gui_config.color_panel_tx,
            text="No style loaded"
        )

        # Transport status indicator
        self.transport_indicator = self.widget_canvas.create_oval(
            0, 0, 12, 12,
            fill=self.COLOR_STOPPED,
            outline=""
        )
        self.transport_text = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.NW,
            font=(zynthian_gui_config.font_family, 9),
            fill=zynthian_gui_config.color_panel_tx,
            text="STOPPED"
        )

        # Sections header
        self.sections_header = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.NW,
            font=(zynthian_gui_config.font_family, 8),
            fill=zynthian_gui_config.color_tx_off,
            text="SECTIONS"
        )

        # Channels header
        self.channels_header = self.widget_canvas.create_text(
            0, 0,
            anchor=tkinter.NW,
            font=(zynthian_gui_config.font_family, 8),
            fill=zynthian_gui_config.color_tx_off,
            text="CHANNEL INSTRUMENTS"
        )

        # Bind click on transport indicator to toggle play/stop
        self.widget_canvas.tag_bind(self.transport_indicator, "<ButtonPress-1>", self.on_transport_click)
        self.widget_canvas.tag_bind(self.transport_text, "<ButtonPress-1>", self.on_transport_click)

    def on_size(self, event):
        if super().on_size(event):
            self._layout()

    def _layout(self):
        """Recalculate positions and sizes of all UI elements."""
        w = self.width
        h = self.height
        pad = max(4, w // 80)
        fs_title = max(8, w // 28)
        fs_status = max(7, w // 32)
        fs_header = max(6, w // 38)
        fs_item = max(6, w // 36)

        y = pad

        # Style name
        self.widget_canvas.coords(self.style_text, pad, y)
        self.widget_canvas.itemconfigure(self.style_text,
            font=(zynthian_gui_config.font_family, fs_title),
            width=w - 2 * pad)
        y += fs_title + pad

        # Transport indicator
        indicator_size = max(8, fs_status)
        self.widget_canvas.coords(self.transport_indicator,
            pad, y, pad + indicator_size, y + indicator_size)
        self.widget_canvas.coords(self.transport_text,
            pad + indicator_size + pad, y)
        self.widget_canvas.itemconfigure(self.transport_text,
            font=(zynthian_gui_config.font_family, fs_status))
        y += indicator_size + pad + 2

        # Sections header
        self.widget_canvas.coords(self.sections_header, pad, y)
        self.widget_canvas.itemconfigure(self.sections_header,
            font=(zynthian_gui_config.font_family, fs_header))
        y += fs_header + 2

        # Sections - remove old and create new
        for item in self.section_items:
            self.widget_canvas.delete(item)
        self.section_items = []

        section_y = y
        for i, section in enumerate(self.sections):
            is_active = (section == self.current_section)
            color = self.COLOR_SECTION_ACTIVE if is_active else self.COLOR_SECTION_NORMAL
            prefix = "\u25b6 " if is_active else "  "
            item = self.widget_canvas.create_text(
                pad + 4, section_y,
                anchor=tkinter.NW,
                font=(zynthian_gui_config.font_family, fs_item, "bold" if is_active else ""),
                fill=color,
                text=prefix + section,
                tags=f"section_{i}"
            )
            self.widget_canvas.tag_bind(item, "<ButtonPress-1>",
                lambda event, idx=i: self.on_section_click(idx))
            self.section_items.append(item)
            section_y += fs_item + 2

        y = section_y + pad

        # Channels header
        self.widget_canvas.coords(self.channels_header, pad, y)
        self.widget_canvas.itemconfigure(self.channels_header,
            font=(zynthian_gui_config.font_family, fs_header))
        y += fs_header + 2

        # Channel instruments - remove old and create new
        for item in self.channel_items:
            self.widget_canvas.delete(item)
        self.channel_items = []

        if self.channel_instruments:
            for ch in sorted(self.channel_instruments.keys()):
                instr_name = self.channel_instruments[ch]
                ch_label = f"Ch {ch + 1:2d}: {instr_name}"
                item = self.widget_canvas.create_text(
                    pad + 4, y,
                    anchor=tkinter.NW,
                    font=(zynthian_gui_config.font_family, fs_item),
                    fill=self.COLOR_INSTRUMENT_TEXT,
                    text=ch_label
                )
                self.channel_items.append(item)
                y += fs_item + 1
        else:
            item = self.widget_canvas.create_text(
                pad + 4, y,
                anchor=tkinter.NW,
                font=(zynthian_gui_config.font_family, fs_item),
                fill=zynthian_gui_config.color_tx_off,
                text="No instruments loaded"
            )
            self.channel_items.append(item)

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
                self.channel_instruments = monitors.get('channel_instruments', {})

    def _update_display(self):
        """Update displayed text and indicators."""
        # Update style name
        display_name = self.style_name if self.style_name else "No style loaded"
        self.widget_canvas.itemconfigure(self.style_text, text=display_name)

        # Update transport
        if self.playing:
            self.widget_canvas.itemconfigure(self.transport_indicator,
                fill=self.COLOR_PLAYING)
            self.widget_canvas.itemconfigure(self.transport_text,
                text="PLAYING")
        else:
            self.widget_canvas.itemconfigure(self.transport_indicator,
                fill=self.COLOR_STOPPED)
            self.widget_canvas.itemconfigure(self.transport_text,
                text="STOPPED")

        # Rebuild sections and channels
        self._layout()

    def on_transport_click(self, event):
        """Toggle play/stop when the transport indicator is clicked."""
        if self.processor:
            if self.playing:
                self.processor.engine.stop_playing()
            else:
                self.processor.engine.start_playing()

    def on_section_click(self, section_idx):
        """Select a section when clicked."""
        if self.processor and 0 <= section_idx < len(self.sections):
            self.processor.engine.select_section(section_idx)

# ------------------------------------------------------------------------------
