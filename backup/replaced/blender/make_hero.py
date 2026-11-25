# Toonistaan Blender character builder (headless). Usage:
#   blender -b --python make_hero.py -- out.png [front|side|back] [male|female]
import bpy, bmesh, math, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "/root/hero.png"
VIEW = argv[1] if len(argv) > 1 else "front"
KIND = argv[2] if len(argv) > 2 else "male"
FEMALE = KIND == "female"

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def mat(name, color, rough=0.5, sss=0.0, sheen=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
        b.inputs["Subsurface Scale"].default_value = 0.03
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
    return m

def lin(h):
    return tuple(pow(int(h[i:i+2], 16) / 255, 2.2) for i in (1, 3, 5))

SKIN = mat("skin", lin("#C98B68" if not FEMALE else "#D99B7A"), 0.45, sss=0.25)
HAIR = mat("hair", lin("#17120F"), 0.35)
SHIRT = mat("shirt", lin("#2878C8" if not FEMALE else "#C2185B"), 0.8, sheen=0.4)
PANT = mat("pant", lin("#30364A"), 0.75, sheen=0.3)
SHOE = mat("shoe", lin("#39271E"), 0.35)
EYEW = mat("eyewhite", (0.85, 0.85, 0.82), 0.15)
IRIS = mat("iris", lin("#3A2216"), 0.1)
PUPIL = mat("pupil", (0.005, 0.005, 0.005), 0.1)
LIP = mat("lip", lin("#A85A55" if not FEMALE else "#B8475A"), 0.35, sss=0.2)
GOLD = mat("border", lin("#E0B040"), 0.3)

def obj_from_bm(name, bm, m):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    o.data.materials.append(m); return o

def smooth(o, levels=2):
    for p in o.data.polygons: p.use_smooth = True
    md = o.modifiers.new("sub", "SUBSURF"); md.levels = levels; md.render_levels = levels
    return o

# ---------- BODY: skin-modifier skeleton (ek jude hue mesh se poora sharir) ----------
H = 1.0 if not FEMALE else 0.95
J = {  # joint: (position, radius x, radius y)
 "pelvis": ((0, 0, .98), .135, .10), "waist": ((0, 0, 1.10), .12 if not FEMALE else .10, .09),
 "chest": ((0, 0, 1.28), .16 if not FEMALE else .13, .105), "neckb": ((0, 0, 1.45), .055, .055),
 "neckt": ((0, 0, 1.585), .046, .05),
}
S = .19 if not FEMALE else .165
for sd, x in (("L", 1), ("R", -1)):
    J["clav"+sd] = ((x*.07, 0, 1.43), .06, .055)
    J["sh"+sd] = ((x*S, 0, 1.40), .055, .055)
    J["bic"+sd] = ((x*(S+.02), 0, 1.27), .048 if not FEMALE else .04, .048)
    J["el"+sd] = ((x*(S+.035), .01, 1.14), .036, .036)
    J["fa"+sd] = ((x*(S+.04), .025, 1.02), .036 if not FEMALE else .031, .033)
    J["wr"+sd] = ((x*(S+.045), .04, .91), .025, .02)
    J["hip"+sd] = ((x*.09, 0, .93), .085, .085)
    J["th"+sd] = ((x*.095, .005, .73), .072 if not FEMALE else .068, .072)
    J["kn"+sd] = ((x*.095, .01, .52), .05, .05)
    J["calf"+sd] = ((x*.095, -.005, .36), .052, .052)
    J["an"+sd] = ((x*.095, 0, .1), .032, .032)
    J["toe"+sd] = ((x*.1, .14, .03), .035, .02)
EDGES = [("pelvis","waist"),("waist","chest"),("chest","neckb"),("neckb","neckt")]
for sd in "LR":
    EDGES += [("chest","clav"+sd),("clav"+sd,"sh"+sd),("sh"+sd,"bic"+sd),("bic"+sd,"el"+sd),("el"+sd,"fa"+sd),("fa"+sd,"wr"+sd),
              ("pelvis","hip"+sd),("hip"+sd,"th"+sd),("th"+sd,"kn"+sd),("kn"+sd,"calf"+sd),("calf"+sd,"an"+sd),("an"+sd,"toe"+sd)]
names = list(J)
me = bpy.data.meshes.new("body")
me.from_pydata([J[n][0] for n in names], [(names.index(a), names.index(b)) for a, b in EDGES], [])
body = bpy.data.objects.new("Body", me); sc.collection.objects.link(body)
sk = body.modifiers.new("skin", "SKIN"); sk.use_smooth_shade = True
for i, n in enumerate(names):
    body.data.skin_vertices[0].data[i].radius = (J[n][1], J[n][2])
body.data.skin_vertices[0].data[names.index("pelvis")].use_root = True
sub = body.modifiers.new("sub", "SUBSURF"); sub.levels = 2; sub.render_levels = 3
body.data.materials.append(SKIN)

# armature (rig) skin-modifier se — chalne/haath hilane ke liye haddiyan
bpy.context.view_layer.objects.active = body; body.select_set(True)
try:
    bpy.ops.object.skin_armature_create(modifier="skin"); RIG = True
except Exception as e:
    RIG = False; print("rig skip", e)

# ---------- HAATH: hatheli + 5 ungliyan ----------
def hand(x):
    w = Vector((x*(S+.045), .045, .885))
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts: v.co = Vector((v.co.x*.05, v.co.y*.022, v.co.z*.07)) + w
    o = smooth(obj_from_bm("palm", bm, SKIN), 2)
    for k in range(4):
        fx = (k - 1.5) * .0125 * x; L = (.055, .062, .058, .047)[k]
        bpy.ops.mesh.primitive_cylinder_add(radius=.0065, depth=L, location=(w.x+fx, w.y+.002, w.z-.035-L/2))
        f = bpy.context.object; f.data.materials.append(SKIN); bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.0068, location=(w.x+fx, w.y+.002, w.z-.035-L))
        bpy.context.object.data.materials.append(SKIN); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_cylinder_add(radius=.008, depth=.045, location=(w.x-x*.028, w.y+.018, w.z-.02), rotation=(0.5, x*0.4, 0))
    bpy.context.object.data.materials.append(SKIN); bpy.ops.object.shade_smooth()
for x in (1, -1): hand(x)

# ---------- SIR: chehra (sculpt jaisa: vertices ko khiskakar) ----------
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=48, radius=1, location=(0, 0, 1.64))
head = bpy.context.object; head.name = "Head"; head.data.materials.append(SKIN)
for v in head.data.vertices:
    c = v.co.copy()
    x, y, z = c.x, c.y, c.z
    sx, sy, sz = .088, .1, .112
    if z < -.1:                                   # jabda aur thodi patli
        t = min(1, (-z - .1) / .9)
        sx *= 1 - .38*t*t * (1.0 if not FEMALE else 1.12); sy *= 1 - .12*t
    if y > .55 and abs(z) < .35: sy *= 1 + .05*(1-abs(z)/.35)  # gaal ki haddi aage
    if y > .3 and .05 < z < .3 and abs(x) < .55: sy *= .93     # aankh ke gaddhe
    p = Vector((x*sx, y*sy, z*sz))
    if y > .85 and -.25 < z < .12 and abs(x) < .18:          # naak
        n = (1 - abs(x)/.18) * (1 - abs(z+.07)/.19)
        p.y += .028 * max(0, n) * (1.0 if not FEMALE else .8)
    if y > .7 and z < -.55 and abs(x) < .35: p.y += .01*(1-abs(x)/.35)  # thodi
    v.co = p
smooth(head, 1); bpy.ops.object.shade_smooth()
for sd in (1, -1):  # kaan
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(sd*.087, -.005, 1.635))
    e = bpy.context.object; e.scale = (.011, .02, .029); e.data.materials.append(SKIN); bpy.ops.object.shade_smooth()
    # aankh: safed gola + putli + pupil
    ex, ey, ez = sd*.034, .078, 1.655
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.0175 if not FEMALE else .019, location=(ex, ey, ez))
    bpy.context.object.data.materials.append(EYEW); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.0095, location=(ex, ey+.012, ez))
    i = bpy.context.object; i.scale = (1, .45, 1); i.data.materials.append(IRIS); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.0048, location=(ex, ey+.0165, ez))
    pp = bpy.context.object; pp.scale = (1, .4, 1); pp.data.materials.append(PUPIL)
    # upar ki palak
    bpy.ops.mesh.primitive_torus_add(major_radius=.0185, minor_radius=.0028, location=(ex, ey+.004, ez+.003), rotation=(math.radians(80), 0, 0))
    lid = bpy.context.object; lid.scale = (1.05, 1, .6); lid.data.materials.append(HAIR)
    # bhaunh
    bpy.ops.mesh.primitive_cylinder_add(radius=.0045 if not FEMALE else .003, depth=.034, location=(sd*.036, .089, 1.683), rotation=(0, math.radians(90 - sd*8), 0))
    b = bpy.context.object; b.data.materials.append(HAIR); bpy.ops.object.shade_smooth()
# honth
for z, sc_ in ((1.578, (.022, .009, .006)), (1.568, (.019, .009, .0072))):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, .093, z))
    l = bpy.context.object; l.scale = sc_; l.data.materials.append(LIP); bpy.ops.object.shade_smooth()

# ---------- BAAL: asli lat (particle hair, Cycles mein strand render) ----------
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1, location=(0, -.004, 1.655))
scalp = bpy.context.object; scalp.name = "Scalp"; scalp.scale = (.092, .104, .114); scalp.data.materials.append(HAIR)
bpy.ops.object.transform_apply(scale=True)
bm = bmesh.new(); bm.from_mesh(scalp.data)
cut = [v for v in bm.verts if (v.co.z < 1.655 - .02 and v.co.y > .03) or v.co.z < 1.655 - (.06 if not FEMALE else -.2)
       or (v.co.y > .07 and v.co.z < 1.655 + .045)]
if FEMALE: cut = [v for v in bm.verts if (v.co.y > .03 and v.co.z < 1.655 + .04) and abs(v.co.x) < .075 or (v.co.y > .07 and v.co.z < 1.70)]
bmesh.ops.delete(bm, geom=cut, context="VERTS"); bm.to_mesh(scalp.data); bm.free()
bpy.ops.object.shade_smooth()
ps = scalp.modifiers.new("hair", "PARTICLE_SYSTEM").particle_system.settings
ps.type = "HAIR"; ps.count = 1800; ps.hair_length = .07 if not FEMALE else .32
ps.child_type = "INTERPOLATED"; ps.rendered_child_count = 12; ps.child_length = 1
ps.clump_factor = .7; ps.child_radius = .015; ps.roughness_1 = .004; ps.kink = "WAVE" if FEMALE else "NO"
ps.use_advanced_hair = True; ps.normal_factor = .02; ps.object_align_factor = (0, -.035, -.03) if not FEMALE else (0, -.02, -.2); ps.factor_random = .004

ps.material_slot = "hair"; ps.root_radius = .9 if not FEMALE else .7
ps.display_step = 4; ps.render_step = 5
scalp.particle_systems[0].settings.effector_weights.gravity = 1

# ---------- KAPDE: alag mesh (sharir se thoda bada, solidify = kapde ki motai) ----------
def cloth_from_body(name, m, zmin, zmax, inflate, arms_to=None):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); me2 = bpy.data.meshes.new_from_object(ev)
    o = bpy.data.objects.new(name, me2); sc.collection.objects.link(o)
    bm = bmesh.new(); bm.from_mesh(me2)
    kill = [v for v in bm.verts if not (zmin < v.co.z < zmax) or (arms_to and abs(v.co.x) > arms_to)]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    for v in bm.verts: v.co += v.normal * inflate
    bm.to_mesh(me2); bm.free()
    o.data.materials.clear(); o.data.materials.append(m)
    so = o.modifiers.new("thick", "SOLIDIFY"); so.thickness = .006
    for p in o.data.polygons: p.use_smooth = True
    return o
if not FEMALE:
    shirt = cloth_from_body("Shirt", SHIRT, .93, 1.47, .012, arms_to=S + .06)
    pant = cloth_from_body("Pant", PANT, .09, 1.0, .01)
    # collar + button
    bpy.ops.mesh.primitive_torus_add(major_radius=.06, minor_radius=.012, location=(0, .0, 1.455))
    bpy.context.object.data.materials.append(SHIRT)
    for k in range(5):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.007, location=(0, .118 - k*.002, 1.38 - k*.085))
        bpy.context.object.data.materials.append(EYEW)
else:
    blouse = cloth_from_body("Blouse", SHIRT, 1.12, 1.47, .01, arms_to=S + .05)
    # saree: plete (pleats) wala alag kapda
    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=.16, depth=1.0, location=(0, 0, .58), end_fill_type="NOTHING")
    sar = bpy.context.object; sar.name = "Saree"; sar.data.materials.append(SHIRT)
    for v in sar.data.vertices:
        t = (v.co.z + .5)  # 0 neeche .. 1 upar
        r = .16 + (1 - t) * .09
        ang = math.atan2(v.co.y, v.co.x)
        front = max(0, math.cos(ang - math.pi/2))
        pleat = .012 * math.sin(ang * 40) * front * (1 - t*.5) + .004*math.sin(ang*9)
        v.co.x = math.cos(ang) * (r + pleat); v.co.y = math.sin(ang) * (r + pleat)
    sub2 = sar.modifiers.new("sub", "SUBSURF"); sub2.levels = 1; sub2.render_levels = 2
    so = sar.modifiers.new("thick", "SOLIDIFY"); so.thickness = .005
    bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_torus_add(major_radius=.25, minor_radius=.009, location=(0, 0, .09))
    bpy.context.object.data.materials.append(GOLD)
    # pallu: kandhe se tirchha kapda
    bpy.ops.mesh.primitive_plane_add(size=1, location=(.02, .06, 1.2), rotation=(0, math.radians(-33), 0))
    pal = bpy.context.object; pal.scale = (.12, .01, .42); pal.data.materials.append(SHIRT)
    bpy.ops.object.transform_apply(scale=True)
    sw = pal.modifiers.new("fold", "WAVE"); sw.height = .008; sw.width = .03; sw.use_x = True; sw.use_y = False
    so = pal.modifiers.new("thick", "SOLIDIFY"); so.thickness = .006
    sd = pal.modifiers.new("sub", "SUBSURF"); sd.levels = 2
    # khule baal peeche
# joote
for x in (1, -1):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(x*.098, .06, .045))
    s_ = bpy.context.object; s_.scale = (.048, .12, .045); s_.data.materials.append(SHOE); bpy.ops.object.shade_smooth()

# ---------- ZAMEEN, ROSHNI, CAMERA ----------
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
g = bpy.context.object; g.data.materials.append(mat("ground", (.32, .5, .26), .9))
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (.55, .7, .95, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = .6
bpy.ops.object.light_add(type="AREA", location=(1.6, 2.2, 2.4)); k = bpy.context.object
k.data.energy = 260; k.data.size = 1.5; k.rotation_euler = (math.radians(-55), 0, math.radians(145))
bpy.ops.object.light_add(type="AREA", location=(-1.8, 1.2, 1.8)); f = bpy.context.object
f.data.energy = 90; f.data.size = 2; f.rotation_euler = (math.radians(-60), 0, math.radians(-125))
bpy.ops.object.light_add(type="AREA", location=(0, -2, 2.2)); r = bpy.context.object
r.data.energy = 140; r.data.size = 1; r.rotation_euler = (math.radians(55), 0, 0)

ang = {"front": 0, "side": 90, "back": 180, "threeq": 35, "face": 20}[VIEW]
dist, tz = (3.6, 1.0) if VIEW != "face" else (1.1, 1.58)
a = math.radians(ang)
bpy.ops.object.camera_add(location=(math.sin(a)*dist, math.cos(a)*dist, tz + .05))
cam = bpy.context.object; sc.camera = cam
cam.data.lens = 50
tc = cam.constraints.new("TRACK_TO")
bpy.ops.object.empty_add(location=(0, 0, tz)); tc.target = bpy.context.object
tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"

sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 48
sc.cycles.use_denoising = True
sc.render.resolution_x = 540; sc.render.resolution_y = 960
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDER_OK", OUT, "rig=", RIG)
