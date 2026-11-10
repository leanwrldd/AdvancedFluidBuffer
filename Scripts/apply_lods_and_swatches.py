# Adds LOD1/LOD2 to SM_AdvancedFluidBuffer and gives its two paint slots swatch-aware materials.
# Re-runnable. Touches ONLY the main body mesh and materials under /AdvancedFluidBuffer/Materials.
# It never loads or saves Build_AdvancedFluidBuffer.
#
# RUN ORDER: create_assets.py first (it re-imports the mesh, which drops the LODs and puts the plain
# M_ materials back on the slots), then this script.
#
# This must run in the FULL editor binary, not the pythonscript commandlet: every LOD helper
# (StaticMeshEditorSubsystem.import_lod, set_lod_screen_sizes, ...) returns -1 in the commandlet.
#   "C:\Program Files\Unreal Engine - CSS\Engine\Binaries\Win64\UnrealEditor.exe" C:\SF\SML\FactoryGame.uproject
#       -ExecutePythonScript=C:\SF\Mods\AdvancedFluidBuffer\Scripts\apply_lods_and_swatches.py
#       -unattended -nosplash -nullrhi -NoLogTimes -abslog=<log>
# The script quits the editor when it is done (about 30 s). Set AFB_VERIFY_ONLY=1 to only log what a
# fresh load sees (LOD count, triangles per LOD, slot -> material) without changing anything.
import os
import traceback
import unreal

MOD = "AdvancedFluidBuffer"
ROOT = f"/{MOD}"
EXPORT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Art", "Export")
MESH_PATH = f"{ROOT}/Mesh/SM_{MOD}"

# Screen size = fraction of the screen height the mesh bounds cover. The tank is about 6 m x 8 m,
# so LOD1 takes over once it is under 40% of the screen height and LOD2 under 12%.
LOD_SCREEN_SIZES = [1.0, 0.40, 0.12]

# Paint slot -> (instance name, UseSecondary, metallic, roughness). Metallic/roughness are the values
# create_assets.py already used for these slots.
PAINT_SLOTS = {
    "M_Paint_Primary": (f"MI_{MOD}_Paint_Primary", 0.0, 0.35, 0.40),
    "M_Paint_Secondary": (f"MI_{MOD}_Paint_Secondary", 1.0, 0.45, 0.55),   # was 0.75 / 0.40, too shiny
}
PRIMARY_DEFAULT = (0.85, 0.19, 0.025)       # linear, the old plain material colours
SECONDARY_DEFAULT = (0.045, 0.058, 0.07)
MASTER_NAME = f"M_{MOD}_Swatch"

lib = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary


def log(msg):
    unreal.log(f"AFBLS: {msg}")


def find(path):
    """Existing asset or None. does_asset_exist alone misses unscanned plugin content."""
    name = path.rsplit("/", 1)[1]
    asset = lib.load_asset(path) if lib.does_asset_exist(path) else None
    return asset or unreal.load_object(None, f"{path}.{name}")


# --- LODs -----------------------------------------------------------------------------------
def apply_lods(mesh):
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if sub is None:
        raise RuntimeError("StaticMeshEditorSubsystem is None: this is the commandlet, run it in UnrealEditor.exe")
    for index, suffix in ((1, "LOD1"), (2, "LOD2")):
        fbx = os.path.join(EXPORT, f"SM_{MOD}_{suffix}.fbx")
        if not os.path.exists(fbx):
            raise RuntimeError(f"missing {fbx}")
        result = sub.import_lod(mesh, index, fbx)
        log(f"import_lod {index} <- {suffix}.fbx returned {result}")
        if result != index:
            raise RuntimeError(f"import_lod {index} failed (see LogStaticMeshEditorSubsystem / LogFbx above)")
    # set_lod_screen_sizes also switches off the automatic screen size computation.
    ok = sub.set_lod_screen_sizes(mesh, LOD_SCREEN_SIZES)
    log(f"set_lod_screen_sizes {LOD_SCREEN_SIZES} -> {ok}")


# --- Swatch materials -----------------------------------------------------------------------
def scalar_param(mat, name, default, x, y, primitive_index=None):
    node = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", default)
    if primitive_index is not None:
        # Same mechanism as the game's MF_GetPrimaryColor / MF_GetSecondaryColor: the proxy mesh
        # component receives the swatch colour as custom primitive data floats 0-5.
        node.set_editor_property("use_custom_primitive_data", True)
        node.set_editor_property("primitive_data_index", primitive_index)
    return node


def swatch_color(mat, label, rgb_default, first_index, data_index, y):
    """float3 = per-instance custom data (instanced path) or custom primitive data (plain mesh path)."""
    channels = [scalar_param(mat, f"{label}_Color_{c}", rgb_default[i], -1300, y + i * 110, first_index + i)
                for i, c in enumerate("RGB")]
    rg = mel.create_material_expression(mat, unreal.MaterialExpressionAppendVector, -1050, y)
    mel.connect_material_expressions(channels[0], "", rg, "A")
    mel.connect_material_expressions(channels[1], "", rg, "B")
    rgb = mel.create_material_expression(mat, unreal.MaterialExpressionAppendVector, -900, y + 50)
    mel.connect_material_expressions(rg, "", rgb, "A")
    mel.connect_material_expressions(channels[2], "", rgb, "B")
    per_instance = mel.create_material_expression(mat, unreal.MaterialExpressionPerInstanceCustomData3Vector, -720, y + 50)
    per_instance.set_editor_property("data_index", data_index)
    linked = False
    for pin in ("DefaultValue", "Default Value", "InputDefaultValue"):
        if mel.connect_material_expressions(rgb, "", per_instance, pin):
            linked = True
            break
    log(f"{label}: PerInstanceCustomData3Vector idx {data_index}, default input linked={linked}")
    if not linked:
        raise RuntimeError(f"could not link default input of the {label} per-instance node")
    return per_instance


def build_master(mat):
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    primary = swatch_color(mat, "PrimaryPaintMetal", PRIMARY_DEFAULT, 0, 0, 0)
    secondary = swatch_color(mat, "SecondaryPaintedMetal", SECONDARY_DEFAULT, 3, 3, 500)
    pick = scalar_param(mat, "UseSecondary", 0.0, -520, 300)
    mix = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -300, 250)
    mel.connect_material_expressions(primary, "", mix, "A")
    mel.connect_material_expressions(secondary, "", mix, "B")
    mel.connect_material_expressions(pick, "", mix, "Alpha")
    mel.connect_material_property(mix, "", unreal.MaterialProperty.MP_BASE_COLOR)
    metallic = scalar_param(mat, "Metallic", 0.35, -300, 450)
    rough = scalar_param(mat, "Roughness", 0.40, -300, 560)
    mel.connect_material_property(metallic, "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)


def ensure_master():
    path = f"{ROOT}/Materials/{MASTER_NAME}"
    mat = find(path)
    if mat is not None:
        # Rebuilding in place leaves the old expressions behind as orphan sub-objects in the saved
        # package (the transaction buffer keeps them alive; seen 2026-11-10). So an existing master is
        # reused. To change its graph, delete M_AdvancedFluidBuffer_Swatch.uasset and the two MI_
        # files on disk first, then run this script again.
        return mat
    mat = tools.create_asset(MASTER_NAME, f"{ROOT}/Materials", unreal.Material, unreal.MaterialFactoryNew())
    build_master(mat)
    mel.recompile_material(mat)
    lib.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


def ensure_instance(name, parent, use_secondary, metallic, roughness):
    path = f"{ROOT}/Materials/{name}"
    mi = find(path)
    if mi is None:
        mi = tools.create_asset(name, f"{ROOT}/Materials", unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, parent)
    mel.set_material_instance_scalar_parameter_value(mi, "UseSecondary", use_secondary)
    mel.set_material_instance_scalar_parameter_value(mi, "Metallic", metallic)
    mel.set_material_instance_scalar_parameter_value(mi, "Roughness", roughness)
    mel.update_material_instance(mi)
    lib.save_loaded_asset(mi, only_if_is_dirty=False)
    return mi


def apply_swatch_materials(mesh):
    master = ensure_master()
    instances = {key: ensure_instance(name, master, sec, met, rgh)
                 for key, (name, sec, met, rgh) in PAINT_SLOTS.items()}
    for i, slot in enumerate(mesh.get_editor_property("static_materials")):
        slot_name = str(slot.get_editor_property("material_slot_name"))
        if slot_name in instances:
            mesh.set_material(i, instances[slot_name])
            log(f"slot {i} '{slot_name}' -> {instances[slot_name].get_name()}")
        else:
            # Every material on a mesh that goes into an instanced component needs this flag.
            mat = mesh.get_material(i)
            if isinstance(mat, unreal.Material):
                mat.set_editor_property("used_with_instanced_static_meshes", True)
                lib.save_loaded_asset(mat, only_if_is_dirty=False)
                log(f"slot {i} '{slot_name}' keeps {mat.get_name()} (instanced-mesh usage flag set)")


# --- Report ---------------------------------------------------------------------------------
def report(mesh):
    n = mesh.get_num_lods()
    log(f"VERIFY lods={n}")
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if sub is not None:
        log(f"VERIFY screen sizes (render data) = {[round(s, 4) for s in sub.get_lod_screen_sizes(mesh)]}")
    slots = [str(s.get_editor_property("material_slot_name")) for s in mesh.get_editor_property("static_materials")]
    for lod in range(n):
        sections = mesh.get_num_sections(lod)
        mapping = []
        for sec in range(sections):
            slot = sub.get_lod_material_slot(mesh, lod, sec)
            mapping.append(slots[slot] if 0 <= slot < len(slots) else slot)
        log(f"VERIFY LOD{lod}: triangles={mesh.get_num_triangles(lod)} vertices={mesh.get_num_vertices(lod)} "
            f"sections={sections} section_slots={mapping}")
    box = mesh.get_bounding_box()
    log(f"VERIFY bounds min={box.min} max={box.max}")
    for i, slot in enumerate(mesh.get_editor_property("static_materials")):
        mat = slot.get_editor_property("material_interface")
        parent = mat.get_editor_property("parent").get_name() if isinstance(mat, unreal.MaterialInstanceConstant) and mat.get_editor_property("parent") else None
        log(f"VERIFY slot {i} '{slots[i]}' -> {mat.get_name() if mat else None} ({mat.get_class().get_name() if mat else ''}) parent={parent}")
    master = find(f"{ROOT}/Materials/{MASTER_NAME}")
    if master is not None:
        log(f"VERIFY {MASTER_NAME}: instanced_ok={master.get_editor_property('used_with_instanced_static_meshes')} "
            f"scalars={list(mel.get_scalar_parameter_names(master))}")
        for ex in unreal.ObjectIterator(unreal.MaterialExpressionScalarParameter):
            if ex.get_outer() == master and ex.get_editor_property("use_custom_primitive_data"):
                log(f"VERIFY   {ex.get_editor_property('parameter_name')} primitive_data_index={ex.get_editor_property('primitive_data_index')}")
        for ex in unreal.ObjectIterator(unreal.MaterialExpressionPerInstanceCustomData3Vector):
            if ex.get_outer() == master:
                ins = [i.get_class().get_name() if i else None for i in mel.get_inputs_for_material_expression(master, ex)]
                log(f"VERIFY   PerInstanceCustomData3Vector data_index={ex.get_editor_property('data_index')} inputs={ins}")


def main():
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([ROOT], True)
    mesh = find(MESH_PATH)
    if mesh is None:
        raise RuntimeError(f"{MESH_PATH} not found; run create_assets.py first")
    if os.environ.get("AFB_VERIFY_ONLY") != "1":
        apply_lods(mesh)
        apply_swatch_materials(mesh)
        lib.save_loaded_asset(mesh, only_if_is_dirty=False)
        mesh = unreal.EditorAssetLibrary.load_asset(MESH_PATH)
    report(mesh)
    log("done")


try:
    main()
except Exception:
    unreal.log_error("AFBLS: FAILED\n" + traceback.format_exc())
finally:
    try:
        unreal.SystemLibrary.quit_editor()
    except Exception:
        pass
