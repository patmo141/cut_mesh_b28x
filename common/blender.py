'''
Copyright (C) 2017 CG Cookie
http://cgcookie.com
hello@cgcookie.com

Created by Jonathan Denning, Jonathan Williamson

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

import bpy
from .decorators import blender_version_wrapper

@blender_version_wrapper("<=", "2.79")
def get_preferences(ctx=None):
    return (ctx if ctx else bpy.context).user_preferences
@blender_version_wrapper(">=", "2.80")
def get_preferences(ctx=None):
    return (ctx if ctx else bpy.context).preferences



#############################################################
# TODO: generalize these functions to be add_object, etc.

@blender_version_wrapper('<=','2.79')
def set_object_layers(o):
    o.layers = list(bpy.context.scene.layers)
@blender_version_wrapper('>=','2.80')
def set_object_layers(o):
    print('unhandled: set_object_layers')
    pass

@blender_version_wrapper('<=','2.79')
def set_object_selection(o, sel):
    o.select = sel
@blender_version_wrapper('>=','2.80')
def set_object_selection(o, sel):
    o.select_set('SELECT' if sel else 'DESELECT')

@blender_version_wrapper('<=','2.79')
def link_object(o):
    bpy.context.scene.objects.link(o)
@blender_version_wrapper('>=','2.80')
def link_object(o):
    print('unhandled: link_object')
    pass

@blender_version_wrapper('<=','2.79')
def set_active_object(o):
    bpy.context.scene.objects.active = o
@blender_version_wrapper('>=','2.80')
def set_active_object(o):
    print('unhandled: set_active_object')
    pass

@blender_version_wrapper('<=','2.79')
def get_active_object():
    return bpy.context.scene.objects.active
@blender_version_wrapper('>=','2.80')
def get_active_object():
    return bpy.context.active_object



def show_blender_popup(message, title="Message", icon="INFO", wrap=80):
    '''
    icons: NONE, QUESTION, ERROR, CANCEL,
           TRIA_RIGHT, TRIA_DOWN, TRIA_LEFT, TRIA_UP,
           ARROW_LEFTRIGHT, PLUS,
           DISCLOSURE_TRI_DOWN, DISCLOSURE_TRI_RIGHT,
           RADIOBUT_OFF, RADIOBUT_ON,
           MENU_PANEL, BLENDER, GRIP, DOT, COLLAPSEMENU, X,
           GO_LEFT, PLUG, UI, NODE, NODE_SEL,
           FULLSCREEN, SPLITSCREEN, RIGHTARROW_THIN, BORDERMOVE,
           VIEWZOOM, ZOOMIN, ZOOMOUT, ...
    see: https://git.blender.org/gitweb/gitweb.cgi/blender.git/blob/HEAD:/source/blender/editors/include/UI_icons.h
    '''  # noqa

    if not message: return
    lines = message.splitlines()
    if wrap > 0:
        nlines = []
        for line in lines:
            spc = len(line) - len(line.lstrip())
            while len(line) > wrap:
                i = line.rfind(' ',0,wrap)
                if i == -1:
                    nlines += [line[:wrap]]
                    line = line[wrap:]
                else:
                    nlines += [line[:i]]
                    line = line[i+1:]
                if line:
                    line = ' '*spc + line
            nlines += [line]
        lines = nlines
    def draw(self,context):
        for line in lines:
            self.layout.label(line)
    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
    return

def show_error_message(message, title="Error", wrap=80):
    show_blender_popup(message, title, "ERROR", wrap)

def create_and_show_blender_text(text, name='A Report', hide_header=True, goto_top=True):
    # create a new textblock for reporting
    bpy.ops.text.new()                  # create new text block, which is appended to list
    bpy.data.texts[-1].name = name      # set name, but if another object exists with the
    name = bpy.data.texts[-1].name      # same name, blender will append .001 (or similar)
    bpy.data.texts[name].text = text    # set text of text block
    show_blender_text(name, hide_header=hide_header, goto_top=goto_top)

def show_blender_text(textblock_name, hide_header=True, goto_top=True):
    if textblock_name not in bpy.data.texts:
        # no textblock to show
        return

    txt = bpy.data.texts[textblock_name]
    if goto_top:
        txt.current_line_index = 0

    # duplicate the current area then change it to a text editor
    area_dupli = bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
    win = bpy.context.window_manager.windows[-1]
    area = win.screen.areas[-1]
    area.type = 'TEXT_EDITOR'

    # load the text file into the correct space
    for space in area.spaces:
        if space.type == 'TEXT_EDITOR':
            space.text = txt
            space.show_word_wrap = True
            space.top = 0
            if hide_header and area.regions[0].height != 1:
                # hide header
                bpy.ops.screen.header({'window':win, 'region':area.regions[2], 'area':area})

def bversion(short=True):
    major,minor,rev = bpy.app.version
    bver_long = '%03d.%03d.%03d' % (major,minor,rev)
    bver_short = '%d.%02d' % (major, minor)
    return bver_short if short else bver_long

