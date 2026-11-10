"""Advanced Fluid Buffer -- complete Blender 4.x / 5.x procedural generator.
Centimetres, +X front, Z up. Clears the scene and calls export_all_fbx().
Original port treatment informed by the user's two vanilla coupling screenshots:
deep dark socket, broad metal lip, axial ribs, guard plates and recessed bolts.
This builds an original mesh, not a reproduction of a vanilla asset.
"""
import bpy
import bmesh
import math
import json
from pathlib import Path
from mathutils import Vector

# 1. DIMENSIONS / QUALITY -- centimetres unless specified -----------------------
# Locked integration contract. Keep these values for the existing UE setup.
FOOTPRINT = 600.0
INTERNAL_FLOOR = 90.0
INTERNAL_TOP = 780.0
LOW_PORT_Z = 175.0
OVERFLOW_FRACTION = 0.75
PORT_FACE_RADIUS = 290.0
# Primary structure.
PLINTH_WIDTH = 520.0
PLINTH_HEIGHT = 65.0
PLINTH_CHAMFER = 5.0
BODY_RADIUS = 210.0
INTERNAL_RADIUS = 190.0
BODY_SEGMENTS = 48
ROOF_Z = 800.0
ROOF_RADIUS = 203.0
ROOF_RIM_RADIUS = 212.0
RIM_CHAMFER = 2.5
FRAME_RING_RADIUS = 224.0
FRAME_RING_HEIGHT = 14.0
FRAME_RING_Z = (292.0, 704.0)
# Every socket dimension can be tuned here. The front opening remains at t=290.
PIPE_INNER_RADIUS_REFERENCE = 65.0
PORT_BORE_RADIUS = 75.0            # 150 cm mouth diameter
PORT_THROAT_RADIUS = 73.0          # 146 cm minimum clear diameter
PORT_FLANGE_RADIUS = 100.0         # 200 cm maximum rim diameter
PORT_FLANGE_THICKNESS = 20.0
PORT_MOUTH_CHAMFER = 4.0
PORT_CONTACT_LIP_WIDTH = 7.0
PORT_BOLT_LEDGE_INNER_RADIUS = 83.0
PORT_PROFILE_SHOULDER_SETBACK = 4.0
PORT_PROFILE_SHOULDER_INSET = 5.0
PORT_BACK_RING_RAISE = 3.0
PORT_BACK_RING_EMBED = 1.0
PORT_BOSS_FRONT_BORE_EXTRA = 5.0
PORT_INTERIOR_WALL = 2.0
PORT_INTERIOR_CAP_THICKNESS = 2.0
PORT_NECK_RADIUS = 93.0
PORT_SLEEVE_BACK = 235.0
PORT_BACK_RING_Z = 245.0           # distance along port axis, not world Z
PORT_BACK_RING_WIDTH = 5.0
PORT_SEGMENTS = 32
PORT_BOLT_COUNT = 12
PORT_BOLT_PITCH_RADIUS = 89.5
PORT_BOLT_HEAD_RADIUS = 5.8
PORT_BOLT_HEAD_DEPTH = 5.0
PORT_BOLT_RECESS = 7.0             # bolt heads end before the face plane
PORT_BOLT_PHASE_DEGREES = 15.0
PORT_BOLT_SEGMENTS = 6
PORT_HOUSING_SEGMENTS = 24
PORT_HOUSING_HALF_WIDTH = 116.0    # tangential dimension
PORT_HOUSING_HALF_HEIGHT = 106.0
PORT_HOUSING_CORNER_CUT = 22.0
PORT_HOUSING_FACE = 242.0
PORT_HOUSING_BEVEL = 5.0
PORT_HOUSING_EMBED = 6.0
PORT_PANEL_CLEARANCE = 6.0
PORT_SHELL_OVERLAP = 8.0
PORT_INTERIOR_CAP_DISTANCE = 194.0
PORT_RIB_ANGLES = (35.0, 62.0, 118.0, 145.0, 215.0, 242.0, 298.0, 325.0)
PORT_RIB_LENGTH = 37.0
PORT_RIB_RADIAL_THICKNESS = 9.0
PORT_RIB_WIDTH = 12.0
PORT_RIB_RADIUS = 100.0
PORT_GUARD_LENGTH = 48.0
PORT_GUARD_RADIUS = 103.0
PORT_GUARD_THICKNESS = 18.0
PORT_GUARD_HEIGHT = 64.0
PORT_DETAIL_CHAMFER = 2.0
PORT_GUARD_ARROW_SIZE = 9.0
PORT_GUARD_ARROW_THICKNESS = 2.8
# Armour: spaced, raised panels produce real inset dark seams.
PANEL_COUNT = 8
PANEL_ROWS = 1
PANEL_START_Z = 304.0
PANEL_END_Z = 698.0
PANEL_ANGLE_GAP = 0.022
PANEL_Z_GAP = 14.0
PANEL_INNER_RADIUS = 212.0
PANEL_OUTER_RADIUS = 219.0
PANEL_CHAMFER = 1.8
PANEL_MIN_HEIGHT = 12.0
PANEL_MIN_ANGLE = 0.035
RIVET_RADIUS = 3.8
RIVET_DEPTH = 4.0
RIVET_Z_INSET = 15.0
RIVET_ANGLE_INSET = 0.035
BOLT_SEGMENTS = 6
# Sight strip moved away from the larger front socket; marker remains at 75%.
WINDOW_ANGLE_MIN = math.radians(-51.0)
WINDOW_ANGLE_MAX = math.radians(-39.0)
WINDOW_BOTTOM = 112.0
WINDOW_TOP = 758.0
GLASS_INNER_RADIUS = 199.0
GLASS_OUTER_RADIUS = 201.0
WINDOW_FRAME_RADIAL_SIZE = 28.0
WINDOW_FRAME_WIDTH = 9.0
WINDOW_FRAME_RADIUS = 208.0
WINDOW_FRAME_CHAMFER = 2.0
WINDOW_BOLT_STEP = 90.0
WINDOW_MARK_OFFSET = 0.018
WINDOW_MARK_RADIUS = 227.0
WINDOW_MARK_STEPS = 20
LIQUID_RADIUS = INTERNAL_RADIUS - 2.0
# Base bracing, rim, corner posts and exported yellow/black band geometry.
CORNER_POST_OFFSET = 211.0
CORNER_POST_WIDTH = 34.0
CORNER_POST_HEIGHT = 82.0
CORNER_POST_CHAMFER = 3.0
GUSSET_ANGLES = (45.0, 135.0, 225.0, 315.0)
GUSSET_INNER_RADIUS = 206.0
GUSSET_OUTER_RADIUS = 269.0
GUSSET_HEIGHT = 100.0
GUSSET_THICKNESS = 14.0
HAZARD_BOTTOM = 22.0
HAZARD_TOP = 40.0
HAZARD_HALF_SPAN = 100.0
HAZARD_PITCH = 39.0
HAZARD_YELLOW_WIDTH = 21.0
HAZARD_SLOPE = 0.85
HAZARD_PROJECTION = 0.5
HAZARD_THICKNESS = 0.7
# Ladder and guard rail.
LADDER_ANGLE = math.radians(180.0)
LADDER_WIDTH = 70.0
# Rung line. Was 250, only ~20 cm off the hull collision (228) and the spines (233): the climbing
# player ended up inside the tank wall. 268 keeps the climber clear of the hull; Scripts/ladder.py
# puts the trigger box's inner face on this line. Must stay below PORT_FACE_RADIUS (290), since
# create_assets.py finds the import mirror from the 75% port being the furthest-out part on X.
LADDER_RADIUS = 268.0
LADDER_RUNG_SPACING = 32.0
LADDER_RAIL_RADIUS = 5.5
LADDER_RUNG_RADIUS = 4.3
LADDER_BOTTOM = 0.0           # past the plinth edge (260) now, so the rails stand on the ground
LADDER_RUNG_COLLISION_DEPTH = 12.0   # radial depth of each rung's collision box
LADDER_TOP = 870.0
LADDER_SEGMENTS = 8
RAIL_TOP = 900.0
RAIL_RADIUS = 178.0
RAIL_TUBE_RADIUS = 5.0
RAIL_LOWER_HEIGHT = 48.0
RAIL_SEGMENTS = 28
RAIL_CROSS_SEGMENTS = 6
RAIL_POST_COUNT = 13
RAIL_GAP_DEGREES = 36.0       # ~110 cm opening at the ladder; 24 was too narrow for the player once the rail got collision
RAIL_COLLISION_THICKNESS = 12.0
# Secondary trim and hardware dimensions.
FLOOR_PLATE_THICKNESS = 10.0
ROOF_RIM_BELOW = 12.0
ROOF_RIM_ABOVE = 5.0
HATCH_XY = (-55.0,30.0)
HATCH_RADIUS = 48.0
HATCH_HEIGHT = 14.0
HATCH_HANDLE_SIZE = (45.0,8.0,8.0)
HATCH_HANDLE_HEIGHT = 21.0
HATCH_SEGMENTS = 24
SMALL_CHAMFER = 2.0
WINDOW_FRAME_END_EXTENSION = 22.0
WINDOW_BOLT_START_OFFSET = 28.0
WINDOW_BOLT_END_INSET = 15.0
WINDOW_BOLT_RADIUS = 3.5
WINDOW_BOLT_BASE_RADIUS = 222.0
WINDOW_BOLT_FACE_RADIUS = 226.0
WINDOW_END_FRAME_INNER_RADIUS = 193.0
WINDOW_END_FRAME_OUTER_RADIUS = 224.0
WINDOW_END_FRAME_HALF_HEIGHT = 7.0
WINDOW_END_FRAME_ANGLE_MARGIN = 0.02
WINDOW_MARK_MAJOR_LENGTH = 25.0
WINDOW_MARK_MINOR_LENGTH = 13.0
WINDOW_MARK_SIZE = (3.0,3.0)
WINDOW_OVERFLOW_MARK_SIZE = (4.0,39.0,8.0)
WINDOW_OVERFLOW_MARK_RAISE = 1.0
CORNER_BOLT_RADIUS = 7.0
CORNER_BOLT_HEIGHT = 5.0
GUSSET_BASE_RAISE = 5.0
GUSSET_TOP_RADIAL_SHIFT = 5.0
PORT_GUARD_FACE_RECESS = 3.0
PORT_ARROW_FACE_RECESS = 2.2
PORT_ARROW_DEPTH = 0.8
PORT_ARROW_HEIGHTS = (-12.0,12.0)
PORT_ARROW_HALF_HEIGHT = 3.0
LADDER_SUPPORT_HEIGHTS = (150.0,400.0,650.0,795.0)
LADDER_SUPPORT_RADIUS = 5.0
LADDER_RUNG_START = 95.0
RAIL_POST_RADIUS = 4.5
MAIN_COLLISION_RADIUS = 228.0
MAIN_COLLISION_SEGMENTS = 24
# Visual redesign: shoulders, vertical load frame and compact service crown.
PLINTH_CORNER_CUT = 62.0
SPINE_ANGLES = (45.0,135.0,225.0)
SPINE_RADIUS = 233.0
SPINE_BOTTOM = 108.0
SPINE_TOP = 792.0
SPINE_SIZE = (22.0,26.0)
SHOULDER_PROFILE = ((196,695),(210,695),(226,718),(232,740),(228,759),(217,780),(205,798),(196,798))
CROWN_INNER_RADIUS = 176.0
CROWN_OUTER_RADIUS = 192.0
CROWN_BOTTOM = 875.0
CROWN_TOP = 893.0
VENT_HEIGHTS = (390.0,425.0,460.0)
VENT_HEIGHT = 5.0
# Mesh/UV/export settings. No automatic preview or render is started.
LOD0_MIN_TRIANGLES = 15000
LOD0_MAX_TRIANGLES = 25000
LOD1_RATIO = 0.50
LOD2_RATIO = 0.20
UV_MARGIN = 0.006
LIGHTMAP_RESOLUTION = 2048
UV_PROJECT_ANGLE_DEGREES = 66.0
FBX_DIRECTORY = str(Path(__file__).resolve().parent / 'Export') if '__file__' in globals() else bpy.path.abspath('//Export')
WRITE_SOCKET_JSON = False
PAINT_PRIMARY = (0.72, 0.24, 0.035)
PAINT_SECONDARY = (0.045, 0.060, 0.070)
METAL_DETAIL_COLOR = (0.22, 0.27, 0.29)
HAZARD_YELLOW = (0.98, 0.66, 0.025)
PORT_INTERIOR_COLOR = (0.008, 0.012, 0.018)

LIQUID_HEIGHT = INTERNAL_TOP - INTERNAL_FLOOR
OVERFLOW_Z = INTERNAL_FLOOR + OVERFLOW_FRACTION * LIQUID_HEIGHT
WINDOW_MID = (WINDOW_ANGLE_MIN + WINDOW_ANGLE_MAX) / 2
PORTS = [
    ('Socket_Port1_Inlet', Vector((0, 1, 0)), LOW_PORT_Z, 90.0),
    ('Socket_Port2_Outlet', Vector((0, -1, 0)), LOW_PORT_Z, -90.0),
    ('Socket_Port3_Overflow', Vector((1, 0, 0)), OVERFLOW_Z, 0.0),
]
assert INTERNAL_FLOOR == 90 and INTERNAL_TOP == 780 and OVERFLOW_Z == 607.5
assert PORT_FACE_RADIUS == 290 and LOW_PORT_Z == 175
assert 70 <= PORT_THROAT_RADIUS <= PORT_BORE_RADIUS < PORT_FLANGE_RADIUS
assert PORT_HOUSING_FACE < PORT_FACE_RADIUS - PORT_FLANGE_THICKNESS
assert PORT_THROAT_RADIUS > PIPE_INNER_RADIUS_REFERENCE
assert INTERNAL_RADIUS < GLASS_INNER_RADIUS < GLASS_OUTER_RADIUS < BODY_RADIUS
assert PLINTH_WIDTH <= FOOTPRINT
assert HAZARD_YELLOW_WIDTH < HAZARD_PITCH
assert PORT_BOLT_PITCH_RADIUS-PORT_BOLT_HEAD_RADIUS>PORT_BOLT_LEDGE_INNER_RADIUS
assert PORT_BOLT_PITCH_RADIUS+PORT_BOLT_HEAD_RADIUS<PORT_FLANGE_RADIUS-PORT_MOUTH_CHAMFER
assert PORT_BORE_RADIUS+PORT_CONTACT_LIP_WIDTH<PORT_BOLT_LEDGE_INNER_RADIUS
assert PORT_BOLT_HEAD_DEPTH<PORT_BOLT_RECESS

# 2. CLEAN SCENE / CENTIMETRE UNITS --------------------------------------------
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
# Include objects hidden by a previous run, avoiding .001 name collisions.
for obj in list(scene_obj for scene_obj in bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for name in ('OverflowTank_Asset','OverflowTank_Collision','OverflowTank_LODs'):
    old_collection = bpy.data.collections.get(name)
    if old_collection: bpy.data.collections.remove(old_collection)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.01
scene.unit_settings.length_unit = 'CENTIMETERS'
scene.cursor.location = (0, 0, 0)
asset_collection = bpy.data.collections.new('OverflowTank_Asset')
scene.collection.children.link(asset_collection)
collision_collection = bpy.data.collections.new('OverflowTank_Collision')
scene.collection.children.link(collision_collection)
lod_collection = bpy.data.collections.new('OverflowTank_LODs')
scene.collection.children.link(lod_collection)

# 3. EXACT MATERIAL SLOT CONTRACT -- NO PROCEDURAL-ONLY STRIPES -----------------
def material(name, rgb, metallic=0.0, roughness=0.4, transmission=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    bs = m.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    out = m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    m.node_tree.links.new(bs.outputs['BSDF'],out.inputs['Surface'])
    bs.inputs['Base Color'].default_value = (*rgb,1)
    bs.inputs['Metallic'].default_value = metallic
    bs.inputs['Roughness'].default_value = roughness
    bs.inputs['Transmission Weight'].default_value = transmission
    bs.inputs['IOR'].default_value = 1.45
    m.diffuse_color = (*rgb,1)
    return m

MAIN_MATERIALS = [
    material('M_Paint_Primary',PAINT_PRIMARY,0.25,0.5),
    material('M_Paint_Secondary',PAINT_SECONDARY,0.55,0.5),
    material('M_Metal_Detail',METAL_DETAIL_COLOR,0.65,0.42),
    material('M_Hazard_Stripe',HAZARD_YELLOW,0.15),
    material('M_Port_Interior',PORT_INTERIOR_COLOR,0.1,0.65),
]
PRIMARY, SECONDARY, METAL, HAZARD, INTERIOR = range(5)
glass_material = material('M_Glass',(0.64,0.85,0.9),0,0.12,1)
liquid_material = material('M_Liquid',(0.015,0.38,0.53),0.1,0.2,0.15)

# 4. CLOSED TRIANGLE PRIMITIVES ------------------------------------------------



def radial(a, r, z):
    return Vector((r * math.cos(a), r * math.sin(a), z))

def basis(axis):
    w = Vector(axis).normalized()
    helper = Vector((0, 0, 1)) if abs(w.z) < 0.9 else Vector((0, 1, 0))
    u = helper.cross(w).normalized()
    return u, w.cross(u).normalized(), w

class MeshBuilder:
    def __init__(self):
        self.verts, self.faces, self.mats, self.smooth = [], [], [], []

    def part(self, verts, faces, mat, smooth=False):
        offset = len(self.verts)
        self.verts.extend(tuple(v) for v in verts)
        for face in faces:
            # Quads are split consistently; no input polygon exceeds 4 vertices.
            triangles = [face] if len(face) == 3 else [face[:3], (face[0], face[2], face[3])]
            for tri in triangles:
                self.faces.append(tuple(offset + i for i in tri))
                self.mats.append(mat)
                self.smooth.append(smooth)

    def box(self, center, size, mat, angle=0):
        c = Vector(center)
        x = Vector((math.cos(angle), math.sin(angle), 0)) * size[0] / 2
        y = Vector((-math.sin(angle), math.cos(angle), 0)) * size[1] / 2
        z = Vector((0, 0, size[2] / 2))
        verts = [c-x-y-z, c+x-y-z, c+x+y-z, c-x+y-z,
                 c-x-y+z, c+x-y+z, c+x+y+z, c-x+y+z]
        self.part(verts, [(0,3,2,1), (4,5,6,7), (0,1,5,4),
                          (1,2,6,5), (2,3,7,6), (3,0,4,7)], mat)

    def cylinder(self, a, b, radius, mat, n=12):
        a, b = Vector(a), Vector(b)
        u, v, w = basis(b-a)
        verts = [p + radius*(u*math.cos(2*math.pi*i/n)+v*math.sin(2*math.pi*i/n))
                 for p in (a,b) for i in range(n)]
        verts += [a,b]
        faces = []
        for i in range(n):
            j = (i+1) % n
            faces += [(i,j,n+j,n+i), (2*n,j,i), (2*n+1,n+i,n+j)]
        self.part(verts, faces, mat, True)
        # End caps stay flat; side faces smooth around circumference.
        for k in range(len(self.smooth)-4*n, len(self.smooth), 4):
            self.smooth[k+2] = self.smooth[k+3] = False

    def tube(self, a, b, outer, inner, mat, n=24):
        a, b = Vector(a), Vector(b)
        u, v, w = basis(b-a)
        verts = [p + r*(u*math.cos(2*math.pi*i/n)+v*math.sin(2*math.pi*i/n))
                 for p,r in ((a,outer),(b,outer),(a,inner),(b,inner))
                 for i in range(n)]
        faces = []
        for i in range(n):
            j = (i+1) % n
            faces += [(i,j,n+j,n+i), (2*n+j,2*n+i,3*n+i,3*n+j),
                      (j,i,2*n+i,2*n+j), (n+i,n+j,3*n+j,3*n+i)]
        self.part(verts, faces, mat, True)
        for k in range(len(self.smooth)-8*n, len(self.smooth), 8):
            for j in range(4,8): self.smooth[k+j] = False

    def arc(self, r0, r1, z0, z1, a0, a1, mat, n=None):
        # Closed annular sector with real wall thickness and capped ends.
        n = n or max(1, math.ceil(BODY_SEGMENTS*(a1-a0)/(2*math.pi)))
        count = n+1
        verts = [radial(a0+(a1-a0)*i/n,r,z)
                 for r,z in ((r1,z0),(r1,z1),(r0,z0),(r0,z1))
                 for i in range(count)]
        faces = []
        for i in range(n):
            j = i+1
            faces += [(i,j,count+j,count+i),
                      (2*count+j,2*count+i,3*count+i,3*count+j),
                      (j,i,2*count+i,2*count+j),
                      (count+i,count+j,3*count+j,3*count+i)]
        faces += [(0,count,3*count,2*count),
                  (n,2*count+n,3*count+n,count+n)]
        self.part(verts, faces, mat, True)
        start = len(self.smooth) - (8*n+4)
        for k in range(start,start+8*n,8):
            for j in range(4,8): self.smooth[k+j] = False
        self.smooth[-4:] = [False]*4

    def object(self, name, materials, collection=asset_collection):
        mesh = bpy.data.meshes.new(name+'_Mesh')
        mesh.from_pydata(self.verts, [], self.faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        for mat in materials: mesh.materials.append(mat)
        for p,mat,smooth in zip(mesh.polygons,self.mats,self.smooth):
            p.material_index = mat
            p.use_smooth = smooth
        # Explicit outward normals on every disconnected, closed component.
        bm = bmesh.new(); bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh); bm.free(); mesh.update()
        return obj


# Analytic bevels below are geometry, not modifiers. They are included in the
# triangle count and FBX, including when the script is run without a viewport.
class MeshBuilder(MeshBuilder):
    def solid_box(self,center,size,mat,axes):
        c=Vector(center); x,y,z=[axis*length/2 for axis,length in zip(axes,size)]
        verts=[c-x-y-z,c+x-y-z,c+x+y-z,c-x+y-z,
               c-x-y+z,c+x-y+z,c+x+y+z,c-x+y+z]
        self.part(verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),
                         (1,2,6,5),(2,3,7,6),(3,0,4,7)],mat)

    def bevel_box(self, center, size, mat, bevel=2.0, axes=None, angle=0, corner_cut=0):
        c = Vector(center)
        if axes is None:
            axes = (Vector((math.cos(angle),math.sin(angle),0)),
                    Vector((-math.sin(angle),math.cos(angle),0)),Vector((0,0,1)))
        x,y,z = (v/2 for v in size)
        q = min(bevel,x/3,y/3,z/3)
        def octagon(hx,hy):
            k=max(q,min(corner_cut,hx*0.8,hy*0.8))
            return [(-hx+k,-hy),(hx-k,-hy),(hx,-hy+k),(hx,hy-k),
                    (hx-k,hy),(-hx+k,hy),(-hx,hy-k),(-hx,-hy+k)]
        local = [(u,v,h) for hx,hy,h in
                 ((x-q,y-q,-z),(x,y,-z+q),(x,y,z-q),(x-q,y-q,z))
                 for u,v in octagon(hx,hy)]
        local += [(0,0,-z),(0,0,z)]
        verts = [c+axes[0]*u+axes[1]*v+axes[2]*w for u,v,w in local]
        faces = []
        for k in range(3):
            for j in range(8):
                m=(j+1)%8
                faces.append((k*8+j,k*8+m,(k+1)*8+m,(k+1)*8+j))
        for j in range(8):
            m=(j+1)%8
            faces += [(32,m,j),(33,24+j,24+m)]
        self.part(verts,faces,mat)

    def bevel_arc(self,r0,r1,z0,z1,a0,a1,mat,bevel=2.0,n=None):
        q=min(bevel,(r1-r0)/3,(z1-z0)/3)
        profile=[(r0+q,z0),(r1-q,z0),(r1,z0+q),(r1,z1-q),
                 (r1-q,z1),(r0+q,z1),(r0,z1-q),(r0,z0+q)]
        n=n or max(1,math.ceil(BODY_SEGMENTS*(a1-a0)/(2*math.pi)))
        full=abs(a1-a0-2*math.pi)<1e-6
        rings=n if full else n+1
        verts=[radial(a0+(a1-a0)*i/n,r,z) for i in range(rings) for r,z in profile]
        faces=[]
        for i in range(n):
            nxt=(i+1)%rings
            for j in range(8):
                m=(j+1)%8
                faces.append((i*8+j,nxt*8+j,nxt*8+m,i*8+m))
        if not full:
            verts += [radial(a0,(r0+r1)/2,(z0+z1)/2),radial(a1,(r0+r1)/2,(z0+z1)/2)]
            for j in range(8):
                m=(j+1)%8
                faces += [(rings*8,j,m),(rings*8+1,n*8+m,n*8+j)]
        self.part(verts,faces,mat,True)
        if not full: self.smooth[-16:]=[False]*16

    def axial_profile(self,origin,direction,profile,n=32):
        # Closed hollow lathe: (axial_distance, radius, material_for_next_edge).
        u,v,w=basis(direction); origin=Vector(origin)
        verts=[origin+w*t+r*(u*math.cos(2*math.pi*j/n)+v*math.sin(2*math.pi*j/n))
               for t,r,mat in profile for j in range(n)]
        offset=len(self.verts)
        self.verts.extend(tuple(p) for p in verts)
        for i,(t,r,mat) in enumerate(profile):
            nxt=(i+1)%len(profile)
            smooth=abs(t-profile[nxt][0])>1e-7
            for j in range(n):
                m=(j+1)%n
                quad=(offset+i*n+j,offset+i*n+m,offset+nxt*n+m,offset+nxt*n+j)
                for tri in (quad[:3],(quad[0],quad[2],quad[3])):
                    self.faces.append(tri); self.mats.append(mat); self.smooth.append(smooth)

    def chamfer_cylinder(self,a,b,radius,mat,n=32,bevel=2):
        a,b=Vector(a),Vector(b); u,v,w=basis(b-a)
        length=(b-a).length
        q=min(bevel,length/3,radius/3)
        profile=((0,radius-q),(q,radius),(length-q,radius),(length,radius-q))
        verts=[a+w*t+r*(u*math.cos(2*math.pi*j/n)+v*math.sin(2*math.pi*j/n))
               for t,r in profile for j in range(n)]
        verts += [a,b]
        faces=[]
        for i in range(3):
            for j in range(n):
                m=(j+1)%n
                faces.append((i*n+j,i*n+m,(i+1)*n+m,(i+1)*n+j))
        for j in range(n):
            m=(j+1)%n
            faces += [(4*n,m,j),(4*n+1,3*n+j,3*n+m)]
        self.part(verts,faces,mat,True)
        self.smooth[-2*n:]=[False]*(2*n)

    def prism(self,poly,origin,normal,u,v,depth,mat):
        # poly is convex and counter-clockwise in the local u/v plane.
        verts=[Vector(origin)+Vector(normal)*t+Vector(u)*a+Vector(v)*b
               for t in (0,depth) for a,b in poly]
        n=len(poly); faces=[]
        for j in range(1,n-1): faces += [(0,j+1,j),(n,n+j,n+j+1)]
        for j in range(n):
            m=(j+1)%n
            faces.append((j,m,n+m,n+j))
        self.part(verts,faces,mat)

    def shaped_arc(self,profile,a0,a1,mat,n=32):
        k=len(profile)
        verts=[radial(a0+(a1-a0)*i/n,r,z) for i in range(n+1) for r,z in profile]
        faces=[]
        for i in range(n):
            for j in range(k):
                m=(j+1)%k
                faces.append((i*k+j,(i+1)*k+j,(i+1)*k+m,i*k+m))
        cr=sum(r for r,z in profile)/k; cz=sum(z for r,z in profile)/k
        verts += [radial(a0,cr,cz),radial(a1,cr,cz)]
        for j in range(k):
            m=(j+1)%k
            faces += [((n+1)*k,j,m),((n+1)*k+1,n*k+m,n*k+j)]
        self.part(verts,faces,mat,True)
        self.smooth[-2*k:]=[False]*(2*k)

    def housing(self,direction,z):
        u,v,w=basis(direction); center=Vector((0,0,z)); verts=[]
        for ring in range(5):
            for j in range(PORT_HOUSING_SEGMENTS):
                angle=2*math.pi*j/PORT_HOUSING_SEGMENTS
                ca,sa=math.cos(angle),math.sin(angle)
                if ring<=2:
                    hw=PORT_HOUSING_HALF_WIDTH
                    hh=PORT_HOUSING_HALF_HEIGHT
                    q=PORT_HOUSING_CORNER_CUT
                    radius=min(hw/max(abs(ca),1e-9),hh/max(abs(sa),1e-9),
                               (hw+hh-q)/max(abs(ca)+abs(sa),1e-9))
                    if ring==2: radius-=PORT_HOUSING_BEVEL
                    a,b=radius*ca,radius*sa
                    if ring==0:
                        t=math.sqrt(INTERNAL_RADIUS**2-a*a)-PORT_HOUSING_EMBED
                    else:
                        t=PORT_HOUSING_FACE-(PORT_HOUSING_BEVEL if ring==1 else 0)
                else:
                    radius=PORT_BORE_RADIUS+PORT_BOSS_FRONT_BORE_EXTRA if ring==3 else PORT_THROAT_RADIUS
                    a,b=radius*ca,radius*sa
                    t=PORT_HOUSING_FACE if ring==3 else INTERNAL_RADIUS-PORT_HOUSING_EMBED
                verts.append(center+w*t+u*a+v*b)
        faces=[]
        for i in range(5):
            nxt=(i+1)%5
            for j in range(PORT_HOUSING_SEGMENTS):
                m=(j+1)%PORT_HOUSING_SEGMENTS
                faces.append((i*PORT_HOUSING_SEGMENTS+j,i*PORT_HOUSING_SEGMENTS+m,
                              nxt*PORT_HOUSING_SEGMENTS+m,nxt*PORT_HOUSING_SEGMENTS+j))
        self.part(verts,faces,SECONDARY)

# 5. CUTOUTS -- SUBTRACT ANGULAR/HEIGHT RECTANGLES BEFORE MAKING PANELS ----------
def subtract_rectangles(rectangles,cuts):
    result=list(rectangles)
    for ca,cb,cz0,cz1 in cuts:
        remaining=[]
        for a,b,z0,z1 in result:
            lo,hi=max(a,ca),min(b,cb)
            low,high=max(z0,cz0),min(z1,cz1)
            if hi<=lo or high<=low:
                remaining.append((a,b,z0,z1)); continue
            for r in ((a,lo,z0,z1),(hi,b,z0,z1),(lo,hi,z0,low),(lo,hi,high,z1)):
                if r[1]-r[0]>1e-7 and r[3]-r[2]>1e-7: remaining.append(r)
        result=remaining
    return result

def port_cuts(clearance=0,shell=False):
    width=PORT_HOUSING_HALF_WIDTH+clearance
    height=PORT_HOUSING_HALF_HEIGHT+clearance
    if shell: width-=PORT_SHELL_OVERLAP; height-=PORT_SHELL_OVERLAP
    theta=math.asin(width/(BODY_RADIUS if shell else PANEL_INNER_RADIUS))
    cuts=[]
    for name,d,z,yaw in PORTS:
        a=math.atan2(d.y,d.x)
        for wrap in (-2*math.pi,0,2*math.pi):
            cuts.append((a+wrap-theta,a+wrap+theta,z-height,z+height))
    return cuts

window_cut=(WINDOW_ANGLE_MIN,WINDOW_ANGLE_MAX,WINDOW_BOTTOM,WINDOW_TOP)
shell_cuts=[window_cut]+port_cuts(shell=True)
armor_cuts=[(WINDOW_ANGLE_MIN-0.008,WINDOW_ANGLE_MAX+0.008,WINDOW_BOTTOM-8,WINDOW_TOP+8)]+port_cuts(PORT_PANEL_CLEARANCE)

# Slots are cut out of armour rather than drawn onto its surface.
for i in range(PANEL_COUNT):
    a=-math.pi+2*math.pi*(i+0.5)/PANEL_COUNT
    for z in VENT_HEIGHTS:
        armor_cuts.append((a-0.15,a+0.15,z-VENT_HEIGHT/2,z+VENT_HEIGHT/2))

# 6. PLINTH / CLOSED SHELL / BEVELLED ARMOUR ------------------------------------
b=MeshBuilder()
b.bevel_box((0,0,PLINTH_HEIGHT/2),(PLINTH_WIDTH,PLINTH_WIDTH,PLINTH_HEIGHT),SECONDARY,PLINTH_CHAMFER,corner_cut=PLINTH_CORNER_CUT)
b.chamfer_cylinder((0,0,PLINTH_HEIGHT),(0,0,INTERNAL_FLOOR),ROOF_RADIUS,SECONDARY,BODY_SEGMENTS,RIM_CHAMFER)
for a0,a1,z0,z1 in subtract_rectangles([(-math.pi,math.pi,INTERNAL_FLOOR,INTERNAL_TOP)],shell_cuts):
    b.arc(INTERNAL_RADIUS,BODY_RADIUS,z0,z1,a0,a1,SECONDARY)
b.chamfer_cylinder((0,0,INTERNAL_FLOOR-FLOOR_PLATE_THICKNESS),(0,0,INTERNAL_FLOOR),BODY_RADIUS,SECONDARY,BODY_SEGMENTS,RIM_CHAMFER)
b.chamfer_cylinder((0,0,INTERNAL_TOP),(0,0,ROOF_Z),ROOF_RADIUS,SECONDARY,BODY_SEGMENTS,RIM_CHAMFER)

for row in range(PANEL_ROWS):
    step=(PANEL_END_Z-PANEL_START_Z)/PANEL_ROWS
    z0=PANEL_START_Z+row*step+PANEL_Z_GAP/2
    z1=PANEL_START_Z+(row+1)*step-PANEL_Z_GAP/2
    for i in range(PANEL_COUNT):
        a0=-math.pi+2*math.pi*i/PANEL_COUNT+PANEL_ANGLE_GAP
        a1=-math.pi+2*math.pi*(i+1)/PANEL_COUNT-PANEL_ANGLE_GAP
        for lo,hi,za,zb in subtract_rectangles([(a0,a1,z0,z1)],armor_cuts):
            if hi-lo<PANEL_MIN_ANGLE or zb-za<PANEL_MIN_HEIGHT: continue
            # Painted (secondary swatch), not bare metal: in METAL the big curved panels read as
            # chrome stripes around the tank (user feedback 2026-11-10).
            b.bevel_arc(PANEL_INNER_RADIUS,PANEL_OUTER_RADIUS,za,zb,lo,hi,SECONDARY,PANEL_CHAMFER)
            if hi-lo>2*RIVET_ANGLE_INSET and zb-za>2*RIVET_Z_INSET:
                # Two diagonal fasteners keep cut panel fragments readable
                # without spending the budget on four bolts per tiny patch.
                for a,z in ((lo+RIVET_ANGLE_INSET,za+RIVET_Z_INSET),
                            (hi-RIVET_ANGLE_INSET,zb-RIVET_Z_INSET)):
                    b.cylinder(radial(a,PANEL_OUTER_RADIUS,z),
                               radial(a,PANEL_OUTER_RADIUS+RIVET_DEPTH,z),RIVET_RADIUS,METAL,BOLT_SEGMENTS)
for z in FRAME_RING_Z:
    for a0,a1,za,zb in subtract_rectangles([(-math.pi,math.pi,z-FRAME_RING_HEIGHT/2,z+FRAME_RING_HEIGHT/2)],armor_cuts):
        # Clip the height as well as the angle when a housing meets a frame band.
        b.bevel_arc(BODY_RADIUS-1,FRAME_RING_RADIUS,za,zb,a0,a1,SECONDARY,RIM_CHAMFER)
b.bevel_arc(BODY_RADIUS-3,ROOF_RIM_RADIUS,ROOF_Z-ROOF_RIM_BELOW,ROOF_Z+ROOF_RIM_ABOVE,0,2*math.pi,METAL,RIM_CHAMFER)
b.chamfer_cylinder((*HATCH_XY,ROOF_Z),(*HATCH_XY,ROOF_Z+HATCH_HEIGHT),HATCH_RADIUS,METAL,HATCH_SEGMENTS,SMALL_CHAMFER)
b.bevel_box((*HATCH_XY,ROOF_Z+HATCH_HANDLE_HEIGHT),HATCH_HANDLE_SIZE,SECONDARY,SMALL_CHAMFER)

# Shaped shoulder: a pressure-vessel crown that rolls inward toward the roof.
b.shaped_arc(SHOULDER_PROFILE,WINDOW_ANGLE_MAX,WINDOW_ANGLE_MIN+2*math.pi,SECONDARY,48)
# Close only the cap above the sight pane.
b.shaped_arc(((196,769),(222,769),(217,780),(205,798),(196,798)),
             WINDOW_ANGLE_MIN,WINDOW_ANGLE_MAX,SECONDARY,4)
# Lower protective skirt and local orange armour cheeks, clear of pipe bosses.
for a0,a1,z0,z1 in subtract_rectangles([(-math.pi,math.pi,98,282)],armor_cuts):
    if a1-a0>0.03 and z1-z0>8:
        b.bevel_arc(211,228,z0,z1,a0,a1,SECONDARY,3)
for degrees in SPINE_ANGLES:
    a=math.radians(degrees)
    b.bevel_box(radial(a,SPINE_RADIUS,(SPINE_BOTTOM+SPINE_TOP)/2),
                (*SPINE_SIZE,SPINE_TOP-SPINE_BOTTOM),SECONDARY,3,angle=a)
    b.bevel_box(radial(a,SPINE_RADIUS+13,450),(5,9,540),METAL,1.5,angle=a)
    for z,height in ((151,146),(760,68)):
        b.bevel_box(radial(a,SPINE_RADIUS+3,z),(34,43,height),PRIMARY,5,angle=a)
    b.bevel_box(radial(a,250,85),(70,53,44),PRIMARY,6,angle=a)
# Orange service crown is broken into three arcs; the ladder gets a clear gap.
for start,end in ((-162,-56),(-48,64),(72,162)):   # gap matches RAIL_GAP_DEGREES at 180
    b.bevel_arc(CROWN_INNER_RADIUS,CROWN_OUTER_RADIUS,CROWN_BOTTOM,CROWN_TOP,
                math.radians(start),math.radians(end),PRIMARY,3)

# 7. EXPORTED HAZARD STRIPES / CORNER POSTS / LOAD-BEARING GUSSETS ---------------
def clip_polygon(poly,axis,limit,keep_greater):
    out=[]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        inside_p=p[axis]>=limit if keep_greater else p[axis]<=limit
        inside_q=q[axis]>=limit if keep_greater else q[axis]<=limit
        if inside_p: out.append(p)
        if inside_p!=inside_q:
            t=(limit-p[axis])/(q[axis]-p[axis])
            out.append(tuple(p[j]+t*(q[j]-p[j]) for j in range(2)))
    return out
for face_angle in (0,math.pi/2,math.pi,3*math.pi/2):
    normal=radial(face_angle,1,0)
    u=Vector((-normal.y,normal.x,0)); v=Vector((0,0,1))
    origin=normal*(PLINTH_WIDTH/2+HAZARD_PROJECTION)
    shift=HAZARD_SLOPE*(HAZARD_TOP-HAZARD_BOTTOM)
    count=math.ceil((2*HAZARD_HALF_SPAN+abs(shift))/HAZARD_PITCH)+2
    for i in range(-count,count+1):
        start=i*HAZARD_PITCH
        poly=[(start,HAZARD_BOTTOM),(start+HAZARD_YELLOW_WIDTH,HAZARD_BOTTOM),
              (start+HAZARD_YELLOW_WIDTH+shift,HAZARD_TOP),(start+shift,HAZARD_TOP)]
        poly=clip_polygon(poly,0,-HAZARD_HALF_SPAN,True)
        if poly: poly=clip_polygon(poly,0,HAZARD_HALF_SPAN,False)
        if len(poly)>=3: b.prism(poly,origin,normal,u,v,HAZARD_THICKNESS,HAZARD)
for x in (-CORNER_POST_OFFSET,CORNER_POST_OFFSET):
    for y in (-CORNER_POST_OFFSET,CORNER_POST_OFFSET):
        b.bevel_box((x,y,CORNER_POST_HEIGHT/2),(CORNER_POST_WIDTH,CORNER_POST_WIDTH,CORNER_POST_HEIGHT),
                    METAL,CORNER_POST_CHAMFER)
        b.cylinder((x,y,CORNER_POST_HEIGHT),(x,y,CORNER_POST_HEIGHT+CORNER_BOLT_HEIGHT),CORNER_BOLT_RADIUS,SECONDARY,BOLT_SEGMENTS)
for angle_degrees in GUSSET_ANGLES:
    a=math.radians(angle_degrees)
    u=radial(a,1,0); v=Vector((0,0,1)); tangent=u.cross(v)
    base=PLINTH_HEIGHT+GUSSET_BASE_RAISE
    poly=[(GUSSET_INNER_RADIUS,base),(GUSSET_OUTER_RADIUS,base),
          (GUSSET_INNER_RADIUS+GUSSET_TOP_RADIAL_SHIFT,base+GUSSET_HEIGHT)]
    b.prism(poly,-tangent*GUSSET_THICKNESS/2,tangent,u,v,GUSSET_THICKNESS,SECONDARY)

# 8. REINFORCED VANILLA-FAMILY COUPLINGS -- FACE PLANE IS EXACTLY R=290 ----------
port_collision_points=[]
for socket_name,direction,z,yaw in PORTS:
    origin=Vector((0,0,z)); u,v,w=basis(direction)
    def p(t): return origin+direction*t
    before=len(b.verts)
    b.housing(direction,z)
    # The profile returns along the inside, creating a real 146 cm clear throat.
    # Front bevel opens from 146 to 150 cm without moving the face plane.
    profile=[
        (PORT_SLEEVE_BACK,PORT_NECK_RADIUS,SECONDARY),
        (PORT_BACK_RING_Z,PORT_NECK_RADIUS,SECONDARY),
        (PORT_FACE_RADIUS-PORT_FLANGE_THICKNESS-PORT_PROFILE_SHOULDER_SETBACK,PORT_FLANGE_RADIUS-PORT_PROFILE_SHOULDER_INSET,METAL),
        (PORT_FACE_RADIUS-PORT_FLANGE_THICKNESS,PORT_FLANGE_RADIUS,METAL),
        (PORT_FACE_RADIUS-PORT_BOLT_RECESS-PORT_MOUTH_CHAMFER,PORT_FLANGE_RADIUS,METAL),
        (PORT_FACE_RADIUS-PORT_BOLT_RECESS,PORT_FLANGE_RADIUS-PORT_MOUTH_CHAMFER,METAL),
        (PORT_FACE_RADIUS-PORT_BOLT_RECESS,PORT_BOLT_LEDGE_INNER_RADIUS,METAL),
        (PORT_FACE_RADIUS,PORT_BORE_RADIUS+PORT_CONTACT_LIP_WIDTH,METAL),
        (PORT_FACE_RADIUS,PORT_BORE_RADIUS,METAL),
        (PORT_FACE_RADIUS-PORT_MOUTH_CHAMFER,PORT_THROAT_RADIUS,INTERIOR),
        (PORT_SLEEVE_BACK,PORT_THROAT_RADIUS,SECONDARY),
    ]
    b.axial_profile(origin,direction,profile,PORT_SEGMENTS)
    b.axial_profile(origin,direction,[
        (PORT_BACK_RING_Z-PORT_BACK_RING_WIDTH,PORT_NECK_RADIUS-PORT_BACK_RING_EMBED,METAL),
        (PORT_BACK_RING_Z-PORT_BACK_RING_WIDTH+1,PORT_NECK_RADIUS+PORT_BACK_RING_RAISE,METAL),
        (PORT_BACK_RING_Z-1,PORT_NECK_RADIUS+PORT_BACK_RING_RAISE,METAL),
        (PORT_BACK_RING_Z,PORT_NECK_RADIUS-PORT_BACK_RING_EMBED,SECONDARY)],PORT_SEGMENTS)
    # Recessed dark bore/cap, behind a full-depth seating area.
    b.tube(p(PORT_INTERIOR_CAP_DISTANCE),p(PORT_SLEEVE_BACK),
           PORT_THROAT_RADIUS+PORT_INTERIOR_WALL,PORT_THROAT_RADIUS,INTERIOR,PORT_SEGMENTS)
    b.cylinder(p(PORT_INTERIOR_CAP_DISTANCE-PORT_INTERIOR_CAP_THICKNESS),p(PORT_INTERIOR_CAP_DISTANCE),PORT_THROAT_RADIUS,INTERIOR,PORT_SEGMENTS)
    for j in range(PORT_BOLT_COUNT):
        a=2*math.pi*j/PORT_BOLT_COUNT+math.radians(PORT_BOLT_PHASE_DEGREES)
        offset=PORT_BOLT_PITCH_RADIUS*(u*math.cos(a)+v*math.sin(a))
        bolt_base=PORT_FACE_RADIUS-PORT_BOLT_RECESS
        b.cylinder(p(bolt_base)+offset,p(bolt_base+PORT_BOLT_HEAD_DEPTH)+offset,
                   PORT_BOLT_HEAD_RADIUS,SECONDARY,PORT_BOLT_SEGMENTS)
    rib_center=PORT_FACE_RADIUS-PORT_FLANGE_THICKNESS-PORT_RIB_LENGTH/2
    for degrees in PORT_RIB_ANGLES:
        a=math.radians(degrees)
        radial_axis=u*math.cos(a)+v*math.sin(a)
        tangent_axis=-u*math.sin(a)+v*math.cos(a)
        b.bevel_box(p(rib_center)+radial_axis*PORT_RIB_RADIUS,
            (PORT_RIB_LENGTH,PORT_RIB_RADIAL_THICKNESS,PORT_RIB_WIDTH),METAL,PORT_DETAIL_CHAMFER,
            axes=(direction,radial_axis,tangent_axis))
    guard_center=PORT_FACE_RADIUS-PORT_GUARD_FACE_RECESS-PORT_GUARD_LENGTH/2
    for sign in (-1,1):
        ru=u*sign; tv=v*sign
        b.bevel_box(p(guard_center)+ru*PORT_GUARD_RADIUS,
                   (PORT_GUARD_LENGTH,PORT_GUARD_THICKNESS,PORT_GUARD_HEIGHT),SECONDARY,
                   PORT_DETAIL_CHAMFER,axes=(direction,ru,tv))
        # Original yellow double-chevron markings, made from thin closed prisms.
        # These have a material slot, not a Blender-only node or a copied decal.
        for height in PORT_ARROW_HEIGHTS:
            for slope in (-1,1):
                radial_axis=(ru+tv*slope).normalized()
                across=direction.cross(radial_axis)
                center=p(PORT_FACE_RADIUS-PORT_ARROW_FACE_RECESS)+ru*PORT_GUARD_RADIUS+tv*(height+slope*PORT_ARROW_HALF_HEIGHT)
                b.solid_box(center,(PORT_ARROW_DEPTH,PORT_GUARD_ARROW_SIZE,PORT_GUARD_ARROW_THICKNESS),
                            HAZARD,axes=(direction,radial_axis,across))
    # Hull is built from all port vertices, including the reinforced boss/guards.
    # Points are retained separately so there is exactly one convex hull per port.
    port_collision_points.append(list(b.verts[before:]))

# 9. SIGHT STRIP FRAME / LEVEL SCALE / EXACT 75% MARKER -------------------------
for a in (WINDOW_ANGLE_MIN,WINDOW_ANGLE_MAX):
    b.bevel_box(radial(a,WINDOW_FRAME_RADIUS,(WINDOW_BOTTOM+WINDOW_TOP)/2),
                (WINDOW_FRAME_RADIAL_SIZE,WINDOW_FRAME_WIDTH,WINDOW_TOP-WINDOW_BOTTOM+WINDOW_FRAME_END_EXTENSION),
                SECONDARY,WINDOW_FRAME_CHAMFER,angle=a)
    z=WINDOW_BOTTOM+WINDOW_BOLT_START_OFFSET
    while z<WINDOW_TOP-WINDOW_BOLT_END_INSET:
        b.cylinder(radial(a,WINDOW_BOLT_BASE_RADIUS,z),radial(a,WINDOW_BOLT_FACE_RADIUS,z),WINDOW_BOLT_RADIUS,METAL,BOLT_SEGMENTS)
        z+=WINDOW_BOLT_STEP
for z in (WINDOW_BOTTOM,WINDOW_TOP):
    b.bevel_arc(WINDOW_END_FRAME_INNER_RADIUS,WINDOW_END_FRAME_OUTER_RADIUS,z-WINDOW_END_FRAME_HALF_HEIGHT,z+WINDOW_END_FRAME_HALF_HEIGHT,WINDOW_ANGLE_MIN-WINDOW_END_FRAME_ANGLE_MARGIN,WINDOW_ANGLE_MAX+WINDOW_END_FRAME_ANGLE_MARGIN,METAL,SMALL_CHAMFER)
mark_angle=WINDOW_ANGLE_MAX+WINDOW_MARK_OFFSET
for step in range(1,WINDOW_MARK_STEPS):
    z=INTERNAL_FLOOR+LIQUID_HEIGHT*step/WINDOW_MARK_STEPS
    length=WINDOW_MARK_MAJOR_LENGTH if step%5==0 else WINDOW_MARK_MINOR_LENGTH
    b.box(radial(mark_angle,WINDOW_MARK_RADIUS,z),(WINDOW_MARK_SIZE[0],length,WINDOW_MARK_SIZE[1]),METAL,mark_angle)
b.bevel_box(radial(mark_angle,WINDOW_MARK_RADIUS+WINDOW_OVERFLOW_MARK_RAISE,OVERFLOW_Z),WINDOW_OVERFLOW_MARK_SIZE,HAZARD,WINDOW_OVERFLOW_MARK_RAISE,angle=mark_angle)

# 10. LADDER / ROOF RAILING ----------------------------------------------------
ladder_normal=radial(LADDER_ANGLE,1,0)
ladder_tangent=Vector((-ladder_normal.y,ladder_normal.x,0))
for sign in (-1,1):
    xy=ladder_normal*LADDER_RADIUS+ladder_tangent*(sign*LADDER_WIDTH/2)
    b.cylinder(xy+Vector((0,0,LADDER_BOTTOM)),xy+Vector((0,0,LADDER_TOP)),LADDER_RAIL_RADIUS,METAL,LADDER_SEGMENTS)
    for z in LADDER_SUPPORT_HEIGHTS:
        b.cylinder(ladder_normal*215+ladder_tangent*(sign*LADDER_WIDTH/2)+Vector((0,0,z)),
                   xy+Vector((0,0,z)),LADDER_SUPPORT_RADIUS,SECONDARY,LADDER_SEGMENTS)
z=LADDER_RUNG_START
while z<ROOF_Z+1:
    c=ladder_normal*LADDER_RADIUS+Vector((0,0,z))
    b.cylinder(c-ladder_tangent*LADDER_WIDTH/2,c+ladder_tangent*LADDER_WIDTH/2,
               LADDER_RUNG_RADIUS,METAL,LADDER_SEGMENTS)
    z+=LADDER_RUNG_SPACING
gap=math.radians(RAIL_GAP_DEGREES)
a0,a1=LADDER_ANGLE+gap/2,LADDER_ANGLE+2*math.pi-gap/2
for z in (ROOF_Z+RAIL_LOWER_HEIGHT,):
    for i in range(RAIL_SEGMENTS):
        aa=a0+(a1-a0)*i/RAIL_SEGMENTS
        ab=a0+(a1-a0)*(i+1)/RAIL_SEGMENTS
        b.cylinder(radial(aa,RAIL_RADIUS,z),radial(ab,RAIL_RADIUS,z),RAIL_TUBE_RADIUS,METAL,RAIL_CROSS_SEGMENTS)
for i in range(RAIL_POST_COUNT):
    a=a0+(a1-a0)*i/(RAIL_POST_COUNT-1)
    b.cylinder(radial(a,RAIL_RADIUS,ROOF_Z),radial(a,RAIL_RADIUS,CROWN_TOP-1),RAIL_POST_RADIUS,METAL,LADDER_SEGMENTS)
main=b.object('SM_OverflowTank',MAIN_MATERIALS)
assert LOD0_MIN_TRIANGLES<=len(main.data.polygons)<=LOD0_MAX_TRIANGLES, f'LOD0 triangle budget: {len(main.data.polygons)}'




# 11. SEPARATE FULL-HEIGHT LIQUID / GLASS ---------------------------------------
l = MeshBuilder()
l.cylinder((0,0,0),(0,0,LIQUID_HEIGHT),LIQUID_RADIUS,0,BODY_SEGMENTS)
liquid = l.object('SM_OverflowTank_Liquid',[liquid_material])
# Geometry starts at local Z=0. Location is internal floor, scale remains 1.
# Fill display: liquid.scale.z = fraction. Do NOT change origin to tank floor.
liquid.location.z = INTERNAL_FLOOR
liquid['FullHeightCm'] = LIQUID_HEIGHT
liquid['InternalFloorCm'] = INTERNAL_FLOOR
liquid['Example80PercentScaleZ'] = 0.8
liquid['FullCylinderTopCm'] = INTERNAL_TOP

g = MeshBuilder()
g.arc(GLASS_INNER_RADIUS,GLASS_OUTER_RADIUS,WINDOW_BOTTOM,WINDOW_TOP,
      WINDOW_ANGLE_MIN,WINDOW_ANGLE_MAX,0)
glass = g.object('SM_OverflowTank_Glass',[glass_material])

# 12. UV0 TEXTURE ATLAS / UV1 LIGHTMAP ATLAS -----------------------------------
def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def unwrap(obj):
    activate(obj)
    # LODs are re-unwrapped AFTER decimation to avoid inherited UV folds.
    while obj.data.uv_layers: obj.data.uv_layers.remove(obj.data.uv_layers[0])
    # One padded unique atlas is valid for both channels. Copying it saves a
    # second identical packing pass while retaining two independent UV layers.
    layer=obj.data.uv_layers.new(name='UV0')
    obj.data.uv_layers.active=layer
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(UV_PROJECT_ANGLE_DEGREES),
        margin_method='FRACTION',island_margin=UV_MARGIN,
        area_weight=0.0,correct_aspect=False,scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.data.uv_layers.new(name='UV1_Lightmap',do_init=True)
    obj.data.uv_layers.active_index = 0
    obj.data.uv_layers[0].active_render = True
    obj['LightmapCoordinateIndex'] = 1
    obj['SuggestedLightmapResolution'] = LIGHTMAP_RESOLUTION

for obj in (main,liquid,glass): unwrap(obj)

# 13. DECIMATED LODS -- MODIFIERS APPLIED --------------------------------------
def triangulate_and_normals(obj):
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data); bm.free(); obj.data.update()

lods = []
for name,ratio in (('SM_OverflowTank_LOD1',LOD1_RATIO),('SM_OverflowTank_LOD2',LOD2_RATIO)):
    obj = main.copy(); obj.data = main.data.copy(); obj.name = name
    lod_collection.objects.link(obj)
    activate(obj)
    dec = obj.modifiers.new('Reduction','DECIMATE')
    dec.decimate_type = 'COLLAPSE'; dec.ratio = ratio
    dec.use_collapse_triangulate = True
    # Collapse the joined asset; keep its material slots and regenerate UVs below.
    bpy.ops.object.modifier_apply(modifier=dec.name)
    triangulate_and_normals(obj)
    unwrap(obj)
    obj.hide_set(True)  # avoid coincident LODs in the working viewport
    obj.hide_render = True
    lods.append(obj)

# 14. SIMPLE CLOSED CONVEX COLLISION -- EXACTLY FIVE HULLS ---------------------
collisions = []
def collision(builder):
    obj = builder.object(f'UCX_SM_OverflowTank_{len(collisions)+1:02d}',[],collision_collection)
    obj.display_type = 'WIRE'; obj.hide_render = True
    obj.hide_set(True)
    collisions.append(obj)

c = MeshBuilder()
c.cylinder((0,0,PLINTH_HEIGHT+1),(0,0,ROOF_Z),MAIN_COLLISION_RADIUS,0,MAIN_COLLISION_SEGMENTS)
collision(c)
for points in port_collision_points:
    # One convex envelope of the complete boss, rim, ribs and guard plates.
    bm=bmesh.new()
    for point in points: bm.verts.new(point)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.0001)
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    unused=[v for v in bm.verts if not v.link_faces]
    if unused: bmesh.ops.delete(bm,geom=unused,context='VERTS')
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    mesh=bpy.data.meshes.new('PortConvexCollision')
    bm.to_mesh(mesh); bm.free()
    obj=bpy.data.objects.new(f'UCX_SM_OverflowTank_{len(collisions)+1:02d}',mesh)
    collision_collection.objects.link(obj)
    obj.display_type='WIRE'; obj.hide_render=True; obj.hide_set(True)
    collisions.append(obj)
c = MeshBuilder()
c.box((0,0,PLINTH_HEIGHT/2),(PLINTH_WIDTH+2,PLINTH_WIDTH+2,PLINTH_HEIGHT),0)
collision(c)
# Port hulls deliberately fill the visual bore (one convex envelope per housing).
# Ladder rungs: one box per rung, so the climber stays in front of the ladder and footstep traces
# hit something. The side rails get none: above the roof they would block the step off the ladder.
z=LADDER_RUNG_START
while z<ROOF_Z+1:
    c = MeshBuilder()
    c.box(ladder_normal*LADDER_RADIUS+Vector((0,0,z)),
          (LADDER_RUNG_COLLISION_DEPTH,LADDER_WIDTH+2*LADDER_RAIL_RADIUS,2*LADDER_RUNG_RADIUS),0,angle=LADDER_ANGLE)
    collision(c)
    z+=LADDER_RUNG_SPACING
# Roof railing: one thin wall per rail segment, roof to crown top, leaving the ladder gap open.
for i in range(RAIL_SEGMENTS):
    aa=a0+(a1-a0)*i/RAIL_SEGMENTS
    ab=a0+(a1-a0)*(i+1)/RAIL_SEGMENTS
    half=(ab-aa)/2
    c = MeshBuilder()
    c.box(radial(aa+half,RAIL_RADIUS*math.cos(half),(ROOF_Z+CROWN_TOP)/2),
          (RAIL_COLLISION_THICKNESS,2*RAIL_RADIUS*math.sin(half)+RAIL_POST_RADIUS,CROWN_TOP-ROOF_Z),0,angle=aa+half)
    collision(c)

# 15. SOCKET EMPTIES + TRANSFORMS ---------------------------------------------
socket_rows = []
for name,direction,z,yaw in PORTS:
    obj = bpy.data.objects.new(name,None)
    asset_collection.objects.link(obj)
    obj.empty_display_type = 'ARROWS'; obj.empty_display_size = 35
    obj.location = direction*PORT_FACE_RADIUS+Vector((0,0,z))
    obj.rotation_euler = (0,0,math.atan2(direction.y,direction.x))
    # Empty local +X is the outward pipe normal; no parent scale to contaminate it.
    obj['Note'] = 'Mesh-only FBX omits empties: create named socket in UE using these numbers.'
    socket_rows.append({'name':name,'location_cm':list(obj.location),
                        'rotation_degrees':{'pitch':0,'yaw':yaw,'roll':0}})

manifest = {
    'asset':'SM_OverflowTank','coordinate_policy':'numeric XYZ preserved; +X front, Z up',
    'internal_floor_cm':INTERNAL_FLOOR,'internal_top_cm':INTERNAL_TOP,
    'overflow_center_cm':OVERFLOW_Z,'liquid_full_height_cm':LIQUID_HEIGHT,
    'liquid_component_relative_location_cm':[0,0,INTERNAL_FLOOR],
    'sockets':socket_rows,
    'port_mouth_diameter_cm':2*PORT_BORE_RADIUS,'port_throat_diameter_cm':2*PORT_THROAT_RADIUS,
    'port_flange_diameter_cm':2*PORT_FLANGE_RADIUS,
    'port_housing_width_height_cm':[2*PORT_HOUSING_HALF_WIDTH,2*PORT_HOUSING_HALF_HEIGHT],
}
text_block = bpy.data.texts.get('OverflowTank_ImportManifest.json') or bpy.data.texts.new('OverflowTank_ImportManifest.json')
text_block.clear(); text_block.write(json.dumps(manifest,indent=2))
if WRITE_SOCKET_JSON:
    Path(FBX_DIRECTORY).mkdir(parents=True,exist_ok=True)
    (Path(FBX_DIRECTORY)/'OverflowTank_ImportManifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

# 16. VALIDATE / REPORT --------------------------------------------------------
render_objects = [main,liquid,glass]+lods
for obj in render_objects:
    assert not obj.modifiers, f'Unapplied modifier on {obj.name}'
    assert len(obj.data.uv_layers)==2
    assert all(len(p.vertices)==3 for p in obj.data.polygons)
    assert all(p.area > 1e-8 for p in obj.data.polygons), f'Degenerate face: {obj.name}'
    assert tuple(obj.scale)==(1,1,1) and sum(abs(v) for v in obj.rotation_euler) < 1e-6
    for layer in obj.data.uv_layers:
        assert all(-0.0001 <= value <= 1.0001 for loop in layer.data for value in loop.uv)
# Exact max extents, including bolts, ladder and foundation trim.
for v in main.data.vertices:
    assert abs(v.co.x)<=FOOTPRINT/2 and abs(v.co.y)<=FOOTPRINT/2
    assert v.co.z >= -1e-5 and v.co.z <= RAIL_TOP+1e-5
main['OverflowCenterCm'] = OVERFLOW_Z
main['OverflowFraction'] = OVERFLOW_FRACTION
main['FrontAxis'] = '+X'
print('\n========== OVERFLOW TANK COMPLETE ==========')
print(f'1 Blender unit = 1 cm; internal floor/top = {INTERNAL_FLOOR:.2f}/{INTERNAL_TOP:.2f} cm')
print(f'Internal liquid height: {LIQUID_HEIGHT:.2f} cm')
print(f'Overflow centerline: {OVERFLOW_Z:.2f} cm above floor (75% of usable height)')
print(f'80% surface: {INTERNAL_FLOOR+0.8*LIQUID_HEIGHT:.2f} cm')
for obj in render_objects:
    print(f'{obj.name}: {len(obj.data.polygons):,} triangles')
for row in socket_rows: print(row)
print(f'Port mouth/throat diameters: {2*PORT_BORE_RADIUS:.1f} / {2*PORT_THROAT_RADIUS:.1f} cm')
print(f'Port flange diameter: {2*PORT_FLANGE_RADIUS:.1f} cm; flange depth: {PORT_FLANGE_THICKNESS:.1f} cm')
print(f'Port housing: {2*PORT_HOUSING_HALF_WIDTH:.1f} x {2*PORT_HOUSING_HALF_HEIGHT:.1f} cm')
print(f'Port bolt pattern: {PORT_BOLT_COUNT} on {2*PORT_BOLT_PITCH_RADIUS:.1f} cm PCD; head diameter {2*PORT_BOLT_HEAD_RADIUS:.1f} cm')
print(f'Port seating depth before recessed cap: {PORT_FACE_RADIUS-PORT_INTERIOR_CAP_DISTANCE:.1f} cm')
print(f'{len(collisions)} UCX hulls; two UV channels; applied geometry chamfers; exported mesh stripes.')
print('Socket transforms also available in Blender Text: OverflowTank_ImportManifest.json')
activate(main)

# 17. FBX EXPORT -- EXISTING FUNCTION, SETTINGS AND FILE NAMES PRESERVED --------
# The settings below intentionally PRESERVE numeric XYZ coordinates. In UE5.6:
# Convert Scene OFF, Convert Scene Unit ON, Force Front XAxis OFF; rotation 0.
# All geometry is authored in the intended UE basis (+X front / Z up), so no
# speculative -90 degree corrective rotations or experimental space bake needed.
# apply_unit_scale=True with scene scale .01 gives centimetre FBX units.
# 'Apply transforms' is already satisfied: render mesh rotations/scales are
# identity and geometry is built in final coordinates. Liquid translation is
# temporarily zeroed to export its actual bottom pivot; restored afterward.
# A Blender _LOD1 name alone is NOT an FBX LODGroup. Export LODs separately.
FBX_OPTIONS = dict(
    use_selection=True, object_types={'MESH'}, global_scale=1.0,
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
    axis_forward='-Y', axis_up='Z', use_space_transform=False,
    bake_space_transform=False, use_mesh_modifiers=True,
    mesh_smooth_type='FACE', use_tspace=False, use_custom_props=False,
    bake_anim=False, add_leaf_bones=False, path_mode='AUTO',
)

EXPORT_JOBS = [
    ('SM_AdvancedFluidBuffer.fbx',[main]+collisions),
    ('SM_AdvancedFluidBuffer_LOD1.fbx',[lods[0]]),
    ('SM_AdvancedFluidBuffer_LOD2.fbx',[lods[1]]),
    ('SM_AdvancedFluidBuffer_Liquid.fbx',[liquid]),
    ('SM_AdvancedFluidBuffer_Glass.fbx',[glass]),
]

def export_all_fbx():
    Path(FBX_DIRECTORY).mkdir(parents=True,exist_ok=True)
    original_active = bpy.context.view_layer.objects.active
    original_selected = list(bpy.context.selected_objects)
    original_locations = {o:o.location.copy() for o in render_objects}
    original_hidden = {o:o.hide_get() for o in render_objects+collisions}
    try:
        liquid.location = (0,0,0)  # component is placed at Z=90 in UE Blueprint
        for filename,objects in EXPORT_JOBS:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in objects:
                obj.hide_set(False); obj.select_set(True)
            bpy.context.view_layer.objects.active = objects[0]
            bpy.context.view_layer.update()
            # Export call intentionally remains enabled, as in the supplied script.
            bpy.ops.export_scene.fbx(filepath=str(Path(FBX_DIRECTORY)/filename), **FBX_OPTIONS)
            print('Export prepared:',str(Path(FBX_DIRECTORY)/filename))
    finally:
        bpy.ops.object.select_all(action='DESELECT')
        for obj,location in original_locations.items(): obj.location = location
        for obj,hidden in original_hidden.items(): obj.hide_set(hidden)
        for obj in original_selected: obj.select_set(True)
        bpy.context.view_layer.objects.active = original_active

# Existing entry point: writes the same five FBXs to the same Export folder.
export_all_fbx()




