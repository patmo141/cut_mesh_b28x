'''
Copyright (C) 2018 CG Cookie

https://github.com/CGCookie/retopoflow

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import math

import bpy
import bgl

from ..common.decorators import blender_version_wrapper
from ..common.debug import debugger
from ..common.drawing import Drawing
from ..common.ui import UI_WindowManager
from ..common.utils import iter_head


class CookieCutter_Blender:
    def blenderui_init(self):
        self._area = self.context.area
        self._space = self.context.space_data
        self._window = self.context.window
        self._screen = self.context.screen
        self._region = self.context.region
        self._rgn3d = self.context.space_data.region_3d
        self.manipulator_store()
        self.panels_store()
        self.overlays_store()

    def blenderui_end(self):
        self.overlays_restore()
        self.panels_restore()
        self.manipulator_restore()
        self.cursor_modal_restore()
        self.header_text_restore()


    #########################################
    # Header

    @blender_version_wrapper("<=", "2.79")
    def header_text_set(self, s=None):
        if s is None:
            self._area.header_text_set()
        else:
            self._area.header_text_set(s)
    @blender_version_wrapper(">=", "2.80")
    def header_text_set(self, s=None):
        self._area.header_text_set(s)

    def header_text_restore(self):
        self.header_text_set()


    #########################################
    # Cursor

    def cursor_modal_set(self, v):
        self._window.cursor_modal_set(v)

    def cursor_modal_restore(self):
        self._window.cursor_modal_restore()


    #########################################
    # Panels

    def panels_get_details(self):
        # regions for 3D View:
        #     279: [ HEADER, TOOLS, TOOL_PROPS, UI, WINDOW ]
        #     280: [ HEADER, TOOLS, UI,         '', WINDOW ]  ( yes, there is no name at index 3 :( )
        #            0       1      2           3   4
        # could hard code the indices, but these magic numbers might change.
        # will stick to magic (but also way more descriptive) types
        rgn_header = iter_head(r for r in self._area.regions if r.type == 'HEADER')
        rgn_toolshelf = iter_head(r for r in self._area.regions if r.type == 'TOOLS')
        rgn_properties = iter_head(r for r in self._area.regions if r.type == 'UI')
        return (rgn_header, rgn_toolshelf, rgn_properties)

    def panels_store(self):
        rgn_header,rgn_toolshelf,rgn_properties = self.panels_get_details()
        show_header,show_toolshelf,show_properties = rgn_header.height>1, rgn_toolshelf.width>1, rgn_properties.width>1
        self._show_header = show_header
        self._show_toolshelf = show_toolshelf
        self._show_properties = show_properties

    def panels_restore(self):
        rgn_header,rgn_toolshelf,rgn_properties = self.panels_get_details()
        show_header,show_toolshelf,show_properties = rgn_header.height>1, rgn_toolshelf.width>1, rgn_properties.width>1
        ctx = {
            'area': self._area,
            'space_data': self._space,
            'window': self._window,
            'screen': self._screen,
            'region': self._region,
        }
        if self._show_header and not show_header: bpy.ops.screen.header(ctx)
        if self._show_toolshelf and not show_toolshelf: bpy.ops.view3d.toolshelf(ctx)
        if self._show_properties and not show_properties: bpy.ops.view3d.properties(ctx)

    def panels_hide(self):
        rgn_header,rgn_toolshelf,rgn_properties = self.panels_get_details()
        show_header,show_toolshelf,show_properties = rgn_header.height>1, rgn_toolshelf.width>1, rgn_properties.width>1
        if show_header: bpy.ops.screen.header()
        if show_toolshelf: bpy.ops.view3d.toolshelf()
        if show_properties: bpy.ops.view3d.properties()


    #########################################
    # Overlays and Manipulators/Gizmos

    @blender_version_wrapper("<=", "2.79")
    def overlays_get(self): return None
    @blender_version_wrapper("<=", "2.79")
    def overlays_set(self, v): pass

    @blender_version_wrapper("<=", "2.80")
    def overlays_get(self): return self._space.overlay.show_overlays
    @blender_version_wrapper("<=", "2.80")
    def overlays_set(self, v): self._space.overlay.show_overlays = v

    @blender_version_wrapper("<=", "2.79")
    def manipulator_get(self): return self._space.show_manipulator
    @blender_version_wrapper("<=", "2.79")
    def manipulator_set(self, v): self._space.show_manipulator = v

    @blender_version_wrapper(">=", "2.80")
    def manipulator_get(self):    return self._space.show_gizmo
    @blender_version_wrapper(">=", "2.80")
    def manipulator_set(self, v): self._space.show_gizmo = v

    def overlays_store(self):   self._overlays = self.overlays_get()
    def overlays_restore(self): self.overlays_set(self._overlays)
    def overlays_hide(self):    self.overlays_set(False)

    def manipulator_store(self):   self._manipulator = self.manipulator_get()
    def manipulator_restore(self): self.manipulator_set(self._manipulator)
    def manipulator_hide(self):    self.manipulator_set(False)
    def manipulator_show(self):    self.manipulator_set(True)

    def gizmo_store(self):         self._manipulator = self.manipulator_get()
    def gizmo_restore(self):       self.manipulator_set(self._manipulator)
    def gizmo_hide(self):          self.manipulator_set(False)
    def gizmo_show(self):          self.manipulator_set(True)
