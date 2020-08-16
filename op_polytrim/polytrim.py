'''
Created on Oct 8, 2015

@author: Patrick
'''
import time

import bpy

from ..subtrees.addon_common.cookiecutter.cookiecutter import CookieCutter
from ..subtrees.addon_common.common import ui
from ..subtrees.addon_common.common.utils import get_settings
from ..subtrees.addon_common.common.boundvar import BoundInt, BoundFloat, BoundBool
#from ..subtrees.addon_common.common.ui import Drawing


from .polytrim_states        import Polytrim_States280
from .polytrim_ui_init       import Polytrim_UI_Init280
from .polytrim_ui_tools      import Polytrim_UI_Tools
from .polytrim_ui_draw       import Polytrim_UI_Draw280
from .polytrim_datastructure import InputNetwork, NetworkCutter, SplineNetwork
from .polytrim_render  import SplineNetworkRender
from .polytrim_render import opts as render_opts


#some settings container
options = {}
options["variable_1"] = 5.0
options["variable_3"] = True

#ModalOperator
class CutMesh_Polytrim(Polytrim_States280, Polytrim_UI_Init280, Polytrim_UI_Tools, Polytrim_UI_Draw280):
    ''' Cut Mesh Polytrim Modal Editor '''
    ''' Note: the functionality of this operator is split up over multiple base classes '''

    operator_id    = "cut_mesh.polytrim"    # operator_id needs to be the same as bl_idname
                                            # important: bl_idname is mangled by Blender upon registry :(
    bl_idname      = "cut_mesh.polytrim"
    bl_label       = "Polytrim"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_options = {'REGISTER','UNDO'}

    #for this, checkout "polystrips_props.py'
    @property
    def variable_2_gs(self):
        return getattr(self, '_var_cut_count_value', 0)
    @variable_2_gs.setter
    def variable_2_gs(self, v):
        if self.variable_2 == v: return
        self.variable_2 = v
        
        
    default_keymap = {
        # key: a human-readable label
        # val: a str or a set of strings representing the user action
        'action': {'LEFTMOUSE'},
        'redraw':{'D'},
        'sketch': {'SHIFT+LEFTMOUSE'},
        'select': {'LEFTMOUSE'},
        'connect': {'LEFTMOUSE'},
        'add point': {'LEFTMOUSE'},
        'add point (disconnected)': {'CTRL+LEFTMOUSE'},
        'cancel': {'ESC', 'RIGHTMOUSE'},
        'grab': 'G',
        'delete': {'RIGHTMOUSE'},
        'paint delete':{'CTRL+RIGHTMOUSE'},
        'delete (disconnect)': {'CTRL+RIGHTMOUSE'},
        'preview cut': 'C',
        'up': 'UP_ARROW',
        'down': 'DOWN_ARROW'
        # ... more
    }

    @classmethod
    def can_start(cls, context):
        ''' Called when tool is invoked to determine if tool can start '''
        if context.mode != 'OBJECT':
            #showErrorMessage('Object Mode please')
            return False
        if not context.object:
            return False
        if context.object.type != 'MESH':
            #showErrorMessage('Must select a mesh object')
            return False

        #if context.object.hide:
        #    return False

        return True

    def start_pre(self):
        prefs = get_settings()  #get this addon settings
        
        self.load_ob_name = ''
        self.destructive = prefs.destructive
        
        return
    
    def behavior_preferences(self):
        
        prefs = get_settings() 
        self.spline_preview_tess = prefs.spline_preview_tess
        self.sketch_fit_epsilon = prefs.sketch_fit_epsilon
        self.patch_boundary_fit_epsilon =  prefs.patch_boundary_fit_epsilon
        self.spline_tessellation_epsilon = prefs.spline_tessellation_epsilon
        
        
    
    def start(self):
        
        self.start_pre()
        
        if self.load_ob_name == '':
            self.load_ob_name = self.context.object.name + '_cut_mesh'
        
        self.cursor_modal_set('CROSSHAIR')

        #self.drawing = Drawing.get_instance()
        #self.drawing.set_region(bpy.context.region, bpy.context.space_data.region_3d, bpy.context.window)?
        self.mode_pos        = (0, 0)
        self.cur_pos         = (0, 0)
        self.mode_radius     = 0
        self.action_center   = (0, 0)
        
        #SAMPLE VARIABLES FOR UI
        self.variable_1 = BoundFloat('''options['variable_1']''', min_value =0.5, max_value = 15.5)
        self.variable_2 = BoundInt('''self.variable_2_gs''',  min_value = 0, max_value = 10)
        self.variable_3 = BoundBool('''options['variable_3']''')
        
        source_ob = bpy.context.object
        self.net_ui_context = self.NetworkUIContext(source_ob, geometry_mode = self.destructive)

        self.hint_bad = False   #draw obnoxious things over the bad segments
        self.input_net = InputNetwork(self.net_ui_context)
        self.spline_net = SplineNetwork(self.net_ui_context)
        self.network_cutter = NetworkCutter(self.input_net, self.net_ui_context)
        self.sketcher = self.SketchManager(self.input_net, self.spline_net, self.net_ui_context, self.network_cutter)
        self.grabber = self.GrabManager(self.input_net, self.net_ui_context, self.network_cutter)
        self.brush = None
        self.brush_radius = 1.5
        
        self.check_depth = 0
        self.autofix_max_attempts = 2  #will subdivide and attempt to fix bad segments
        self.last_bad_check = time.time()
        self.seed_iterations = 10000
        
        self.behavior_preferences()

        self.polytrim_render = SplineNetworkRender(self.spline_net, 
                                                   self.network_cutter, 
                                                   render_opts)
        
        
        self.setup_ui()
        
        self.load_from_bmesh()
        #self.fsm_setup()
        #self.window_state_overwrite(show_only_render=False, hide_manipulator=True)

    def end(self):
        ''' Called when tool is ending modal '''
        self.header_text_set()
        self.cursor_modal_restore()

    def update(self):
        pass