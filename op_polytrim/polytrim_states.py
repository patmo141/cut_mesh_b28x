'''
Created on Oct 11, 2015

@author: Patrick
'''

import time
import random

from bpy_extras import view3d_utils

from ..subtrees.addon_common.cookiecutter.cookiecutter import CookieCutter
from ..subtrees.addon_common.common.blender import show_error_message, tag_redraw_all
from ..subtrees.addon_common.common.fsm import FSM

from .polytrim_datastructure import InputPoint, SplineSegment, CurveNode

'''
these are the states and substates (tool states)

    main --> spline                         (automatically switch to default tool)
        spline --> seed,region
        seed   --> spline,region
        region --> spline,seed
    spline,seed,region --> segmentation     (pre cut -> post cut)

    spline tool:
        main --> grab   --> main
        main --> sketch --> main

    seed tool:
        (no states)

    region tool:
        main --> paint --> main

    segmentation
'''


class Polytrim_States280(CookieCutter): #(CookieCutter) <- May need to do it this way
    # spline, seed selection
    
    #spline main
        #hover
        #click
        #sketching
            #enter
                #mousemove
                #release
                
        #grab/tweak
            #enter
                #mousemove
                #release
            #exit
        
    #seed main
        #click

    #segmentation
        #hover patch
        #select_patch
        #menu operators
        




    #main menu states
    @CookieCutter.FSM_State('main')
    def main(self):        
        return 'spline main'

    
    ######################################################
    # spline editing
    @CookieCutter.FSM_State('spline main', 'enter')
    def spline_enter(self):
        self.create_points_batch()
        self.polytrim_render._gather_data()
        tag_redraw_all('spline_enter')
        
    @CookieCutter.FSM_State('spline main')
    def spline_main(self):
        
        if self.actions.pressed('RET'):
            self.done()
            return

        #if self.actions.pressed('ESC'):
        #    self.done(cancel=True)
        #    return
                
        #if self.actions.pressed('ESC'):
        #    return 'cancel'
            

        if self.actions.pressed('cancel'):
            #self.main_menu_options()
            pass
            
            
        if self.actions.pressed('redraw'):
            self.create_points_batch()
            self.polytrim_render._gather_data()
            tag_redraw_all('delete point')
            return 'spline main'

        mouse_just_stopped = self.actions.mousemove_prev and not self.actions.mousemove
        if mouse_just_stopped:
            self.net_ui_context.update(self.actions.mouse)
            #TODO: Bring hover into NetworkUiContext
            self.hover_spline()
            if self.net_ui_context.hovered_near[0] == 'POINT':
                self.cursor_modal_set('HAND')
            else:
                self.cursor_modal_set('CROSSHAIR')
            #print(self.net_ui_context.hovered_near)
            #self.net_ui_context.inspect_print()

        if self.actions.pressed('select', unpress=False):
            if self.spline_select_can_enter():
                self.actions.unpress()
                return 'spline select'

        if self.actions.pressed('connect', unpress=False):
            if self.spline_connect_can_enter():
                self.actions.unpress()
                self.cache_to_bmesh()
                return 'spline connect'

        if self.actions.pressed('add point', unpress=False):
            # first try to add a connected point
            # if that fails, try to add a disconnected point
            if self.spline_add_point_can_enter():
                self.actions.unpress()
                self.cache_to_bmesh()
                return 'add point'
        
            elif self.spline_add_point_disconnected_can_enter():
                self.actions.unpress()
                return 'add point (disconnected)'
            elif self.spline_insert_point_can_enter():
                self.cache_to_bmesh()
                return 'insert point'

        if self.actions.pressed('sketch'):
            self.cache_to_bmesh()
            return 'sketch'

        if self.actions.pressed('add point (disconnected)'):
            self.cache_to_bmesh()
            return 'add point (disconnected)'

        if self.actions.pressed('grab'):
            return 'grab'

        if self.actions.pressed('delete'):
            self.click_delete_spline_point(mode='mouse')
            self.net_ui_context.update(self.actions.mouse)

            self.hover_spline()
            self.polytrim_render._gather_data()
            tag_redraw_all('delete point')
            self.cache_to_bmesh()
            #self.ui_text_update()
            return

        if self.actions.pressed('delete (disconnect)'):
            self.click_delete_spline_point('mouse', True)
            self.net_ui_context.update(self.actions.mouse)
            self.hover_spline()
            self.polytrim_render._gather_data()
            tag_redraw_all('delete point')
            self.cache_to_bmesh()
            #self.ui_text_update()
            return

        
        if self.actions.timer and self.autofix_max_attempts > 0:
            
            #make sure we aren't checking constantly
            
            dt = time.time() - self.last_bad_check
            if dt < 1.5: return
            
            self.last_bad_check = time.time()
            
            #don't keep recursively dividing segments
            if self.check_depth > self.autofix_max_attempts: 
                print('maxed out number of checks')
                return
            
            #need all segments to be attempted before trying
            if not all([seg.calculation_complete for seg in self.input_net.segments]):
                print('still processing')
                return
            
            #if all segments are good...
            if not any([seg.is_bad for seg in self.input_net.segments]):
                if self.check_depth != 0:
                    print('solved all the problems!')
                    self.check_depth = 0
                return
            
            #ok, now we can attempt to bisect bad segment 
            
            self.check_depth += 1
            self.split_bad_spline_segments()
    #--------------------------------------
    # spline select (this is the oddball, but becaue sketching and grabbing are states, we made "select" a
    # state that then can be entered and existed quickly or push the unser into tweaking/grab

    @CookieCutter.FSM_State('spline select', 'can enter')
    def spline_select_can_enter(self):
        return self.net_ui_context.hovered_near[0] in {'POINT'}

    @CookieCutter.FSM_State('spline select')
    def spline_select(self):
        self.net_ui_context.selected = self.net_ui_context.hovered_near[1]
        self.tweak_release = 'select'
        self.tweak_cancel = 'cancel'
        return 'tweak'


    #--------------------------------------
    # spline tweak

    @CookieCutter.FSM_State('tweak', 'can enter')
    def spline_tweak_can_enter(self):
        if not self.net_ui_context.selected: return False
        if not hasattr(self, 'tweak_release'): self.tweak_release = None
        if not hasattr(self, 'tweak_press'): self.tweak_press = None
        if not hasattr(self, 'tweak_cancel'): self.tweak_cancel = None
        assert self.tweak_release or self.tweak_press, 'Must set either self.tweak_release or self.tweak_press!'
        return True

    @CookieCutter.FSM_State('tweak', 'enter')
    def spline_tweak_enter(self):
        context = self.context  #bpy.context?
        loc3d_reg2D = view3d_utils.location_3d_to_region_2d
        self.tweak_point_p2d = loc3d_reg2D(context.region, context.space_data.region_3d, self.net_ui_context.selected.world_loc)
        self.tweak_mousedown = self.actions.mouse
        self.tweak_moving = False
        self.grabber.initiate_grab_point()
        #self.ui_text_update()

    @CookieCutter.FSM_State('tweak')
    def spline_tweak(self):
        if self.tweak_release and self.actions.released(self.tweak_release):
            return 'spline main'
        if self.tweak_press and self.actions.pressed(self.tweak_press):
            return 'spline main'
        if self.tweak_cancel and self.actions.pressed(self.tweak_cancel):
            #put it back!
            self.grabber.grab_cancel()
            return 'spline main'

        if (self.tweak_mousedown - self.actions.mouse).length > 5:
            self.tweak_moving = True

        if self.tweak_moving and self.actions.mousemove:
            p2d = self.tweak_point_p2d + (self.actions.mouse - self.tweak_mousedown)
            self.net_ui_context.update(p2d)
            self.net_ui_context.nearest_non_man_loc()
            self.grabber.move_grab_point(self.context, p2d)
            self.polytrim_render._gather_data()
            tag_redraw_all('grabing!')

    @CookieCutter.FSM_State('tweak', 'exit')
    def spline_tweak_exit(self):
        #confirm location
        if self.tweak_moving:
            self.grabber.finalize(self.context)
            if isinstance(self.net_ui_context.selected, CurveNode):
                self.spline_net.push_to_input_net(self.net_ui_context, self.input_net)
                self.network_cutter.update_segments_async()
                
                self.create_points_batch()
                self.polytrim_render._gather_data()
                tag_redraw_all('update segments')
                
                
        
            else:
                self.network_cutter.update_segments()
        #self.ui_text_update()
        self.tweak_press = None
        self.tweak_release = None
        self.tweak_cancel = None
        self.cache_to_bmesh()

    #--------------------------------------
    # connect (two endpoints)

    @CookieCutter.FSM_State('spline connect', 'can enter')
    def spline_connect_can_enter(self):
        # make sure selected is an endpoint
        s = self.net_ui_context.selected
        if not s or not s.is_endpoint: return False
        # make sure near is an endpoint
        if self.net_ui_context.hovered_near[0] not in {'POINT CONNECT'}: return False
        n = self.net_ui_context.hovered_near[1]
        if not n or not n.is_endpoint: return False  #impose loops condition
        if s == n:
            print('same point')
            return False
        return True

    @CookieCutter.FSM_State('spline connect')
    def spline_connect(self):
        s = self.net_ui_context.selected
        n = self.net_ui_context.hovered_near[1]
        assert s and n
        self.add_spline(s, n)
        self.net_ui_context.selected = n
        self.tweak_release = 'connect'
        self.tweak_cancel = 'cancel'
        return 'tweak'


    #--------------------------------------
    # add point (connected to selected endpoint)

    @CookieCutter.FSM_State('add point', 'can enter')
    def spline_add_point_can_enter(self):
        # make sure selected is an endpoint
        s = self.net_ui_context.selected
        if not s or not s.is_endpoint: return False

        hn = self.net_ui_context.hovered_near
        if hn and hn[0] == 'EDGE': return False

        # make sure mouse is over source
        if not self.ray_cast_source_hit(self.actions.mouse): return False
        return True

    @CookieCutter.FSM_State('add point')
    def spline_add_point(self):
        s = self.net_ui_context.selected
        n = self.add_point(self.actions.mouse)
        assert s and n
        self.add_spline(s, n)
        self.net_ui_context.selected = n
        self.tweak_release = 'add point'
        self.tweak_cancel = 'cancel'
        return 'tweak'


    #--------------------------------------
    # insert point

    @CookieCutter.FSM_State('insert point', 'can enter')
    def spline_insert_point_can_enter(self):
        # make sure mouse is over source
        if not self.ray_cast_source_hit(self.actions.mouse): return False
        #and over a spline segment
        hn = self.net_ui_context.hovered_near
        if not hn: return False
        if hn[0] != 'EDGE': return False

        return True

    @CookieCutter.FSM_State('insert point')
    def spline_insert_point(self):
        n = self.insert_spline_point(self.actions.mouse)
        self.net_ui_context.selected = n
        self.tweak_release = 'add point'
        self.tweak_cancel = 'cancel'
        return 'tweak'


    #--------------------------------------
    # add point disconnected

    @CookieCutter.FSM_State('add point (disconnected)', 'can enter')
    def spline_add_point_disconnected_can_enter(self):
        # make sure mouse is over source
        hn = self.net_ui_context.hovered_near
        if hn and hn[0] == 'EDGE': return False

        if not self.ray_cast_source_hit(self.actions.mouse): return False
        return True

    @CookieCutter.FSM_State('add point (disconnected)')
    def spline_add_point_disconnected(self):
        n = self.add_point(self.actions.mouse)
        self.net_ui_context.selected = n
        self.tweak_release = {'add point', 'add point (disconnected)'}
        self.tweak_cancel = 'cancel'
        return 'tweak'



    #--------------------------------------
    # grab
    # TODO: can we not just use tweak?  yes we can just use tweak

    @CookieCutter.FSM_State('grab', 'can enter')
    def spline_grab_can_enter(self):
        return (not self.spline_net.is_empty and self.net_ui_context.selected != None)

    @CookieCutter.FSM_State('grab', 'enter')
    def spline_grab_enter(self):
        self.header_text_set("'MoveMouse' and 'LeftClick' to adjust node location, Right Click to cancel the grab")
        self.grabber.initiate_grab_point()
        self.grabber.move_grab_point(self.context, self.actions.mouse)
        #self.ui_text_update()

    @CookieCutter.FSM_State('grab')
    def spline_grab(self):
        # no navigation in grab mode
        self.cursor_modal_set('HAND')

        if self.actions.pressed('LEFTMOUSE'):
            return 'spline main'

        if self.actions.pressed('cancel'):
            #put it back!
            self.grabber.grab_cancel()
            return 'spline main'

        if self.actions.mousemove:
            self.net_ui_context.update(self.actions.mouse)
            #self.net_ui_context.hover()
            return
        if self.actions.mousemove_prev:
            #update the b_pt location
            self.net_ui_context.update(self.actions.mouse)
            self.net_ui_context.nearest_non_man_loc()
            #self.hover()
            #self.net_ui_context.hover()
            self.grabber.move_grab_point(self.context, self.actions.mouse)

    @CookieCutter.FSM_State('grab', 'exit')
    def spline_grab_exit(self):
        #confirm location
        x,y = self.actions.mouse
        self.grabber.finalize(self.context)

        if isinstance(self.net_ui_context.selected, CurveNode):
            self.spline_net.push_to_input_net(self.net_ui_context, self.input_net)
            self.network_cutter.update_segments_async()
            
            self.create_points_batch()
            self.polytrim_render._gather_data()
    
            tag_redraw_all('update segments')
        else:
            self.network_cutter.update_segments()

        #self.ui_text_update()


    #--------------------------------------
    # sketch

    @CookieCutter.FSM_State('sketch', 'can enter')
    def spline_sketch_can_enter(self):
        # as long as mouse is over source, sketch either starts:
        # 1. from selected endpoint if mouse is near (or hovering) selected
        # 2. from a new, disconnected point

        # make sure mouse is over source
        if not self.ray_cast_source_hit(self.actions.mouse): return False

        s = self.net_ui_context.selected
        n = self.net_ui_context.hovered_near[1] if self.net_ui_context.hovered_near[0] in {'POINT', 'POINT CONNECT'} else None

        # case 1: mouse is near selected endpoint
        if s and s.is_endpoint and n == s: return True

        # case 2
        return True

    @CookieCutter.FSM_State('sketch', 'enter')
    def spline_sketch_enter(self):
        self.sketcher.reset()

        s = self.net_ui_context.selected
        n = self.net_ui_context.hovered_near[1] if self.net_ui_context.hovered_near[0] in {'POINT', 'POINT CONNECT'} else None
        if s and s.is_endpoint and n == s:
            # case 1: mouse is near selected endpoint
            self.sketching_start = s
        else:
            # case 2: start with new disconnected point
            self.sketching_start = self.add_point(self.actions.mouse)
            self.net_ui_context.selected = self.sketching_start
        self.sketcher.add_loc(*self.actions.mouse)

    @CookieCutter.FSM_State('sketch')
    def spline_sketch(self):
        if self.actions.mousemove:
            self.sketcher.smart_add_loc(*self.actions.mouse)
            tag_redraw_all('sktch stroke update')
        if self.actions.released('sketch'):
            return 'spline main'

    @CookieCutter.FSM_State('sketch', 'exit')
    def spline_sketch_exit(self):
        is_sketch = self.sketcher.is_good()
        if is_sketch:
            self.net_ui_context.update(self.actions.mouse)
            self.hover_spline()
            self.sketching_end = self.net_ui_context.hovered_near[1] if self.net_ui_context.hovered_near[0] in {'POINT', 'POINT CONNECT'} else None
            self.sketcher.finalize(self.context, self.sketching_start, self.sketching_end)
            self.spline_net.push_to_input_net(self.net_ui_context, self.input_net)
            self.network_cutter.update_segments_async()
            self.hover_spline()
            new_hovered_point = self.net_ui_context.hovered_near[1] if self.net_ui_context.hovered_near[0] in {'POINT', 'POINT CONNECT'} else None
            if new_hovered_point: self.net_ui_context.selected = new_hovered_point
        #self.ui_text_update()
        self.sketcher.reset()
        self.cache_to_bmesh()
        tag_redraw_all('sketch exit')


    @CookieCutter.FSM_State('seed')
    def modal_seed(self):
        self.cursor_modal_set('EYEDROPPER')

        if self.actions.mousemove_prev:
            #update the bmesh geometry under mouse location
            self.net_ui_context.update(self.actions.mouse)

        if self.actions.pressed('LEFTMOUSE'):
            #place seed on surface
            #background watershed form the seed to color the region on the mesh
            self.click_add_seed()
            self.network_cutter.update_spline_edited_patches(self.spline_net)
        #if right click
            #remove the seed
            #remove any "patch" data associated with the seed



    @CookieCutter.FSM_State('seed', 'can enter')
    def seed_can_enter(self):
        print('seed can enter')
        # enter seed mode iff there is at least one cycle
        ip_cyc, seg_cyc = self.input_net.find_network_cycles()
        return len(ip_cyc) > 0

    @CookieCutter.FSM_State('seed', 'enter')
    def seed_enter(self):
        print('seed enter!')
        if self.network_cutter.knife_complete:
            self.network_cutter.find_perimeter_edges()
        else:
            self.network_cutter.find_boundary_faces_cycles()
            print('found boundary face cycles!')
        
        tag_redraw_all('seed enter')
        
        #self.seed_fsm.reset()
        #self.ui_text_update()

    @CookieCutter.FSM_State('seed', 'exit')
    def seed_exit(self):
        pass
        #self.seed_fsm.reset()
        #self.ui_text_update()
        # if not self.network_cutter.knife_complete:
        #    #assoccates SplineNetwork and InputNetwork elements with patches
        #     self.network_cutter.update_spline_edited_patches(self.spline_net)

    ######################################################
    # segmentation state

    @CookieCutter.FSM_State('segmentation')
    def modal_segmentation(self):
        self.cursor_modal_set('CROSSHAIR')

        if self.actions.pressed('redraw'):
            self.create_points_batch()
            self.polytrim_render._gather_data()
            tag_redraw_all('delete point')
            
        
        if self.actions.mousemove_prev:
            #update the bmesh geometry under mouse location
            self.net_ui_context.update(self.actions.mouse)
            self.hover_patches()
            #print(self.net_ui_context.hovered_near)

        if self.actions.pressed('LEFTMOUSE'):
            #place seed on surface
            #background watershed form the seed to color the region on the mesh
            print(self.net_ui_context.hovered_near)
            if self.net_ui_context.hovered_near[1]:
                self.network_cutter.active_patch = self.net_ui_context.hovered_near[1]
                self.polytrim_render._gather_data()


        #if right click
            #remove the seed
            #remove any "patch" data associated with the seed

    #Segmentation State (Delete, Split,Duplicate)
    @CookieCutter.FSM_State('segmentation', 'can enter')
    def segmentation_can_enter(self):
        return True
        #return self.network_cutter.knife_complete??

    @CookieCutter.FSM_State('segmentation', 'enter')
    def segmentation_enter(self):
        if not self.network_cutter.knife_complete:
            self.network_cutter.knife_geometry4()
            self.network_cutter.find_perimeter_edges()
            for patch in self.network_cutter.face_patches:
                patch.grow_seed(self.input_net.bme, self.network_cutter.boundary_edges)
                patch.color_patch()
                self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
                self.net_ui_context.ob.data.update()
        self.polytrim_render._gather_data()
        tag_redraw_all('segmentation enter')
        
        #self.ui_text_update()

   

    ######################################################
    # region painting

    @CookieCutter.FSM_State('region main', 'enter')
    def region_main_enter(self):
        self.brush = self.PaintBrush(self.net_ui_context, radius=self.brush_radius)
        #self.ui_text_update()

    @CookieCutter.FSM_State('region main')
    def region_main(self):
        self.cursor_modal_set('PAINT_BRUSH')

        if self.actions.mousemove_prev:
            #update the bmesh geometry under mouse location
            self.net_ui_context.update(self.actions.mouse)

        if self.actions.pressed('LEFTMOUSE'):
            #start painting
            return 'paint'

        if self.actions.pressed('RIGHTMOUSE'):
            return 'paint delete'


    @CookieCutter.FSM_State('paint', 'can enter')
    def region_paint_can_enter(self):
        #any time really, may require a BVH update if
        #network cutter has been executed
        return True

    @CookieCutter.FSM_State('paint', 'enter')
    def region_paint_enter(self):
        #set the cursor to to something
        self.network_cutter.find_boundary_faces_cycles()
        self.click_enter_paint()
        self.last_loc = None
        self.last_update = 0
        self.paint_dirty = False

    @CookieCutter.FSM_State('paint')
    def region_paint(self):
        self.cursor_modal_set('PAINT_BRUSH')

        if self.actions.released('LEFTMOUSE'):
            return 'region main'

        loc,_,_ = self.brush.ray_hit(self.actions.mouse, self.context)
        if loc and (not self.last_loc or (self.last_loc - loc).length > self.brush.radius*(0.25)):
            self.last_loc = loc
            #update the bmesh geometry under mouse location
            #use brush radius to find all geometry within
            #add that geometry to the "stroke region"
            #color it as the "interim" strokeregion color
            self.brush.absorb_geom_geodesic(self.context, self.actions.mouse)
            #self.brush.absorb_geom(self.context, self.actions.mouse)
            self.paint_dirty = True

        if self.paint_dirty and (time.time() - self.last_update) > 0.2:
            self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
            self.paint_dirty = False
            self.last_update = time.time()

    @CookieCutter.FSM_State('paint', 'exit')
    def region_paint_exit(self):
        self.brush.absorb_geom_geodesic(self.context, self.actions.mouse)
        self.paint_confirm_mergey()
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)


    @CookieCutter.FSM_State('paint delete', 'enter')
    def region_unpaint_enter(self):
        #set the cursor to to something
        self.network_cutter.find_boundary_faces_cycles()
        self.click_enter_paint(delete = True)
        self.last_loc = None
        self.last_update = 0
        self.paint_dirty = False

    @CookieCutter.FSM_State('paint delete')
    def region_unpaint(self):
        self.cursor_modal_set('PAINT_BRUSH')

        if self.actions.released('RIGHTMOUSE'):
            return 'region main'

        loc,_,_ = self.brush.ray_hit(self.actions.mouse, self.context)
        if loc and (not self.last_loc or (self.last_loc - loc).length > self.brush.radius*(0.25)):
            self.last_loc = loc
            #update the bmesh geometry under mouse location
            #use brush radius to find all geometry within
            #add that geometry to the "stroke region"
            #color it as the "interim" strokeregion color
            self.brush.absorb_geom_geodesic(self.context, self.actions.mouse)
            #self.brush.absorb_geom(self.context, self.actions.mouse)
            self.paint_dirty = True

        if self.paint_dirty and (time.time() - self.last_update) > 0.2:
            self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
            self.paint_dirty = False
            self.last_update = time.time()

    @CookieCutter.FSM_State('paint delete', 'exit')
    def region_unpaint_exit(self):
        self.brush.absorb_geom_geodesic(self.context, self.actions.mouse)
        self.paint_confirm_subtract()
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
    
    
'''    
class Polytrim_States():
    # spline, seed, and region are tools with their own states
    spline_fsm = FSM()
    seed_fsm   = FSM()
    region_fsm = FSM()
    segmentation_fsm = FSM()

    def fsm_setup(self):
        # let each fsm know that self should be passed to every fsm state call and transition (main, enter, exit, etc.)
        self.spline_fsm.set_call_args(self)
        self.seed_fsm.set_call_args(self)
        self.region_fsm.set_call_args(self)
        self.segmentation_fsm.set_call_args(self)

    def common(self, fsm):
        # this fn contains common actions for all states

        # test code that will break operator :)
        #if self.actions.pressed('F9'): bad = 3.14 / 0
        #if self.actions.pressed('F10'): assert False

        if fsm.state == 'main':
            # only handle these common actions if we are in the main state of the tool

            if self.actions.pressed('S'): return 'seed'
            if self.actions.pressed('P'): return 'region'

            if self.actions.pressed('RET'):
                self.done()
                return

            if self.actions.pressed('ESC'):
                self.done(cancel=True)
                return
                
            if self.actions.pressed('ESC'):
                return 'cancel'

        # call the currently selected tool
        fsm.update()


    @CookieCutter.FSM_State('main')
    def main(self):
        return 'spline'

    @CookieCutter.FSM_State('spline', 'enter')
    def spline_enter(self):
        self.spline_fsm.reset()

    @CookieCutter.FSM_State('spline', 'exit')
    def spline_exit(self):
        #maybe this needs to happen on paint enter...yes?
        self.spline_fsm.reset()

    @CookieCutter.FSM_State('spline')
    def spline(self):
        return self.common(self.spline_fsm)

    @CookieCutter.FSM_State('spline', 'can exit')
    def spline_can_exit(self):
        # exit spline mode iff cut network has finished and there are no bad segments
        c1 = not any([seg.is_bad for seg in self.input_net.segments])
        if not c1:
            self.hint_bad = True
        else:
            self.hint_bad = False
        c2 = all([seg.calculation_complete for seg in self.input_net.segments])
        return c1 and c2


    @CookieCutter.FSM_State('seed', 'can enter')
    def seed_can_enter(self):
        # enter seed mode iff there is at least one cycle
        ip_cyc, seg_cyc = self.input_net.find_network_cycles()
        return len(ip_cyc) > 0

    @CookieCutter.FSM_State('seed', 'enter')
    def seed_enter(self):
        if self.network_cutter.knife_complete:
            self.network_cutter.find_perimeter_edges()
        else:
            self.network_cutter.find_boundary_faces_cycles()
        self.seed_fsm.reset()
        #self.ui_text_update()

    @CookieCutter.FSM_State('seed', 'exit')
    def seed_exit(self):
        self.seed_fsm.reset()
        #self.ui_text_update()
        # if not self.network_cutter.knife_complete:
        #    #assoccates SplineNetwork and InputNetwork elements with patches
        #     self.network_cutter.update_spline_edited_patches(self.spline_net)

    @CookieCutter.FSM_State('seed')
    def seed(self):
        return self.common(self.seed_fsm)


    #Segmentation State (Delete, Split,Duplicate)
    @CookieCutter.FSM_State('segmentation', 'can enter')
    def segmentation_can_enter(self):
        return True
        #return self.network_cutter.knife_complete

    @CookieCutter.FSM_State('segmentation', 'enter')
    def segmentation_enter(self):
        self.network_cutter.knife_geometry4()
        self.network_cutter.find_perimeter_edges()
        for patch in self.network_cutter.face_patches:
            patch.grow_seed(self.input_net.bme, self.network_cutter.boundary_edges)
            patch.color_patch()
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        self.segmentation_fsm.reset()
        #self.ui_text_update()

    @CookieCutter.FSM_State('segmentation')
    def segmentation(self):
        return self.common(self.segmentation_fsm)


    #Region Painting State
    @CookieCutter.FSM_State('region', 'can enter')
    def region_can_enter(self):
        # exit spline mode iff cut network has finished and there are no bad segments
        c1 = not any([seg.is_bad for seg in self.input_net.segments])

        if not c1:
            self.hint_bad = True
        c2 = all([seg.calculation_complete for seg in self.input_net.segments])
        return c1 and c2

    @CookieCutter.FSM_State('region', 'enter')
    def region_enter(self):
        self.net_ui_context.selected = [None, None]
        self.network_cutter.find_boundary_faces_cycles()
        for patch in self.network_cutter.face_patches:
            patch.grow_seed_faces(self.input_net.bme, self.network_cutter.boundary_faces)
            patch.color_patch()

        self.network_cutter.update_spline_edited_patches(self.spline_net)

        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        self.region_fsm.reset()
        #self.ui_text_update()

    @CookieCutter.FSM_State('region', 'exit')
    def region_exit(self):
        self.paint_exit()
        self.region_fsm.reset()
        #self.ui_text_update()

    @CookieCutter.FSM_State('region')
    def region(self):
        return self.common(self.region_fsm)


    ######################################################
    # spline editing

    @CookieCutter.FSM_State('spline main')
    def spline_main(self):
        self.cursor_modal_set('CROSSHAIR')
        context = self.context

        mouse_just_stopped = self.actions.mousemove_prev and not self.actions.mousemove
        if mouse_just_stopped:
            self.net_ui_context.update(self.actions.mouse)
            #TODO: Bring hover into NetworkUiContext
            self.hover_spline()
            #print(self.net_ui_context.hovered_near)
            #self.net_ui_context.inspect_print()

        if self.actions.pressed('select', unpress=False):
            if self.spline_fsm.can_change('select'):
                self.actions.unpress()
                return 'spline select'

        if self.actions.pressed('connect', unpress=False):
            if self.spline_fsm.can_change('connect'):
                self.actions.unpress()
                return 'spline connect'

        if self.actions.pressed('add point', unpress=False):
            # first try to add a connected point
            # if that fails, try to add a disconnected point
            if self.spline_fsm.can_change('add point'):
                self.actions.unpress()
                return 'add point'
            elif self.spline_fsm.can_change('add point (disconnected)'):
                self.actions.unpress()
                return 'add point (disconnected)'
            elif self.spline_fsm.can_change('insert point'):
                return 'insert point'

        if self.actions.pressed('sketch'):
            return 'sketch'

        if self.actions.pressed('add point (disconnected)'):
            return 'add point (disconnected)'

        if self.actions.pressed('grab'):
            return 'grab'

        if self.actions.pressed('delete'):
            self.click_delete_spline_point(mode='mouse')
            self.net_ui_context.update(self.actions.mouse)

            self.hover_spline()
            #self.ui_text_update()
            return

        if self.actions.pressed('delete (disconnect)'):
            self.click_delete_spline_point('mouse', True)
            self.net_ui_context.update(self.actions.mouse)
            self.hover_spline()
            #self.ui_text_update()
            return


    #--------------------------------------
    # spline select

    @CookieCutter.FSM_State('spline select', 'can enter')
    def spline_select_can_enter(self):
        return self.net_ui_context.hovered_near[0] in {'POINT'}

    @CookieCutter.FSM_State('spline select')
    def spline_select(self):
        self.net_ui_context.selected = self.net_ui_context.hovered_near[1]
        self.tweak_release = 'select'
        self.tweak_cancel = 'cancel'
        return 'tweak'


    #--------------------------------------
    # spline tweak

    @CookieCutter.FSM_State('tweak', 'can enter')
    def spline_tweak_can_enter(self):
        if not self.net_ui_context.selected: return False
        if not hasattr(self, 'tweak_release'): self.tweak_release = None
        if not hasattr(self, 'tweak_press'): self.tweak_press = None
        if not hasattr(self, 'tweak_cancel'): self.tweak_cancel = None
        assert self.tweak_release or self.tweak_press, 'Must set either self.tweak_release or self.tweak_press!'
        return True

    @CookieCutter.FSM_State('tweak', 'enter')
    def spline_tweak_enter(self):
        context = self.context
        loc3d_reg2D = view3d_utils.location_3d_to_region_2d
        self.tweak_point_p2d = loc3d_reg2D(context.region, context.space_data.region_3d, self.net_ui_context.selected.world_loc)
        self.tweak_mousedown = self.actions.mouse
        self.tweak_moving = False
        self.grabber.initiate_grab_point()
        #self.ui_text_update()

    @CookieCutter.FSM_State('tweak')
    def spline_tweak(self):
        if self.tweak_release and self.actions.released(self.tweak_release):
            return 'spline main'
        if self.tweak_press and self.actions.pressed(self.tweak_press):
            return 'spline main'
        if self.tweak_cancel and self.actions.pressed(self.tweak_cancel):
            #put it back!
            self.grabber.grab_cancel()
            return 'spline main'

        if (self.tweak_mousedown - self.actions.mouse).length > 5:
            self.tweak_moving = True

        if self.tweak_moving and self.actions.mousemove:
            p2d = self.tweak_point_p2d + (self.actions.mouse - self.tweak_mousedown)
            self.net_ui_context.update(p2d)
            self.net_ui_context.nearest_non_man_loc()
            self.grabber.move_grab_point(self.context, p2d)

    @CookieCutter.FSM_State('tweak', 'exit')
    def spline_tweak_exit(self):
        #confirm location
        if self.tweak_moving:
            self.grabber.finalize(self.context)
            if isinstance(self.net_ui_context.selected, CurveNode):
                self.spline_net.push_to_input_net(self.net_ui_context, self.input_net)
                self.network_cutter.update_segments_async()
            else:
                self.network_cutter.update_segments()
        #self.ui_text_update()
        self.tweak_press = None
        self.tweak_release = None
        self.tweak_cancel = None


    #--------------------------------------
    # connect (two endpoints)

    @CookieCutter.FSM_State('spline connect', 'can enter')
    def spline_connect_can_enter(self):
        # make sure selected is an endpoint
        s = self.net_ui_context.selected
        if not s or not s.is_endpoint: return False
        # make sure near is an endpoint
        if self.net_ui_context.hovered_near[0] not in {'POINT CONNECT'}: return False
        n = self.net_ui_context.hovered_near[1]
        if not n or not n.is_endpoint: return False  #impose loops condition
        if s == n:
            print('same point')
            return False
        return True

    @CookieCutter.FSM_State('connect')
    def spline_connect(self):
        s = self.net_ui_context.selected
        n = self.net_ui_context.hovered_near[1]
        assert s and n
        self.add_spline(s, n)
        self.net_ui_context.selected = n
        self.tweak_release = 'connect'
        self.tweak_cancel = 'cancel'
        return 'tweak'


    #--------------------------------------
    # add point (connected to selected endpoint)

    @CookieCutter.FSM_State('add point', 'can enter')
    def spline_add_point_can_enter(self):
        # make sure selected is an endpoint
        s = self.net_ui_context.selected
        if not s or not s.is_endpoint: return False

        hn = self.net_ui_context.hovered_near
        if hn and hn[0] == 'EDGE': return False

        # make sure mouse is over source
        if not self.ray_cast_source_hit(self.actions.mouse): return False
        return True

    @CookieCutter.FSM_State('add point')
    def spline_add_point(self):
        s = self.net_ui_context.selected
        n = self.add_point(self.actions.mouse)
        assert s and n
        self.add_spline(s, n)
        self.net_ui_context.selected = n
        self.tweak_release = 'add point'
        self.tweak_cancel = 'cancel'
        return 'tweak'


    #--------------------------------------
    # insert point

    @CookieCutter.FSM_State('insert point', 'can enter')
    def spline_insert_point_can_enter(self):
        # make sure mouse is over source
        if not self.ray_cast_source_hit(self.actions.mouse): return False
        #and over a spline segment
        hn = self.net_ui_context.hovered_near
        if not hn: return False
        if hn[0] != 'EDGE': return False

        return True

    @CookieCutter.FSM_State('insert point')
    def spline_insert_point(self):
        n = self.insert_spline_point(self.actions.mouse)
        self.net_ui_context.selected = n
        self.tweak_release = 'add point'
        self.tweak_cancel = 'cancel'
        return 'tweak'


    #--------------------------------------
    # add point disconnected

    @CookieCutter.FSM_State('add point (disconnected)', 'can enter')
    def spline_add_point_disconnected_can_enter(self):
        # make sure mouse is over source
        hn = self.net_ui_context.hovered_near
        if hn and hn[0] == 'EDGE': return False

        if not self.ray_cast_source_hit(self.actions.mouse): return False
        return True

    @CookieCutter.FSM_State('add point (disconnected)')
    def spline_add_point_disconnected(self):
        n = self.add_point(self.actions.mouse)
        self.net_ui_context.selected = n
        self.tweak_release = {'add point', 'add point (disconnected)'}
        self.tweak_cancel = 'cancel'
        return 'tweak'



    #--------------------------------------
    # grab
    # TODO: can we not just use tweak?  yes we can just use tweak

    @CookieCutter.FSM_State('grab', 'can enter')
    def spline_grab_can_enter(self):
        return (not self.spline_net.is_empty and self.net_ui_context.selected != None)

    @CookieCutter.FSM_State('grab', 'enter')
    def spline_grab_enter(self):
        self.header_text_set("'MoveMouse' and 'LeftClick' to adjust node location, Right Click to cancel the grab")
        self.grabber.initiate_grab_point()
        self.grabber.move_grab_point(self.context, self.actions.mouse)
        #self.ui_text_update()

    @CookieCutter.FSM_State('grab')
    def spline_grab(self):
        # no navigation in grab mode
        self.cursor_modal_set('HAND')

        if self.actions.pressed('LEFTMOUSE'):
            return 'spline main'

        if self.actions.pressed('cancel'):
            #put it back!
            self.grabber.grab_cancel()
            return 'spline main'

        if self.actions.mousemove:
            self.net_ui_context.update(self.actions.mouse)
            #self.net_ui_context.hover()
            return
        if self.actions.mousemove_prev:
            #update the b_pt location
            self.net_ui_context.update(self.actions.mouse)
            self.net_ui_context.nearest_non_man_loc()
            #self.hover()
            #self.net_ui_context.hover()
            self.grabber.move_grab_point(self.context, self.actions.mouse)

    @CookieCutter.FSM_State('grab', 'exit')
    def spline_grab_exit(self):
        #confirm location
        x,y = self.actions.mouse
        self.grabber.finalize(self.context)

        if isinstance(self.net_ui_context.selected, CurveNode):
            self.spline_net.push_to_input_net(self.net_ui_context, self.input_net)
            self.network_cutter.update_segments_async()
        else:
            self.network_cutter.update_segments()

        #self.ui_text_update()


    #--------------------------------------
    # sketch

    @CookieCutter.FSM_State('sketch', 'can enter')
    def spline_sketch_can_enter(self):
        # as long as mouse is over source, sketch either starts:
        # 1. from selected endpoint if mouse is near (or hovering) selected
        # 2. from a new, disconnected point

        # make sure mouse is over source
        if not self.ray_cast_source_hit(self.actions.mouse): return False

        s = self.net_ui_context.selected
        n = self.net_ui_context.hovered_near[1] if self.net_ui_context.hovered_near[0] in {'POINT', 'POINT CONNECT'} else None

        # case 1: mouse is near selected endpoint
        if s and s.is_endpoint and n == s: return True

        # case 2
        return True

    @CookieCutter.FSM_State('sketch', 'enter')
    def spline_sketch_enter(self):
        self.sketcher.reset()

        s = self.net_ui_context.selected
        n = self.net_ui_context.hovered_near[1] if self.net_ui_context.hovered_near[0] in {'POINT', 'POINT CONNECT'} else None
        if s and s.is_endpoint and n == s:
            # case 1: mouse is near selected endpoint
            self.sketching_start = s
        else:
            # case 2: start with new disconnected point
            self.sketching_start = self.add_point(self.actions.mouse)
            self.net_ui_context.selected = self.sketching_start
        self.sketcher.add_loc(*self.actions.mouse)

    @CookieCutter.FSM_State('sketch')
    def spline_sketch(self):
        if self.actions.mousemove:
            self.sketcher.smart_add_loc(*self.actions.mouse)
        if self.actions.released('sketch'):
            return 'spline main'

    @CookieCutter.FSM_State('sketch', 'exit')
    def spline_sketch_exit(self):
        is_sketch = self.sketcher.is_good()
        if is_sketch:
            self.net_ui_context.update(self.actions.mouse)
            self.hover_spline()
            self.sketching_end = self.net_ui_context.hovered_near[1] if self.net_ui_context.hovered_near[0] in {'POINT', 'POINT CONNECT'} else None
            self.sketcher.finalize(self.context, self.sketching_start, self.sketching_end)
            self.spline_net.push_to_input_net(self.net_ui_context, self.input_net)
            self.network_cutter.update_segments_async()
            self.hover_spline()
            new_hovered_point = self.net_ui_context.hovered_near[1] if self.net_ui_context.hovered_near[0] in {'POINT', 'POINT CONNECT'} else None
            if new_hovered_point: self.net_ui_context.selected = new_hovered_point
        #self.ui_text_update()
        self.sketcher.reset()


    @CookieCutter.FSM_State('main')
    def modal_seed(self):
        self.cursor_modal_set('EYEDROPPER')

        if self.actions.mousemove_prev:
            #update the bmesh geometry under mouse location
            self.net_ui_context.update(self.actions.mouse)

        if self.actions.pressed('LEFTMOUSE'):
            #place seed on surface
            #background watershed form the seed to color the region on the mesh
            self.click_add_seed()
            self.network_cutter.update_spline_edited_patches(self.spline_net)
        #if right click
            #remove the seed
            #remove any "patch" data associated with the seed



    ######################################################
    # segmentation state

    @CookieCutter.FSM_State('main')
    def modal_segmentation(self):
        self.cursor_modal_set('CROSSHAIR')

        if self.actions.mousemove_prev:
            #update the bmesh geometry under mouse location
            self.net_ui_context.update(self.actions.mouse)
            self.hover_patches()
            #print(self.net_ui_context.hovered_near)

        if self.actions.pressed('LEFTMOUSE'):
            #place seed on surface
            #background watershed form the seed to color the region on the mesh
            print(self.net_ui_context.hovered_near)
            if self.net_ui_context.hovered_near[1]:
                self.network_cutter.active_patch = self.net_ui_context.hovered_near[1]


        #if right click
            #remove the seed
            #remove any "patch" data associated with the seed



    ######################################################
    # region painting

    @CookieCutter.FSM_State('region main', 'enter')
    def region_main_enter(self):
        self.brush = self.PaintBrush(self.net_ui_context, radius=self.brush_radius)
        #self.ui_text_update()

    @CookieCutter.FSM_State('region main')
    def region_main(self):
        self.cursor_modal_set('PAINT_BRUSH')

        if self.actions.mousemove_prev:
            #update the bmesh geometry under mouse location
            self.net_ui_context.update(self.actions.mouse)

        if self.actions.pressed('LEFTMOUSE'):
            #start painting
            return 'paint'

        if self.actions.pressed('RIGHTMOUSE'):
            return 'paint delete'


    @CookieCutter.FSM_State('paint', 'can enter')
    def region_paint_can_enter(self):
        #any time really, may require a BVH update if
        #network cutter has been executed
        return True

    @CookieCutter.FSM_State('paint', 'enter')
    def region_paint_enter(self):
        #set the cursor to to something
        self.network_cutter.find_boundary_faces_cycles()
        self.click_enter_paint()
        self.last_loc = None
        self.last_update = 0
        self.paint_dirty = False

    @CookieCutter.FSM_State('paint')
    def region_paint(self):
        self.cursor_modal_set('PAINT_BRUSH')

        if self.actions.released('LEFTMOUSE'):
            return 'region main'

        loc,_,_ = self.brush.ray_hit(self.actions.mouse, self.context)
        if loc and (not self.last_loc or (self.last_loc - loc).length > self.brush.radius*(0.25)):
            self.last_loc = loc
            #update the bmesh geometry under mouse location
            #use brush radius to find all geometry within
            #add that geometry to the "stroke region"
            #color it as the "interim" strokeregion color
            self.brush.absorb_geom_geodesic(self.context, self.actions.mouse)
            #self.brush.absorb_geom(self.context, self.actions.mouse)
            self.paint_dirty = True

        if self.paint_dirty and (time.time() - self.last_update) > 0.2:
            self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
            self.paint_dirty = False
            self.last_update = time.time()

    @CookieCutter.FSM_State('paint', 'exit')
    def region_paint_exit(self):
        self.brush.absorb_geom_geodesic(self.context, self.actions.mouse)
        self.paint_confirm_mergey()
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)


    @CookieCutter.FSM_State('paint delete', 'enter')
    def region_unpaint_enter(self):
        #set the cursor to to something
        self.network_cutter.find_boundary_faces_cycles()
        self.click_enter_paint(delete = True)
        self.last_loc = None
        self.last_update = 0
        self.paint_dirty = False

    @CookieCutter.FSM_State('paint delete')
    def region_unpaint(self):
        self.cursor_modal_set('PAINT_BRUSH')

        if self.actions.released('RIGHTMOUSE'):
            return 'region main'

        loc,_,_ = self.brush.ray_hit(self.actions.mouse, self.context)
        if loc and (not self.last_loc or (self.last_loc - loc).length > self.brush.radius*(0.25)):
            self.last_loc = loc
            #update the bmesh geometry under mouse location
            #use brush radius to find all geometry within
            #add that geometry to the "stroke region"
            #color it as the "interim" strokeregion color
            self.brush.absorb_geom_geodesic(self.context, self.actions.mouse)
            #self.brush.absorb_geom(self.context, self.actions.mouse)
            self.paint_dirty = True

        if self.paint_dirty and (time.time() - self.last_update) > 0.2:
            self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
            self.paint_dirty = False
            self.last_update = time.time()

    @CookieCutter.FSM_State('paint delete', 'exit')
    def region_unpaint_exit(self):
        self.brush.absorb_geom_geodesic(self.context, self.actions.mouse)
        self.paint_confirm_subtract()
        self.net_ui_context.bme.to_mesh(self.net_ui_context.ob.data)
        
'''
