
'''
Copyright (C) 2019 CG Cookie
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

import sys
import math
import copy
import json
import time
import random



import bpy
import bgl
import bmesh
from bmesh.types import BMesh, BMVert, BMEdge, BMFace
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from mathutils import Matrix, Vector
from mathutils.geometry import normal as compute_normal, intersect_point_tri
from ..subtrees.addon_common.common.globals import Globals
from ..subtrees.addon_common.common.debug import dprint, Debugger
from ..subtrees.addon_common.common.profiler import profiler
from ..subtrees.addon_common.common.maths import Point, Direction, Normal, Frame
from ..subtrees.addon_common.common.maths import Point2D, Vec2D, Direction2D
from ..subtrees.addon_common.common.maths import Ray, XForm, BBox, Plane
from ..subtrees.addon_common.common.ui import Drawing
from ..subtrees.addon_common.common.utils import min_index
from ..subtrees.addon_common.common.hasher import hash_object, hash_bmesh
from ..subtrees.addon_common.common.decorators import stats_wrapper
from ..subtrees.addon_common.common import bmesh_render as bmegl
from ..subtrees.addon_common.common.bmesh_render import triangulateFace, BufferedRender_Batch

from ..subtrees.addon_common.common.colors import get_random_color, colorname_to_color
from ntpath import commonpath



 # visualization settings
#'target vert size':         4.0,
#'target edge size':         2.0,
#'target alpha':             1.0,
#'target hidden alpha':      0.1,
#'target alpha backface':    0.2,
#'target cull backfaces':    False,



color_mesh = colorname_to_color['indigo']
color_select = colorname_to_color['darkorange']
edge_size = 2.0
vert_size = 8.0
normal_offset_multiplier = 1.0
constrain_offset = True

opts = {
            'poly color':                  (*color_mesh[:3],   0.20),
            'poly color selected':         (*color_select[:3], 0.20),
            'poly offset':                 0.000010,
            'poly dotoffset':              1.0,
            'poly mirror color':           (*color_mesh[:3],   0.10),
            'poly mirror color selected':  (*color_select[:3], 0.10),
            'poly mirror offset':          0.000010,
            'poly mirror dotoffset':       1.0,

            'line color':                  (*color_mesh[:3],   1.00),
            'line color selected':         (*color_select[:3], 1.00),
            'line width':                  edge_size,
            'line offset':                 0.000012,
            'line dotoffset':              1.0,
            'line mirror stipple':         False,
            'line mirror color':           (*color_mesh[:3],   0.25),
            'line mirror color selected':  (*color_select[:3], 0.25),
            'line mirror width':           1.5,
            'line mirror offset':          0.000012,
            'line mirror dotoffset':       1.0,
            'line mirror stipple':         False,

            'point color':                 (*color_mesh[:3],   1.00),
            'point color selected':        (*color_select[:3], 1.00),
            'point color highlight':       (1.0, 1.0, 0.1, 1.0),
            'point size':                  vert_size,
            'point size highlight':        10.0,
            'point offset':                0.000015,
            'point dotoffset':             1.0,
            'point mirror color':          (*color_mesh[:3],   0.25),
            'point mirror color selected': (*color_select[:3], 0.25),
            'point mirror size':           3.0,
            'point mirror offset':         0.000015,
            'point mirror dotoffset':      1.0,

            'focus mult':                  1.0,
            'normal offset':               0.001 * normal_offset_multiplier,    # pushes vertices out along normal
            'constrain offset':            constrain_offset,
        }

class SplineNetworkRender():
    '''
    CurveNetworkRender handles rendering of the SplineNetwork.
    '''

    #what are all the opsts?
    
    def __init__(self, spline_network, network_cutter, opts):
        
        self.load_verts = True #opts.get('load verts', True)
        self.load_edges = True #opts.get('load edges', True)
        self.load_faces = False #opts.get('load faces', True)

        self.buf_matrix_model = spline_network.xform.to_bglMatrix_Model()
        self.buf_matrix_inverse = spline_network.xform.to_bglMatrix_Inverse()
        self.buf_matrix_normal = spline_network.xform.to_bglMatrix_Normal()
        self.buffered_renders = []
        self.drawing = Globals.drawing

        self.spline_network = spline_network
        self.network_cutter = network_cutter
        #self.replace_rfmesh(rfmesh)
        self.replace_opts(opts)

    def __del__(self):
        if hasattr(self, 'buf_matrix_model'):
            del self.buf_matrix_model
        if hasattr(self, 'buf_matrix_inverse'):
            del self.buf_matrix_inverse
        if hasattr(self, 'buf_matrix_normal'):
            del self.buf_matrix_normal
        if hasattr(self, 'buffered_renders'):
            del self.buffered_renders

    #@profiler.function
    def replace_opts(self, opts):
        self.opts = opts
        self.opts['dpi mult'] = self.drawing.get_dpi_mult()
        #self.rfmesh_version = None

    #@profiler.function
    def replace_rfmesh(self, rfmesh):
        self.rfmesh = rfmesh
        self.bmesh = rfmesh.bme
        #self.rfmesh_version = None

    #@profiler.function
    def add_buffered_render(self, bgl_type, data):
        batch = BufferedRender_Batch(bgl_type)
        batch.buffer(data['vco'], data['vno'], data['sel'])
        self.buffered_renders.append(batch)
        # buffered_render = BGLBufferedRender(bgl_type)
        # buffered_render.buffer(data['vco'], data['vno'], data['sel'], data['idx'])
        # self.buffered_renders.append(buffered_render)

    #@profiler.function
    def _gather_data(self):
        
        #print('gathering data')
        self.buffered_renders = []  #TODO, smart update only the buffers that need it

        
        
        def gather():
            vert_count = 100000
            edge_count = 50000
            face_count = 10000

            '''
            IMPORTANT NOTE: DO NOT USE PROFILER INSIDE THIS FUNCTION IF LOADING ASYNCHRONOUSLY!
            '''
            def sel(g):
                return 1.0 if g.select else 0.0

            def sel_node(node):
                
                return 1.0 if node == self.spline_network.net_ui_context.selected else 0.0
                
            try:
                time_start = time.time()
           

                # NOTE: duplicating data rather than using indexing, otherwise
                # selection will bleed
                #pr = profiler.start('gathering', enabled=not self.async_load)
                
                if self.network_cutter.knife_complete:
                    print('Knife complete ')
                    for fp in self.network_cutter.face_patches:
                        if fp == self.network_cutter.active_patch:
                            sel_val = 1.0
                        else:
                            sel_val = 0.0
                        
                        mx= self.spline_network.xform.mx_p
                        mx_n = self.spline_network.xform.mx_n
                        
                        print(len(fp.boundary_edges))
                        for ed in fp.boundary_edges:
                            
                            vpath = [mx @ v.co for v in ed.verts]
                            npath = [mx_n @ v.normal for v in ed.verts]
                            edge_data = {
                                            'vco': [
                                                tuple(v)
                                                for v in vpath #seg.draw_tessellation
                                            ],
                                            'vno': [
                                                tuple(no)
                                                for no in npath
                                            ],
                                            'sel': [
                                                sel_val
                                                for v in vpath
                                            ],
                                            'idx': None,  # list(range(len(self.bmesh.edges)*2)),
                                            }
                
                            #make a buffer per segment
                            try:
                                self.add_buffered_render(bgl.GL_LINES, edge_data)
                            except:
                                print('failed to add edge data')
                                print((len(edge_data['vco']), len(edge_data['vno']), len(edge_data['sel'])))
                                
                                
                else:  #if True  #why if True?
                    if False:  #self.load_faces
                        tri_faces = [(bmf, list(bmvs))
                                     for bmf in self.bmesh.faces
                                     for bmvs in triangulateFace(bmf.verts)
                                     ]
                        l = len(tri_faces)
                        for i0 in range(0, l, face_count):
                            i1 = min(l, i0 + face_count)
                            face_data = {
                                'vco': [
                                    tuple(bmv.co)
                                    for bmf, verts in tri_faces[i0:i1]
                                    for bmv in verts
                                ],
                                'vno': [
                                    tuple(bmv.normal)
                                    for bmf, verts in tri_faces[i0:i1]
                                    for bmv in verts
                                ],
                                'sel': [
                                    sel(bmf)
                                    for bmf, verts in tri_faces[i0:i1]
                                    for bmv in verts
                                ],
                                'idx': None,  # list(range(len(tri_faces)*3)),
                            }
                            
                            self.add_buffered_render(bgl.GL_TRIANGLES, face_data)

                    if self.load_edges:
                        print('loading segements')
                        segs = self.spline_network.segments
                        def sel_seg(seg):
                            if seg.bad_segment:
                                return 1.0
                            else:
                                return 0.0
                            
                        for seg in segs:
                            
                            if seg.is_inet_dirty:
                                node0 = seg.n0
                                node1 = seg.n1
                                no = .5 * (node0.normal + node1.normal)
                                
                                
                                
                                if math.fmod(len(seg.draw_tessellation),2) != 0:
                                    vpath = seg.draw_tessellation + [seg.draw_tessellation[-1]]
                                else:
                                    vpath = seg.draw_tessellation    
                                edge_data = {
                                    'vco': [
                                        tuple(v)
                                        for v in vpath #seg.draw_tessellation
                                    ],
                                    'vno': [
                                        tuple(no)
                                        for v in vpath
                                    ],
                                    'sel': [
                                        0.0
                                        for v in vpath
                                    ],
                                    'idx': None,  # list(range(len(self.bmesh.edges)*2)),
                                    }
                               
                                
                                #make a buffer per segment
                                try:
                                    self.add_buffered_render(bgl.GL_LINES, edge_data)
                                except:
                                    print('failed to add edge data')
                                    print((len(edge_data['vco']), len(edge_data['vno']), len(edge_data['sel'])))
                            else:
                                
                                for ip_seg in seg.input_segments:
                                    
                                    print(len(ip_seg.path))
                                    print(ip_seg.bad_segment)
                                    #print(ip_seg in parent.network_cutter.completed_segments)
                                    print(ip_seg.calculation_complete)
                                    #OK!  this line drawing is simulating the path as quads
                                    #So it needs an even number of verts for some reason (I think)
                                    
                                    #bad segment, no path
                                    if ip_seg.bad_segment and not len(ip_seg.path) > 2:
                                        print('Bad segment')
                                        vpath = [ip_seg.ip0.world_loc, ip_seg.ip1.world_loc]
                                        npath = [-ip_seg.ip0.normal, -ip_seg.ip1.normal]
                                        sel = [0.0, 0.0]

                                    #segmnet has been calculated successfully    
                                    elif len(ip_seg.path) >= 2 and not ip_seg.bad_segment and ip_seg.calculation_complete: #ip_seg in parent.network_cutter.completed_segments:
                                        print('good segment')
                                        #draw3d_polyline(seg.path,  green2, 2, view_loc, view_ortho)    
                                        if math.fmod(len(ip_seg.path),2) != 0:
                                            vpath = ip_seg.path + [ip_seg.path[-1]]
                                            npath =  [ip_seg.ip0.normal] + [f.normal for f in ip_seg.face_chain] + [ip_seg.ip1.normal]
                                        else:
                                            vpath = ip_seg.path
                                            npath = [ip_seg.ip0.normal] + [f.normal for f in ip_seg.face_chain]
                                            
                                        sel = [1.0 for v in vpath]  #need a better way to draw stuff
                                    
                                    #not finished calculating    
                                    elif ip_seg.calculation_complete == False:  #not in self.newtork_cutter.compelted_segments?
                                        print('calculation incomplete')
                                        #draw3d_polyline([seg.ip0.world_loc, seg.ip1.world_loc], orange2, 2, view_loc, view_ortho)
                                        vpath = [ip_seg.ip0.world_loc, ip_seg.ip1.world_loc]
                                        npath = [-ip_seg.ip0.normal, -ip_seg.ip1.normal]
                                        sel = [0.5, 0.5]  #no idea if this is allowed.  But would like this to be a different color
                                    
                                    #a segment which has not been completely cut but does have an ip path??
                                    #elif len(ip_seg.path) >= 2 and not ip_seg.bad_segment and ip_seg not in self.network_cutter.completed_segments:
                                        #draw3d_polyline(seg.path,  blue, 2, view_loc, view_ortho)
                                    #    vpath = 
                                    #    npath
                                    #    sel
                                    
                                    
                                    #Not sure what else there is but it seems I'm getting an else
                                    else:
                                        print('other unknown situation!')
                                        #draw3d_polyline([seg.ip0.world_loc, seg.ip1.world_loc], blue2, 2, view_loc, view_ortho)
                                        vpath = [ip_seg.ip0.world_loc, ip_seg.ip1.world_loc]
                                        npath = [-ip_seg.ip0.normal, -ip_seg.ip1.normal]
                                        sel = [1.0, 1.0]
                                    
                                    if len(vpath) != len(npath):
                                        print('Length mismatch problem')
                                        print((len(vpath),len(npath)))
                                        continue
                                    
                                    edge_data = {
                                    'vco': [
                                        tuple(v)
                                        for v in vpath
                                    ],
                                    'vno': [
                                        tuple(v)
                                        for v in npath
                                    ],
                                    'sel': sel, #hack "selected" as a way to show good segments?
                                    'idx': None,  # list(range(len(self.bmesh.edges)*2)),
                                    }
                                
                                    
                                    
                                    print((len(edge_data['vco']), len(edge_data['vno'])))
                                    self.add_buffered_render(bgl.GL_LINES, edge_data)

                    if self.load_verts:
                        verts = self.spline_network.points
                        l = len(verts)
                        for i0 in range(0, l, vert_count):
                            i1 = min(l, i0 + vert_count)
                            vert_data = {
                                'vco': [tuple(node.world_loc) for node in verts[i0:i1]],
                                'vno': [tuple(node.normal) for node in verts[i0:i1]],
                                'sel': [sel_node(bmv) for bmv in verts[i0:i1]],
                                'idx': None,  # list(range(len(self.bmesh.verts))),
                            }
                            
                            self.add_buffered_render(bgl.GL_POINTS, vert_data)

                time_end = time.time()
                # print('RFMeshRender: Gather time: %0.2f' % (time_end - time_start))

            except Exception as e:
                print('EXCEPTION WHILE GATHERING: ' + str(e))
                raise e

        self._is_loading = True
        self._is_loaded = False

        #pr = profiler.start('Gathering data for RFMesh (%ssync)' % ('a' if self.async_load else ''))
        gather()
        


    
    def clean(self):  #used to only reload if mesh has changed,
        
        return
    
        #while not self.buf_data_queue.empty():
        #    data = self.buf_data_queue.get()
        #    if data == 'done':
        #        self._is_loading = False
        #        self._is_loaded = True
        #        self.async_load = False
        #    else:
        #        self.add_buffered_render(*data)

        #try:
            # return if rfmesh hasn't changed
        #    self.rfmesh.clean()
        #    ver = self.rfmesh.get_version() if not self.always_dirty else None
        #    if self.rfmesh_version == ver:
        #        profiler.add_note('--> is clean')
        #        return
            # profiler.add_note(
            #     '--> versions: "%s",
            #     "%s"' % (str(self.rfmesh_version),
            #     str(ver))
            # )
            # make not dirty first in case bad things happen while drawing
        #    self.rfmesh_version = ver
        #    self._gather_data()
        #except:
        #    Debugger.print_exception()
        #    profiler.add_note('--> exception')
        #    pass

        #profiler.add_note('--> passed through')


    def draw(
        self,
        view_forward, unit_scaling_factor,
        buf_matrix_target, buf_matrix_target_inv,
        buf_matrix_view, buf_matrix_view_invtrans,
        buf_matrix_proj,
        alpha_above, alpha_below,
        cull_backfaces, alpha_backface,
        symmetry=None, symmetry_view=None,
        symmetry_effect=0.0, symmetry_frame: Frame=None
    ):
        self.clean()
        if not self.buffered_renders: return

        try:
            bgl.glDepthMask(bgl.GL_FALSE)       # do not overwrite the depth buffer

            opts = dict(self.opts)

            opts['matrix model'] = self.spline_network.xform.mx_p
            opts['matrix normal'] = self.spline_network.xform.mx_n
            opts['matrix target'] = buf_matrix_target
            opts['matrix target inverse'] = buf_matrix_target_inv
            opts['matrix view'] = buf_matrix_view
            opts['matrix view normal'] = buf_matrix_view_invtrans
            opts['matrix projection'] = buf_matrix_proj
            opts['forward direction'] = view_forward
            opts['unit scaling factor'] = unit_scaling_factor

            opts['symmetry'] = symmetry
            opts['symmetry frame'] = symmetry_frame
            opts['symmetry view'] = symmetry_view
            opts['symmetry effect'] = symmetry_effect

            bmegl.glSetDefaultOptions()

            opts['cull backfaces'] = cull_backfaces
            opts['alpha backface'] = alpha_backface
            opts['dpi mult'] = self.drawing.get_dpi_mult()
            mirror_axes = [] #self.spline_network.mirror_mod.xyz if self.spline_network.mirror_mod else []
            for axis in mirror_axes: opts['mirror %s' % axis] = True

            #pr = profiler.start('geometry above')
            if True:
                bgl.glDepthFunc(bgl.GL_LEQUAL)
                opts['poly hidden']         = 1 - alpha_above
                opts['poly mirror hidden']  = 1 - alpha_above
                opts['line hidden']         = 1 - alpha_above
                opts['line mirror hidden']  = 1 - alpha_above
                opts['point hidden']        = 1 - alpha_above
                opts['point mirror hidden'] = 1 - alpha_above
                for buffered_render in self.buffered_renders:
                    buffered_render.draw(opts)

            if not opts.get('no below', False):
                # draw geometry hidden behind
                #pr = profiler.start('geometry below')
                if True:
                    bgl.glDepthFunc(bgl.GL_GREATER)
                    opts['poly hidden']         = 1 - alpha_below
                    opts['poly mirror hidden']  = 1 - alpha_below
                    opts['line hidden']         = 1 - alpha_below
                    opts['line mirror hidden']  = 1 - alpha_below
                    opts['point hidden']        = 1 - alpha_below
                    opts['point mirror hidden'] = 1 - alpha_below
                    for buffered_render in self.buffered_renders:
                        buffered_render.draw(opts)
                #pr.done()

            bgl.glDepthFunc(bgl.GL_LEQUAL)
            bgl.glDepthMask(bgl.GL_TRUE)
            bgl.glDepthRange(0, 1)
        except:
            #print('Exception Exception')
            Debugger.print_exception()
            pass