'''
Created on Oct 11, 2015

@author: Patrick
'''

import time
import random

import bpy
from bpy_extras import view3d_utils
from ..subtrees.addon_common.cookiecutter.cookiecutter import CookieCutter
from ..subtrees.addon_common.common import ui
from ..subtrees.addon_common.common.blender import show_error_message


from .polytrim_datastructure import InputPoint, SplineSegment, CurveNode


class Polytrim_UI_Init280(CookieCutter):
    def tool_action(self):
        print('tool action')
        return

    
    def bl_ui_vis_setup(self):
        
        #TODO THIS IS MORE BLENDER UI SETTINGS TO MANAGE
        space = bpy.context.space_data
        space.shading.type = 'SOLID'
        space.shading.color_type = 'VERTEX'
        
        
        pass
        
    def setup_ui(self):
        
        #go ahead and open these files
        #addon_common.common.ui
        #addon_common.cookiecutter.cookiecutter_ui
        
        #know that every CookieCutter instance has self.document upon startup
        #most of our ui elements are going to be children of self.document.body
        
        #we generate our UI elements using the methods in ui.py
        
        #we need to read ui_core, particulalry UI_Element
        

        self.bl_ui_vis_setup()
        
        
        #collapsible, and framed_dialog
        #first, know
        
        self.ui_main = ui.framed_dialog(label = 'Polytrim - Region outlining and mesh cutting tool.',
                                          resizable = True,
                                          resizable_x = True,
                                          resizable_y=True, 
                                          closeable=False, 
                                          moveable=True, 
                                          hide_on_close=False,
                                          parent=self.document.body)
        
        # main menu
        self.main_menu = ui.div(id="main_menu", parent=self.ui_main)

        self.main_menu_btn = ui.button(label='Menu', title = 'Back to main menu.', parent=self.main_menu, on_mouseclick=self.main_menu_options)
        self.EXIT_addon = ui.button(label='Close Tool', title = 'Exit the addon.', parent=self.main_menu, on_mouseclick=self.exit_addon)

        



        #spline menu
        self.cut_workflow_container = ui.collection(label="Cut Workflow", parent = self.main_menu)
        pick_seed = ui.button(label='Pick Seed', title = 'Pick Seed', parent=self.main_menu, on_mouseclick=self.launch_seed)
        compute_cut = ui.button(label='Compute Cut', title = 'Compute Cut', parent=self.main_menu, on_mouseclick=self.compute_cut_button)
        self.cut_workflow_container.builder([pick_seed, compute_cut])

        #spline menu
        self.ui_outline_container = ui.collection(label="Outline Properties", parent = self.main_menu)
        o_create = ui.button(label='Draw/Edit Curves', title = 'Create region boundaries.', parent=self.ui_outline_container, on_mouseclick=self.launch_spline_create)
        #o_edit = ui.button(label='Edit', title = 'Edit selected region boundary.', parent=self.ui_outline_container, on_mouseclick=self.tool_action)
        #o_save = ui.button(label='Save', title = 'Save region boundary as a spline in the scene.', parent=self.ui_outline_container, on_mouseclick=self.tool_action)
        #o_select = ui.button(label='Select', title = 'Select existing region boundary spline.', parent=self.ui_outline_container, on_mouseclick=self.tool_action)
        
        
        #menu for after cutting
        self.segmentation_menu = ui.div(id="segmentatino_menue", parent=self.main_menu, is_visible=True)
        delete_patch = ui.button(label='Delete Patch', title = '(delete the active patch)', parent=self.segmentation_menu, on_mouseclick=self.delete_active_patch)
        separate_patch = ui.button(label='Separate Patch', title = '(separate the active patch to new object)', parent=self.segmentation_menu, on_mouseclick=self.separate_active_patch)
        duplicate_patch = ui.button(label='Duplicate Patch', title = '(Duplicate the active patch to new object)', parent=self.segmentation_menu, on_mouseclick=self.separate_active_patch)
        
        #TODO delete_non_patch = ui.button(label='Keep Patches', title = '(Delete all non-patch geometry)', parent=self.segmentation_menu, on_mouseclick=self.delete_non_patch')
        self.segmentation_menu.builder([delete_patch, separate_patch, duplicate_patch])
        
        #spline_cancel = ui.button(label='Cancel', title = 'Cancel procedure.', parent=self.spline_create_menu, on_mouseclick=self.tool_action)
        
        
        
        #spline create sub-menu
        #self.spline_create_menu = ui.div(id="spline_create_menu", parent=self.ui_outline_container, is_visible=False)
        #spline_back = ui.button(label='Back', title = '(prev step description).', parent=self.spline_create_menu, on_mouseclick=self.tool_action)
        #spline_next = ui.button(label='Next', title = '(next step description).', parent=self.spline_create_menu, on_mouseclick=self.tool_action)
        #spline_cancel = ui.button(label='Cancel', title = 'Cancel procedure.', parent=self.spline_create_menu, on_mouseclick=self.tool_action)

        #self.ui_outline_container.builder([o_create, o_edit, o_save, o_select, self.spline_create_menu])
        
        
        #region menu
        #self.ui_region_container = ui.collection(label='Region Properties', parent = self.ui_main)
        #r_inward = ui.button(label='Select Inward', title = 'Select region enclosed by boundary.', parent=self.main_menu, on_mouseclick=self.tool_action)
        #r_outward = ui.button(label='Select Outward', title = 'Select everything outside of boundary.', parent=self.main_menu, on_mouseclick=self.tool_action)
        #r_grow = ui.button(label='Grow Selection', title = 'Increase boundary area with shape preserved.', parent=self.main_menu, on_mouseclick=self.tool_action)
        #r_shrink = ui.button(label='Shrink Selection', title = 'Decrease boundary area with shape preserved.', parent=self.main_menu, on_mouseclick=self.tool_action)
        #boundary_step = ui.labeled_input_text(label='Boundary Size Step', title='Integer property reflecting the step size when using Grow or Shrink Selection', value= self.variable_2)
        #self.ui_region_container.builder([r_inward, r_outward, r_grow, r_shrink, boundary_step])

        #ui_mesh_container = ui.collapsible("Mesh Properties", parent = self.ui_main, collapsed = False)
        #m_cut = ui.button(label='Cut Region', title = 'Copy the region into a new object and delete the selected region from existing mesh.', parent= self.ui_main, on_mouseclick=self.tool_action)
        #m_copy = ui.button(label='Copy Region', title = 'Copy the region into a new object.', parent=self.ui_main, on_mouseclick=self.tool_action)
        #m_delete = ui.button(label='Delete Region', title = 'Delete region from existing mesh. ', parent=self.ui_main, on_mouseclick=self.tool_action)
        #ui_mesh_container.builder([m_cut, m_copy, m_delete])

        #mesh menu
        #self.ui_mesh_container = ui.collection(label="Mesh Properties", parent = self.ui_main)
        #m_cut = ui.button(label='Cut Region', title = 'Copy the region into a new object and delete the selected region from existing mesh.', parent=self.main_menu, on_mouseclick=self.tool_action)
        #m_copy = ui.button(label='Copy Region', title = 'Copy the region into a new object.', parent=self.main_menu, on_mouseclick=self.tool_action)
        #m_delete = ui.button(label='Delete Region', title = 'Delete region from existing mesh. ', parent=self.main_menu, on_mouseclick=self.tool_action)
        #self.ui_mesh_container.builder([m_cut, m_copy, m_delete])
        

 
 

    def main_menu_options(self):
        self.ui_region_container.is_visible = True
        self.ui_mesh_container.is_visible = True
        #self.main_menu_btn.is_visible = False
        self.spline_create_menu.is_visible = False
        self.fsm.force_set_state("main") #

    def launch_spline_create(self):
        #self.ui_region_container.is_visible = False
        #self.ui_mesh_container.is_visible = False
        #self.main_menu_btn.is_visible = True
        #self.spline_create_menu.is_visible = True
        self.fsm.force_set_state("spline main")
        

    def launch_seed(self):
        self.fsm.force_set_state("seed")
        
    
    def compute_cut_button(self):
        self.network_cutter.knife_geometry4()
        
        self.network_cutter.find_perimeter_edges()
        for patch in self.network_cutter.face_patches:
            patch.grow_seed(self.input_net.bme, self.network_cutter.boundary_edges, max_iters = self.seed_iterations)
            patch.color_patch()
            patch.find_all_boundary_edges()  #TODO @Patrick @Jonas  
            
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        
        self.fsm.force_set_state('segmentation')
        
            
    def exit_addon(self):
        self.done(cancel = True)
        #self.fsm.force_set_state("EXIT_addon")

        
        
        
class Polytrim_UI_Init():
    def ui_setup(self):
        self.instructions = {
            "add": "Left-click on the mesh to add a new point",
            "add (extend)": "Left-click to add new a point connected to the selected point. The green line will visualize the new segments created",
            "add (insert)": "Left-click on a segment to insert a new a point. The green line will visualize the new segments created",
            "close loop": "Left-click on the outer hover ring of existing point to close a boundary loop",
            "select": "Left-click on a point to select it",
            "sketch": "Hold Shift + left-click and drag to sketch in a series of points",
            "sketch extend": "Hover near an existing point, Shift + Left-click and drag to sketch in a series of points",
            "delete": "Right-click on a point to remove it",
            "delete (disconnect)": "Ctrl + right-click will remove a point and its connected segments",
            "tweak": "left click and drag a point to move it",
            "tweak confirm": "Release to place point at cursor's location",
            "paint": "Left-click to paint",
            "paint extend": "Left-click inside and then paint outward from an existing patch to extend it",
            "paint greedy": "Painting from one patch into another will remove area from 2nd patch and add it to 1st",
            "paint mergey": "Painting from one patch into another will merge the two patches",
            "paint remove": "Right-click and drag to delete area from patch",
            "seed add": "Left-click within a boundary to indicate it as patch segment",
            "segmentation" : "Left-click on a patch to select it, then use the segmentation buttons to apply changes"
        }

        def mode_getter():
            return self._state
        def mode_setter(m):
            self.fsm_change(m)
        def mode_change():
            nonlocal precut_container, segmentation_container, paint_radius
            m = self._state
            precut_container.visible = (m in {'spline', 'seed', 'region'})
            paint_radius.visible = (m in {'region'})
            no_options.visible = not (m in {'region'})
            segmentation_container.visible = (m in {'segmentation'})
        self.fsm_change_callback(mode_change)

        def radius_getter():
            return self.brush_radius
        def radius_setter(v):
            self.brush_radius = max(0.1, int(v*10)/10)
            if self.brush:
                self.brush.radius = self.brush_radius

        # def compute_cut():
        #     # should this be a state instead?
        #     self.network_cutter.knife_geometry4()
        #     self.network_cutter.find_perimeter_edges()
        #     for patch in self.network_cutter.face_patches:
        #         patch.grow_seed(self.input_net.bme, self.network_cutter.boundary_edges)
        #         patch.color_patch()
        #     self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        #     self.fsm_change('segmentation')

        win_tools = self.wm.create_window('Polytrim Tools', {'pos':7, 'movable':True, 'bgcolor':(0.50, 0.50, 0.50, 0.90)})

        precut_container = win_tools.add(ui.UI_Container(rounded=1))

        precut_tools = precut_container.add(ui.UI_Frame('Pre Cut Tools', fontsize=16, spacer=0))
        precut_mode = precut_tools.add(ui.UI_Options(mode_getter, mode_setter, separation=0, rounded=1))
        precut_mode.add_option('Boundary Edit', value='spline', icon=ui.UI_Image('polyline.png', width=32, height=32))
        precut_mode.add_option('Boundary > Region', value='seed', icon=ui.UI_Image('seed.png', width=32, height=32))
        precut_mode.add_option('Region Paint', value='region', icon=ui.UI_Image('paint.png', width=32, height=32))

        container = precut_container.add(ui.UI_Frame('Cut Tools', fontsize=16, spacer=0))
        container.add(ui.UI_Button('Compute Cut', lambda:self.fsm_change('segmentation'), align=-1, icon=ui.UI_Image('divide32.png', width=32, height=32)))
        container.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), align=0))


        segmentation_container = win_tools.add(ui.UI_Container())
        segmentation_tools = segmentation_container.add(ui.UI_Frame('Segmentation Tools', fontsize=16, spacer=0))
        #segmentation_mode = segmentation_tools.add(ui.UI_Options(mode_getter, mode_setter))
        #segmentation_mode.add_option('Segmentation', value='segmentation', margin = 5)
        #seg_buttons = segmentation_tools.add(ui.UI_EqualContainer(margin=0,vertical=False))
        segmentation_tools.add(ui.UI_Button('Delete', self.delete_active_patch, tooltip='Delete the selected patch', align=-1, icon=ui.UI_Image('delete_patch32.png', width=32, height=32)))
        segmentation_tools.add(ui.UI_Button('Separate', self.separate_active_patch, tooltip='Separate the selected patch', align=-1, icon=ui.UI_Image('separate32.png', width=32, height=32)))
        segmentation_tools.add(ui.UI_Button('Duplicate', self.duplicate_active_patch, tooltip='Duplicate the selected patch', align=-1, icon=ui.UI_Image('duplicate32.png', width=32, height=32)))
        #seg_buttons.add(ui.UI_Button('Patch to VGroup', self.active_patch_to_vgroup, margin=5))

        container = segmentation_container.add(ui.UI_Frame('Cut Tools', fontsize=16, spacer=0))
        container.add(ui.UI_Button('Commit', self.done, align=0))
        container.add(ui.UI_Button('Cancel', lambda:self.done(cancel=True), align=0))


        info = self.wm.create_window('Polytrim Help', {'pos':9, 'movable':True, 'bgcolor':(0.30, 0.60, 0.30, 0.90)})
        #info.add(ui.UI_Label('Instructions', fontsize=16, align=0, margin=4))
        self.inst_paragraphs = [info.add(ui.UI_Markdown('', min_size=(200,10))) for i in range(7)]
        #for i in self.inst_paragraphs: i.visible = False
        #self.ui_instructions = info.add(ui.UI_Markdown('test', min_size=(200,200)))
        precut_options = info.add(ui.UI_Frame('Tool Options', fontsize=16, spacer=0))
        paint_radius = precut_options.add(ui.UI_Number("Paint radius", radius_getter, radius_setter))
        no_options = precut_options.add(ui.UI_Label('(none)', color=(1.00, 1.00, 1.00, 0.25)))
        
        
        self.set_ui_text_no_points()


    # XXX: Fine for now, but will likely be irrelevant in future
    def ui_text_update(self):
        '''
        updates the text in the info box
        '''
        if self._state == 'spline':
            if self.input_net.is_empty:
                self.set_ui_text_no_points()
            elif self.input_net.num_points == 1:
                self.set_ui_text_1_point()
            elif self.input_net.num_points > 1:
                self.set_ui_text_multiple_points()
            elif self.grabber and self.grabber.in_use:
                self.set_ui_text_grab_mode()

        elif self._state == 'region':
            self.set_ui_text_paint()
        elif self._state == 'seed':
            self.set_ui_text_seed_mode()

        elif self._state == 'segmentation':
            self.set_ui_text_segmetation_mode()

        else:
            self.reset_ui_text()

    # XXX: Fine for now, but will likely be irrelevant in future
    def set_ui_text_no_points(self):
        ''' sets the viewports text when no points are out '''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['add'])
        self.inst_paragraphs[1].set_markdown('B) ' + self.instructions['sketch'])

    def set_ui_text_1_point(self):
        ''' sets the viewports text when 1 point has been placed'''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['add (extend)'])
        self.inst_paragraphs[1].set_markdown('B) ' + self.instructions['delete'])
        self.inst_paragraphs[2].set_markdown('C) ' + self.instructions['sketch extend'])
        self.inst_paragraphs[3].set_markdown('C) ' + self.instructions['select'])
        self.inst_paragraphs[4].set_markdown('D) ' + self.instructions['tweak'])
        #self.inst_paragraphs[5].set_markdown('E) ' + self.instructions['add (disconnect)'])
        self.inst_paragraphs[6].set_markdown('F) ' + self.instructions['delete (disconnect)'])

        #self.inst_paragraphs[4].set_markdown('E) ' + self.instructions['add (disconnect)'])


    def set_ui_text_multiple_points(self):
        ''' sets the viewports text when there are multiple points '''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['add (extend)'])
        self.inst_paragraphs[1].set_markdown('B) ' + self.instructions['add (insert)'])
        self.inst_paragraphs[2].set_markdown('C) ' + self.instructions['delete'])
        self.inst_paragraphs[3].set_markdown('D) ' + self.instructions['delete (disconnect)'])
        self.inst_paragraphs[4].set_markdown('E) ' + self.instructions['sketch'])
        self.inst_paragraphs[5].set_markdown('F) ' + self.instructions['tweak'])
        self.inst_paragraphs[6].set_markdown('G) ' + self.instructions['close loop'])

    def set_ui_text_grab_mode(self):
        ''' sets the viewports text during general creation of line '''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['tweak confirm'])

    def set_ui_text_seed_mode(self):
        ''' sets the viewport text during seed selection'''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['seed add'])

    def set_ui_text_segmetation_mode(self):
        ''' sets the viewport text during seed selection'''
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['segmentation'])

    def set_ui_text_paint(self):
        self.reset_ui_text()
        self.inst_paragraphs[0].set_markdown('A) ' + self.instructions['paint'])
        self.inst_paragraphs[1].set_markdown('B) ' + self.instructions['paint extend'])
        self.inst_paragraphs[2].set_markdown('C) ' + self.instructions['paint remove'])
        self.inst_paragraphs[3].set_markdown('D) ' + self.instructions['paint mergey'])

    def reset_ui_text(self):
        for inst_p in self.inst_paragraphs:
            inst_p.set_markdown('')
