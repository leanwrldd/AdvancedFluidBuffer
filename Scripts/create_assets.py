# Creates every asset the Advanced Fluid Buffer needs, headlessly. Re-runnable: existing assets are
# reused and their properties re-applied. Run through the editor's Python commandlet after the
# editor target is built (see first-package.ps1):
#   UnrealEditor-Cmd.exe C:\SF\SML\FactoryGame.uproject -run=pythonscript
#     -script=C:\SF\Mods\AdvancedFluidBuffer\Scripts\create_assets.py -unattended -nosplash -NoLogTimes
# Inputs: Art/Export/*.fbx (from Art/build_mesh.py in Blender) and Art/Icon_AdvancedFluidBuffer_*.png.
import os
import unreal

MOD = "AdvancedFluidBuffer"
ROOT = f"/{MOD}"
ART = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Art")
EXPORT = os.path.join(ART, "Export")

DISPLAY_NAME = "Advanced Fluid Buffer"
DESCRIPTION = ("Stores up to 400 m\u00b3 of fluid.\n"
               "Free-flow port: fluid moves in and out freely, like a Fluid Buffer.\n"
               "Controlled inlet: accepts fluid only while the tank is below 75%.\n"
               "Controlled outlet: releases fluid only while the tank is above 75%.")
CAPACITY = 400.0
TANK_HEIGHT = 800.0           # roof height of the Blender model [cm]
LIQUID_FLOOR = 90.0           # INTERNAL_FLOOR in build_mesh.py [cm]
PORT_RADIUS = 290.0           # PORT_FACE_RADIUS
LOW_PORT_Z = 175.0
OVERFLOW_Z = 607.5            # 75% of the internal liquid height

INGREDIENTS = [  # (class path, amount)
    ("/Game/FactoryGame/Resource/Parts/SteelPlateReinforced/Desc_SteelPlateReinforced.Desc_SteelPlateReinforced_C", 5),
    ("/Game/FactoryGame/Resource/Parts/Plastic/Desc_Plastic.Desc_Plastic_C", 25),
    ("/Game/FactoryGame/Resource/Parts/CopperSheet/Desc_CopperSheet.Desc_CopperSheet_C", 10),
    ("/Game/FactoryGame/Resource/Parts/CircuitBoard/Desc_CircuitBoard.Desc_CircuitBoard_C", 5),
]
VANILLA_DESC = "/Game/FactoryGame/Buildable/Factory/IndustrialFluidContainer/Desc_IndustrialTank.Desc_IndustrialTank_C"
VANILLA_WIDGET = "/Game/FactoryGame/Buildable/Factory/StorageTank/Widget_PipeStorageTank.Widget_PipeStorageTank_C"
VANILLA_RECIPE = "/Game/FactoryGame/Recipes/Buildings/Recipe_IndustrialTank.Recipe_IndustrialTank_C"

lib = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary


def log(msg):
    unreal.log(f"AFB: {msg}")


def find(path):
    """Existing asset or None. does_asset_exist alone misses unscanned plugin content."""
    name = path.rsplit("/", 1)[1]
    asset = lib.load_asset(path) if lib.does_asset_exist(path) else None
    return asset or unreal.load_object(None, f"{path}.{name}")


def import_file(filename, dest, name, options=None):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", filename)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    if options:
        task.set_editor_property("options", options)
    tools.import_asset_tasks([task])
    return find(f"{dest}/{name}")


def fbx_options(scale=1.0):
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", True)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    data = ui.get_editor_property("static_mesh_import_data")
    data.set_editor_property("combine_meshes", True)
    data.set_editor_property("auto_generate_collision", False)
    data.set_editor_property("one_convex_hull_per_ucx", True)
    data.set_editor_property("generate_lightmap_u_vs", False)
    data.set_editor_property("import_uniform_scale", scale)
    return ui


def import_mesh(name):
    """Imports Art/Export/<name>.fbx. Blender FBX sometimes lands in metres; detect and redo at 100x."""
    path = f"{ROOT}/Mesh/{name}"
    fbx = os.path.join(EXPORT, f"{name}.fbx")
    mesh = import_file(fbx, f"{ROOT}/Mesh", name, fbx_options(1.0))
    ext = mesh.get_bounding_box().max - mesh.get_bounding_box().min
    if max(ext.x, ext.y, ext.z) < 50.0:
        log(f"{name} imported at {ext}, looks like metres; reimporting at 100x")
        mesh.get_editor_property("asset_import_data").set_editor_property("import_uniform_scale", 100.0)
        mesh = import_file(fbx, f"{ROOT}/Mesh", name, fbx_options(100.0))
    box = mesh.get_bounding_box()
    log(f"{name}: bounds min={box.min} max={box.max}")
    return mesh


def import_icon(size):
    name = f"Icon_{MOD}_{size}"
    tex = import_file(os.path.join(ART, f"{name}.png"), f"{ROOT}/Icons", name)
    tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    lib.save_loaded_asset(tex, only_if_is_dirty=False)
    return tex


def material(name, build):
    path = f"{ROOT}/Materials/{name}"
    mat = find(path)
    if mat is None:
        mat = tools.create_asset(name, f"{ROOT}/Materials", unreal.Material, unreal.MaterialFactoryNew())
    else:
        mel.delete_all_material_expressions(mat)
    build(mat)
    mel.recompile_material(mat)
    lib.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def build_liquid(mat):
    # The buildable sets FluidColor from the fluid's descriptor at runtime.
    color = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -400, 0)
    color.set_editor_property("parameter_name", "FluidColor")
    color.set_editor_property("default_value", unreal.LinearColor(0.02, 0.38, 0.55, 1.0))
    mel.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    glow = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -150, 200)
    glow.set_editor_property("const_b", 0.35)
    mel.connect_material_expressions(color, "", glow, "A")
    mel.connect_material_property(glow, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 300)
    rough.set_editor_property("r", 0.15)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)


def build_glass(mat):
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    tint = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
    tint.set_editor_property("constant", unreal.LinearColor(0.7, 0.88, 0.95, 1.0))
    mel.connect_material_property(tint, "", unreal.MaterialProperty.MP_BASE_COLOR)
    alpha = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 200)
    alpha.set_editor_property("r", 0.18)
    mel.connect_material_property(alpha, "", unreal.MaterialProperty.MP_OPACITY)


def create_blueprint(name, parent):
    path = f"{ROOT}/{name}"
    bp = find(path)
    if bp is not None:
        return bp, False
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    return tools.create_asset(name, ROOT, None, factory), True


def cdo(bp):
    return unreal.get_default_object(bp.generated_class())


def set_props(obj, props):
    for key, value in props.items():
        try:
            obj.set_editor_property(key, value)
        except Exception as e:  # report and keep going so one bad name doesn't hide the rest
            unreal.log_error(f"AFB: could not set {obj.get_name()}.{key}: {e}")


# --- Game feature data ----------------------------------------------------------------------
unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([ROOT], True)
if find(f"{ROOT}/{MOD}") is None:
    gfd_cls = unreal.load_class(None, "/Script/FactoryGame.FGGameFeatureData")
    f = unreal.DataAssetFactory()
    f.set_editor_property("data_asset_class", gfd_cls)
    lib.save_loaded_asset(tools.create_asset(MOD, ROOT, gfd_cls, f))
    log("created game feature data")

# --- Art ------------------------------------------------------------------------------------
body = import_mesh(f"SM_{MOD}")
# LODs: every LOD helper (StaticMeshEditorSubsystem, EditorStaticMeshLibrary.import_lod and
# set_lod_from_static_mesh) returns -1 in the commandlet, so LOD1/LOD2 from Art/Export are not
# applied yet. Import them in the editor GUI (Static Mesh editor > LOD Import) when needed.
# Metal physical material on the simple collision, so footsteps and ladder climbing pick a metal
# surface sound instead of the silent default. The SML placeholder resolves to the game's asset.
PHYS_METAL = "/Game/FactoryGame/-Shared/Material/PhysicalMaterial/PhysMat_Metal.PhysMat_Metal"
body.get_editor_property("body_setup").set_editor_property("phys_material", unreal.load_asset(PHYS_METAL))
log(f"body collision: {body.get_editor_property('body_setup').get_editor_property('agg_geom').get_editor_property('convex_elems').__len__()} convex hulls, phys material PhysMat_Metal")
lib.save_loaded_asset(body, only_if_is_dirty=False)
# The FBX importer makes no materials for these Blender slots, so build simple ones matching the
# Blender colours (linear RGB, metallic, roughness) and assign them by slot name.
BODY_COLOURS = {
    "M_Paint_Primary": ((0.85, 0.19, 0.025), 0.35, 0.4),
    "M_Paint_Secondary": ((0.045, 0.058, 0.07), 0.45, 0.55),
    "M_Metal_Detail": ((0.30, 0.35, 0.39), 0.6, 0.55),   # was 0.85 / 0.28, read as chrome in game
    "M_Port_Interior": ((0.009, 0.014, 0.018), 0.1, 0.65),
}


def build_solid(rgb, metallic, roughness):
    def build(mat):
        c = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
        c.set_editor_property("constant", unreal.LinearColor(*rgb, 1.0))
        mel.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
        for value, prop, y in ((metallic, unreal.MaterialProperty.MP_METALLIC, 150),
                               (roughness, unreal.MaterialProperty.MP_ROUGHNESS, 300)):
            k = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, y)
            k.set_editor_property("r", value)
            mel.connect_material_property(k, "", prop)
    return build


def build_hazard(mat):
    # Diagonal black/yellow bands from local position, as the Blender material did.
    pos = mel.create_material_expression(mat, unreal.MaterialExpressionLocalPosition, -900, 0)
    axis = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -900, 150)
    axis.set_editor_property("constant", unreal.LinearColor(1 / 35, 1 / 35, 1.8 / 35, 0))
    dot = mel.create_material_expression(mat, unreal.MaterialExpressionDotProduct, -700, 50)
    mel.connect_material_expressions(pos, "", dot, "A")
    mel.connect_material_expressions(axis, "", dot, "B")
    frac = mel.create_material_expression(mat, unreal.MaterialExpressionFrac, -550, 50)
    mel.connect_material_expressions(dot, "", frac, "")
    band = mel.create_material_expression(mat, unreal.MaterialExpressionRound, -420, 50)
    mel.connect_material_expressions(frac, "", band, "")
    black = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -420, 200)
    black.set_editor_property("constant", unreal.LinearColor(0.012, 0.015, 0.018, 1))
    yellow = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -420, 350)
    yellow.set_editor_property("constant", unreal.LinearColor(0.98, 0.66, 0.025, 1))
    lerp = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -250, 150)
    mel.connect_material_expressions(black, "", lerp, "A")
    mel.connect_material_expressions(yellow, "", lerp, "B")
    mel.connect_material_expressions(band, "", lerp, "Alpha")
    mel.connect_material_property(lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -250, 350)
    rough.set_editor_property("r", 0.45)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)


slots = body.get_editor_property("static_materials")
for i, slot in enumerate(slots):
    slot_name = str(slot.get_editor_property("material_slot_name"))
    key = next((k for k in list(BODY_COLOURS) + ["M_Hazard_Stripe"] if slot_name.startswith(k)), None)
    if key is None:
        unreal.log_error(f"AFB: no material for body slot {i} '{slot_name}'")
        continue
    builder = build_hazard if key == "M_Hazard_Stripe" else build_solid(*BODY_COLOURS[key])
    body.set_material(i, material(f"M_{MOD}_{key[2:]}", builder))
    log(f"body slot {i} '{slot_name}' -> M_{MOD}_{key[2:]}")
lib.save_loaded_asset(body, only_if_is_dirty=False)

liquid_mesh = import_mesh(f"SM_{MOD}_Liquid")
glass_mesh = import_mesh(f"SM_{MOD}_Glass")
liquid_mesh.set_material(0, material(f"M_{MOD}_Liquid", build_liquid))
glass_mesh.set_material(0, material(f"M_{MOD}_Glass", build_glass))
for m in (liquid_mesh, glass_mesh):
    lib.save_loaded_asset(m, only_if_is_dirty=False)
icon_small, icon_big = import_icon(256), import_icon(512)

# The FBX import can mirror the model. The 75% port is the only thing sticking out on one X side,
# so read which side it landed on from the bounds instead of trusting Blender's +X.
bounds = body.get_bounding_box()
OVERFLOW_SIGN = 1.0 if bounds.max.x >= -bounds.min.x else -1.0
log(f"overflow port is on the {'+' if OVERFLOW_SIGN > 0 else '-'}X side")

# --- Buildable ------------------------------------------------------------------------------
build_cls_native = unreal.load_class(None, f"/Script/{MOD}.{MOD}")
build_bp, fresh = create_blueprint(f"Build_{MOD}", build_cls_native)
if fresh:
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    root = sub.k2_gather_subobject_data_for_blueprint(build_bp)[0]
    BFL = unreal.SubobjectDataBlueprintFunctionLibrary
    pipe_cls = unreal.load_class(None, "/Script/FactoryGame.FGPipeConnectionComponent")
    factory_pipe_cls = unreal.load_class(None, "/Script/FactoryGame.FGPipeConnectionFactory")

    def add(name, cls, location, yaw=0.0, tags=()):
        params = unreal.AddNewSubobjectParams(parent_handle=root, new_class=cls, blueprint_context=build_bp)
        handle, fail = sub.add_new_subobject(params)
        if not BFL.is_handle_valid(handle):
            raise RuntimeError(f"adding {name} failed: {fail}")
        sub.rename_subobject(handle, unreal.Text(name))
        comp = BFL.get_object_for_blueprint(BFL.get_data(handle), build_bp)
        comp.set_editor_property("relative_location", unreal.Vector(*location))
        comp.set_editor_property("relative_rotation", unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        if tags:
            comp.set_editor_property("component_tags", [unreal.Name(t) for t in tags])
        return comp

    # Colorable mesh component, as on vanilla buildings (ensure_paintable_mesh sets it up).
    add("Mesh", unreal.load_class(None, "/Script/FactoryGame.FGColoredInstanceMeshProxy"), (0, 0, 0))
    add("Glass", unreal.StaticMeshComponent, (0, 0, 0)).set_editor_property("static_mesh", glass_mesh)
    liquid = add("Liquid", unreal.StaticMeshComponent, (0, 0, LIQUID_FLOOR), tags=[f"{MOD}_Liquid"])
    liquid.set_editor_property("static_mesh", liquid_mesh)
    # Socket transforms from build_mesh.py: the two low ports face +Y/-Y, the 75% one faces +/-X.
    add("FreeFlow", pipe_cls, (0, PORT_RADIUS, LOW_PORT_Z), 90.0, ["FreeFlow"]) \
        .set_editor_property("m_pipe_connection_type", unreal.PipeConnectionType.PCT_ANY)
    add("ControlledInlet", factory_pipe_cls, (0, -PORT_RADIUS, LOW_PORT_Z), -90.0, ["ControlledInlet"]) \
        .set_editor_property("m_pipe_connection_type", unreal.PipeConnectionType.PCT_CONSUMER)
    add("ControlledOutlet", factory_pipe_cls, (OVERFLOW_SIGN * PORT_RADIUS, 0, OVERFLOW_Z),
        0.0 if OVERFLOW_SIGN > 0 else 180.0, ["ControlledOutlet"]) \
        .set_editor_property("m_pipe_connection_type", unreal.PipeConnectionType.PCT_PRODUCER)
    log("added components")

# Climbable ladder (vanilla BP_LadderComponent); idempotent, also fixes up an existing Blueprint.
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import ladder
ladder.ensure_ladder(build_bp, body)


def ensure_paintable_mesh():
    """Swatch painting: vanilla buildings draw their main mesh with FGColoredInstanceMeshProxy,
    which feeds the swatch colours to the material as custom primitive data. Give the "Mesh"
    component vanilla's settings.
    The swatch materials themselves come from apply_lods_and_swatches.py."""
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    BFL = unreal.SubobjectDataBlueprintFunctionLibrary
    proxy_cls = unreal.load_class(None, "/Script/FactoryGame.FGColoredInstanceMeshProxy")
    for h in sub.k2_gather_subobject_data_for_blueprint(build_bp):
        comp = BFL.get_object_for_blueprint(BFL.get_data(h), build_bp)
        if comp is None or not comp.get_name().startswith("Mesh"):
            continue
        if comp.get_class() != proxy_cls:
            # change_subobject_class only works on native components, and Mesh is the Blueprint's
            # root with everything attached to it. Everything here is generated, so recreate it.
            unreal.log_error(f"AFB: Mesh is a {comp.get_class().get_name()}, not FGColoredInstanceMeshProxy. "
                             f"Delete Content/Build_{MOD}.uasset and rerun to rebuild the Blueprint.")
            return
        comp.set_editor_property("static_mesh", body)
        set_props(comp, {
            "m_block_instancing": True,   # as on both vanilla tanks, so the proxy itself renders
            "m_num_custom_data_floats": 20,
            "m_optimization_category": unreal.DistanceCullCategory.FGDCC_BUILDING_BIG,
        })
        return
    unreal.log_error("AFB: no Mesh component found")


ensure_paintable_mesh()

unreal.BlueprintEditorLibrary.compile_blueprint(build_bp)
# FGClearanceData fields are EditDefaultsOnly, so Python refuses to set them on a loose struct;
# import_text bypasses that check.
clearance = unreal.FGClearanceData()
clearance.import_text("(Type=CT_Default,ClearanceBox=(Min=(X=-300,Y=-300,Z=0),Max=(X=300,Y=300,Z=900),IsValid=True))")
set_props(cdo(build_bp), {
    "m_display_name": unreal.Text(DISPLAY_NAME),
    "m_description": unreal.Text(DESCRIPTION),
    "m_storage_capacity": CAPACITY,
    "m_stacking_height": TANK_HEIGHT,
    # The vanilla Fluid Buffer / Industrial Fluid Buffer UI; it reads AFGBuildablePipeReservoir.
    "m_is_useable": True,
    "m_interact_widget_soft_class": unreal.load_class(None, VANILLA_WIDGET),
    "m_output_threshold": 0.75,
    "m_input_threshold": 0.75,
    "m_clearance_data": [clearance],
})
lib.save_loaded_asset(build_bp, only_if_is_dirty=False)

# --- Descriptor (build menu entry), copying the Industrial Fluid Buffer's menu placement -----
vanilla_desc = unreal.get_default_object(unreal.load_class(None, VANILLA_DESC))
desc_bp, _ = create_blueprint(f"Desc_{MOD}", unreal.load_class(None, "/Script/FactoryGame.FGBuildingDescriptor"))
unreal.BlueprintEditorLibrary.compile_blueprint(desc_bp)
set_props(cdo(desc_bp), {
    "m_buildable_class": build_bp.generated_class(),
    "m_display_name": unreal.Text(DISPLAY_NAME),
    "m_description": unreal.Text(DESCRIPTION),
    "m_small_icon": icon_small,
    "m_persistent_big_icon": icon_big,
    "m_category": vanilla_desc.get_editor_property("m_category"),
    "m_sub_categories": vanilla_desc.get_editor_property("m_sub_categories"),
    "m_menu_priority": vanilla_desc.get_editor_property("m_menu_priority") + 0.1,
    # Quick-switch wheel (E): without a group it lands with the ungrouped Dimensional Depot
    # uploader. Both vanilla fluid buffers are in SwapGroup_2.
    "m_quick_switch_group": vanilla_desc.get_editor_property("m_quick_switch_group"),
})
lib.save_loaded_asset(desc_bp, only_if_is_dirty=False)

# --- Recipe (built with the build gun, like the Industrial Fluid Buffer) ----------------------
vanilla_recipe = unreal.get_default_object(unreal.load_class(None, VANILLA_RECIPE))
recipe_bp, _ = create_blueprint(f"Recipe_{MOD}", unreal.load_class(None, "/Script/FactoryGame.FGRecipe"))
unreal.BlueprintEditorLibrary.compile_blueprint(recipe_bp)


def amount(cls, n):
    a = unreal.ItemAmount()
    a.set_editor_property("item_class", cls)
    a.set_editor_property("amount", n)
    return a


set_props(cdo(recipe_bp), {
    "m_ingredients": [amount(unreal.load_class(None, p), n) for p, n in INGREDIENTS],
    "m_product": [amount(desc_bp.generated_class(), 1)],
    "m_produced_in": vanilla_recipe.get_editor_property("m_produced_in"),
    "m_manufactoring_duration": vanilla_recipe.get_editor_property("m_manufactoring_duration"),
})
lib.save_loaded_asset(recipe_bp, only_if_is_dirty=False)

# --- Report what actually got saved ----------------------------------------------------------
b, d, r = cdo(build_bp), cdo(desc_bp), cdo(recipe_bp)
log(f"build: name={b.get_editor_property('m_display_name')} capacity={b.get_editor_property('m_storage_capacity')} height={b.get_editor_property('m_stacking_height')} useable={b.get_editor_property('m_is_useable')} widget={b.get_editor_property('m_interact_widget_soft_class')} "
    f"clearance={[c.export_text() for c in b.get_editor_property('m_clearance_data')]}")
log(f"desc: buildable={d.get_editor_property('m_buildable_class')} category={d.get_editor_property('m_category')} "
    f"subcats={d.get_editor_property('m_sub_categories')} priority={d.get_editor_property('m_menu_priority')} "
    f"quickSwitch={d.get_editor_property('m_quick_switch_group')}")
log("recipe: " + ", ".join(f"{i.get_editor_property('amount')}x {i.get_editor_property('item_class').get_name()}"
                           for i in r.get_editor_property('m_ingredients'))
    + f" -> {r.get_editor_property('m_product')[0].get_editor_property('item_class').get_name()}"
    + f" producedIn={r.get_editor_property('m_produced_in')}")
sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
BFL = unreal.SubobjectDataBlueprintFunctionLibrary
for h in sub.k2_gather_subobject_data_for_blueprint(build_bp):
    o = BFL.get_object_for_blueprint(BFL.get_data(h), build_bp)
    if isinstance(o, unreal.SceneComponent):
        loc, rot = o.get_editor_property("relative_location"), o.get_editor_property("relative_rotation")
        extra = ""
        if isinstance(o, unreal.FGPipeConnectionComponent):
            extra = f" type={o.get_editor_property('m_pipe_connection_type')}"
        elif isinstance(o, unreal.StaticMeshComponent):
            m = o.get_editor_property("static_mesh")
            extra = f" mesh={m.get_name() if m else None}"
        log(f"component {o.get_name()} ({o.get_class().get_name()}) at ({loc.x:.1f}, {loc.y:.1f}, {loc.z:.1f}) "
            f"yaw {rot.yaw:.0f} tags={[str(t) for t in o.get_editor_property('component_tags')]}{extra}")
log("done")
