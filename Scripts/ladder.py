# Climbable ladder for Build_AdvancedFluidBuffer, using the game's BP_LadderComponent (a
# UFGLadderComponent, i.e. a box trigger the player climbs inside). Settings copied from the vanilla
# Fluid Buffer's ladders: box extent (32, 50, height/2), centred on the ladder, OverlapAllDynamic,
# component +X pointing into the tank (read from the placeholders 2026-11-10).
#
# Used two ways:
#   - imported by create_assets.py (ensure_ladder after the components are built)
#   - run alone through the commandlet: only touches the Build Blueprint, not meshes or materials.
import math
import os
import re
import unreal

MOD = "AdvancedFluidBuffer"
LADDER_CLASS = "/Game/FactoryGame/Buildable/-Shared/Ladder/BP_LadderComponent.BP_LadderComponent_C"
MODEL_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Art", "build_mesh.py")


def _model_value(name, default):
    """Reads `NAME = <number>` or `NAME = math.radians(<number>)` from Art/build_mesh.py, so the
    ladder follows the model when it is redesigned. Returns degrees for radians() values."""
    try:
        text = open(MODEL_SCRIPT, encoding="utf-8").read()
    except OSError:
        return default
    m = re.search(rf"^{name}\s*=\s*(?:math\.radians\()?\s*(-?[\d.]+)", text, re.M)
    return float(m.group(1)) if m else default


# Blender coordinates, cm, taken from the model script.
LADDER_ANGLE_BLENDER = math.radians(_model_value("LADDER_ANGLE", -140.0))
LADDER_RADIUS = _model_value("LADDER_RADIUS", 250.0)      # rung line
LADDER_HALF_WIDTH = 50.0      # vanilla box half width; the model's ladder is 70 cm wide
LADDER_HALF_DEPTH = 32.0      # vanilla
LADDER_TOP = _model_value("ROOF_Z", 800.0) + 20.0          # a little above the roof so the climb ends on it
LADDER_NAME = "Ladder"


def log(msg):
    unreal.log(f"AFB: {msg}")


def mirror_sign(body_mesh):
    """-1 when the FBX import mirrored X (the 75% port, the only part sticking out past the
    plinth on one X side, then lands on -X). Same test create_assets.py uses."""
    b = body_mesh.get_bounding_box()
    return 1.0 if b.max.x >= -b.min.x else -1.0


def ensure_ladder(build_bp, body_mesh):
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    BFL = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = sub.k2_gather_subobject_data_for_blueprint(build_bp)
    ladder_cls = unreal.load_class(None, LADDER_CLASS)

    comp = None
    for h in handles:
        o = BFL.get_object_for_blueprint(BFL.get_data(h), build_bp)
        if o is not None and o.get_class() == ladder_cls:
            comp = o
            break
    if comp is None:
        params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=ladder_cls, blueprint_context=build_bp)
        handle, fail = sub.add_new_subobject(params)
        if not BFL.is_handle_valid(handle):
            raise RuntimeError(f"adding ladder failed: {fail}")
        sub.rename_subobject(handle, unreal.Text(LADDER_NAME))
        comp = BFL.get_object_for_blueprint(BFL.get_data(handle), build_bp)
        log("added ladder component")

    # Ladder position in Unreal space, following the import's X mirror.
    sign = mirror_sign(body_mesh)
    out_x, out_y = sign * math.cos(LADDER_ANGLE_BLENDER), math.sin(LADDER_ANGLE_BLENDER)
    outward_yaw = math.degrees(math.atan2(out_y, out_x))
    half_height = LADDER_TOP / 2.0
    # Box sits OUTSIDE the rung line (inner face on the rungs). Centred on the rungs, the inner half
    # reached into the hull and the climber was moved into the tank wall (seen in game 2026-11-10).
    centre = LADDER_RADIUS + LADDER_HALF_DEPTH
    comp.set_editor_property("relative_location", unreal.Vector(out_x * centre, out_y * centre, half_height))
    # Vanilla points the box's +X into the tank (yaw 180 for a ladder on the +X side).
    comp.set_editor_property("relative_rotation", unreal.Rotator(roll=0.0, pitch=0.0, yaw=outward_yaw + 180.0))
    comp.set_editor_property("box_extent", unreal.Vector(LADDER_HALF_DEPTH, LADDER_HALF_WIDTH, half_height))
    try:
        comp.set_collision_profile_name("OverlapAllDynamic")
    except Exception as e:  # the class default already matches vanilla; just report
        log(f"could not set ladder collision profile: {e}")
    log(f"ladder at ({out_x * centre:.1f}, {out_y * centre:.1f}, {half_height:.0f}) rungs at r={LADDER_RADIUS} "
        f"yaw {outward_yaw + 180.0:.1f} extent ({LADDER_HALF_DEPTH}, {LADDER_HALF_WIDTH}, {half_height}) mirror={sign}")
    return comp


if __name__ == "__main__":
    root = f"/{MOD}"
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([root], True)
    bp = unreal.load_asset(f"{root}/Build_{MOD}")
    body = unreal.load_asset(f"{root}/Mesh/SM_{MOD}")
    ensure_ladder(bp, body)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    # A recompile must keep the CDO values create_assets.py set; check before saving.
    c = unreal.get_default_object(bp.generated_class())
    log(f"after compile: name={c.get_editor_property('m_display_name')} capacity={c.get_editor_property('m_storage_capacity')} "
        f"useable={c.get_editor_property('m_is_useable')} clearance={len(c.get_editor_property('m_clearance_data'))}")
    unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False)
    log("ladder done")
