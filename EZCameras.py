bl_info = {
    "name": "EZCameras",
    "author": "matidfk",
    "version": (2, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > EZCameras",
    "description": "Allows for easy management of multiple camera angles, each with their own associated world, render resolution, exposure and anything else through the use of drivers.",
    "category": "3D View",
}

import bpy

# =========================================================================
# Core Logic & Handlers
# =========================================================================

_last_active_camera = None

def apply_ezcamera_settings(scene, camera_obj):
    """Core evaluation logic extracted for high performance inside handlers"""
    glob = scene.ezcameras_globals
    props = camera_obj.ezcamera_settings
    
    # Core Native Overrides
    scene.world = props.world if (props.use_world and props.world) else glob.world
    if props.use_res: 
        scene.render.resolution_x, scene.render.resolution_y = props.res_x, props.res_y
    else: 
        scene.render.resolution_x, scene.render.resolution_y = glob.res_x, glob.res_y
    scene.view_settings.exposure = props.exposure if props.use_exposure else glob.exposure
    
    # Sync Custom Props to LIVE 'out_val' variables
    for g_prop in glob.custom_props:
        # Check if the active camera has an explicit override matching this global prop name
        match = next((c_prop for c_prop in props.custom_overrides if c_prop.name == g_prop.name), None)
        
        # Determine source: use camera override ONLY if it exists AND its explicit toggle is checked
        if match and match.use_override:
            source = match
        else:
            source = g_prop
        
        g_prop.out_val_float = source.val_float
        g_prop.out_val_int = source.val_int
        g_prop.out_val_factor = source.val_factor
        g_prop.out_val_bool = source.val_bool


def ezcameras_camera_switch_handler(scene, depsgraph):
    """Automatically catches camera switches anywhere in Blender"""
    global _last_active_camera
    current_camera = scene.camera
    
    if current_camera != _last_active_camera:
        _last_active_camera = current_camera
        if current_camera:
            apply_ezcamera_settings(scene, current_camera)


def sync_active_ezcamera_settings(self, context):
    """Fallback trigger for property tweaks"""
    scene = context.scene
    if isinstance(self.id_data, bpy.types.Scene) or scene.camera == self.id_data:
        if scene.camera:
            apply_ezcamera_settings(scene, scene.camera)

# =========================================================================
# Property Groups
# =========================================================================

class CustomPropItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Prop Name", default="MyProp", update=sync_active_ezcamera_settings)
    use_override: bpy.props.BoolProperty(name="Use Override", default=True, update=sync_active_ezcamera_settings)
    prop_type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ('FLOAT', 'Float', ''), 
            ('INT', 'Int', ''),
            ('FACTOR', 'Factor', ''),
            ('BOOL', 'Bool', '')
        ],
        default='FLOAT',
        update=sync_active_ezcamera_settings
    )
    
    # User-defined values
    val_float: bpy.props.FloatProperty(name="Value", update=sync_active_ezcamera_settings)
    val_int: bpy.props.IntProperty(name="Value", update=sync_active_ezcamera_settings)
    val_factor: bpy.props.FloatProperty(name="Value", min=0.0, max=1.0, precision=3, update=sync_active_ezcamera_settings)
    val_bool: bpy.props.BoolProperty(name="Value", update=sync_active_ezcamera_settings)
    
    # The LIVE Output (This is what you copy for drivers)
    out_val_float: bpy.props.FloatProperty(name="Live Output")
    out_val_int: bpy.props.IntProperty(name="Live Output")
    out_val_factor: bpy.props.FloatProperty(name="Live Output", min=0.0, max=1.0, precision=3)
    out_val_bool: bpy.props.BoolProperty(name="Live Output")


class EZCamerasGlobalProps(bpy.types.PropertyGroup):
    search_query: bpy.props.StringProperty(name="", default="", options={'TEXTEDIT_UPDATE'})
    world: bpy.props.PointerProperty(name="Default World", type=bpy.types.World)
    res_x: bpy.props.IntProperty(name="Default X", default=1920, min=1)
    res_y: bpy.props.IntProperty(name="Default Y", default=1080, min=1)
    exposure: bpy.props.FloatProperty(name="Default Exposure", default=0.0)
    custom_props: bpy.props.CollectionProperty(type=CustomPropItem)


class EZCameraProps(bpy.types.PropertyGroup):
    is_favorite: bpy.props.BoolProperty(name="Favorite", default=False)
    use_world: bpy.props.BoolProperty(name="Override World", default=False, update=sync_active_ezcamera_settings)
    world: bpy.props.PointerProperty(name="World", type=bpy.types.World, update=sync_active_ezcamera_settings)
    use_res: bpy.props.BoolProperty(name="Override Resolution", default=False, update=sync_active_ezcamera_settings)
    res_x: bpy.props.IntProperty(name="X", default=1920, min=1, update=sync_active_ezcamera_settings)
    res_y: bpy.props.IntProperty(name="Y", default=1080, min=1, update=sync_active_ezcamera_settings)
    use_exposure: bpy.props.BoolProperty(name="Override Exposure", default=False, update=sync_active_ezcamera_settings)
    exposure: bpy.props.FloatProperty(name="Exposure", default=0.0, update=sync_active_ezcamera_settings)
    custom_overrides: bpy.props.CollectionProperty(type=CustomPropItem)

# =========================================================================
# Operators & Menus
# =========================================================================

class SCENE_OT_ezcameras_add_custom_prop(bpy.types.Operator):
    bl_idname = "scene.ezcameras_add_custom_prop"
    bl_label = "Add Global Property"
    
    def execute(self, context):
        context.scene.ezcameras_globals.custom_props.add()
        return {'FINISHED'}


class SCENE_OT_ezcameras_add_specific_override(bpy.types.Operator):
    bl_idname = "scene.ezcameras_add_specific_override"
    bl_label = "Add Specific Override"
    
    camera_name: bpy.props.StringProperty()
    prop_name: bpy.props.StringProperty()
    prop_type: bpy.props.StringProperty()
    
    def execute(self, context):
        cam = context.scene.objects.get(self.camera_name)
        if not cam:
            return {'CANCELLED'}
            
        overrides = cam.ezcamera_settings.custom_overrides
        if any(p.name == self.prop_name for p in overrides):
            self.report({'WARNING'}, f"Override '{self.prop_name}' already exists.")
            return {'CANCELLED'}
            
        new_override = overrides.add()
        new_override.name = self.prop_name
        new_override.prop_type = self.prop_type
        new_override.use_override = True # On by default when freshly added
        
        apply_ezcamera_settings(context.scene, cam)
        return {'FINISHED'}


class SCENE_OT_ezcameras_remove_custom_prop(bpy.types.Operator):
    bl_idname = "scene.ezcameras_remove_custom_prop"
    bl_label = "Remove"
    target: bpy.props.StringProperty()
    index: bpy.props.IntProperty()
    
    def execute(self, context):
        if self.target == "GLOBAL": 
            context.scene.ezcameras_globals.custom_props.remove(self.index)
        else:
            cam = context.scene.objects.get(self.target)
            if cam: 
                cam.ezcamera_settings.custom_overrides.remove(self.index)
                
        if context.scene.camera:
            apply_ezcamera_settings(context.scene, context.scene.camera)
        return {'FINISHED'}


class SCENE_OT_ezcameras_set_camera(bpy.types.Operator):
    bl_idname = "scene.ezcameras_set_camera"
    bl_label = "Set Camera"
    camera_name: bpy.props.StringProperty()
    
    def execute(self, context):
        scene = context.scene
        cam_obj = scene.objects.get(self.camera_name)
        if not cam_obj: 
            return {'CANCELLED'}
        scene.camera = cam_obj
        apply_ezcamera_settings(scene, cam_obj)
        return {'FINISHED'}


class EZCAMERAS_MT_add_override_menu(bpy.types.Menu):
    bl_label = "Available Global Properties"
    bl_idname = "EZCAMERAS_MT_add_override_menu"

    def draw(self, context):
        layout = self.layout
        glob = context.scene.ezcameras_globals
        active_cam = context.scene.camera
        
        if not active_cam:
            layout.label(text="No active camera selected.")
            return

        if not glob.custom_props:
            layout.label(text="No global properties defined yet.")
            return

        existing = [p.name for p in active_cam.ezcamera_settings.custom_overrides]

        for prop in glob.custom_props:
            if prop.name in existing:
                row = layout.row()
                row.active = False
                row.label(text=f"{prop.name} (Already Added)", icon='CHECKMARK')
            else:
                op = layout.operator("scene.ezcameras_add_specific_override", text=prop.name, icon='PROPERTIES')
                op.camera_name = active_cam.name
                op.prop_name = prop.name
                op.prop_type = prop.prop_type

# =========================================================================
# UI Panel
# =========================================================================

class VIEW3D_PT_ezcameras(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EZCameras'
    bl_label = "Camera Manager"

    def draw_custom_props(self, layout, prop_collection, is_global, active_cam_name=""):
        col = layout.column(align=True)
        for i, p in enumerate(prop_collection):
            row = col.row(align=True)
            
            if is_global:
                row.prop(p, "name", text="")
                
                # Draw Value input
                if p.prop_type == 'FLOAT': row.prop(p, "val_float", text="")
                elif p.prop_type == 'INT': row.prop(p, "val_int", text="")
                elif p.prop_type == 'FACTOR': row.prop(p, "val_factor", text="", slider=True)
                else: row.prop(p, "val_bool", text="")
                
                # Live Output driver field
                sub = row.row(align=True)
                sub.active = False 
                if p.prop_type == 'FLOAT': sub.prop(p, "out_val_float", text="")
                elif p.prop_type == 'INT': sub.prop(p, "out_val_int", text="")
                elif p.prop_type == 'FACTOR': sub.prop(p, "out_val_factor", text="")
                else: sub.prop(p, "out_val_bool", text="")

                row.prop(p, "prop_type", text="", icon_only=True)
            else:
                # Local Cam Override Block with checkbox toggle activation
                row.prop(p, "use_override", text="", toggle=True, icon='CHECKBOX_HLT' if p.use_override else 'CHECKBOX_DEHLT')
                
                # Lock input block if toggle is off, match native behavior
                sub_row = row.row(align=True)
                sub_row.active = p.use_override
                sub_row.label(text=p.name)
                
                if p.prop_type == 'FLOAT': sub_row.prop(p, "val_float", text="")
                elif p.prop_type == 'INT': sub_row.prop(p, "val_int", text="")
                elif p.prop_type == 'FACTOR': sub_row.prop(p, "val_factor", text="", slider=True)
                else: sub_row.prop(p, "val_bool", text="")
                
                type_label = p.prop_type.title()
                row.label(text=f"({type_label})")

            rem = row.operator("scene.ezcameras_remove_custom_prop", text="", icon='X', emboss=False)
            rem.target, rem.index = ("GLOBAL" if is_global else active_cam_name), i

    def draw(self, context):
        layout = self.layout
        scene, glob = context.scene, context.scene.ezcameras_globals

        # Global Defaults Panel
        box = layout.box()
        box.label(text="Global Defaults & Live Drivers", icon='WORLD')
        col = box.column(align=True)
        col.prop(glob, "world", text="World")
        row = col.row(align=True)
        row.prop(glob, "res_x", text="X"); row.prop(glob, "res_y", text="Y")
        col.prop(glob, "exposure", text="Exposure")
        
        layout.separator()
        self.draw_custom_props(box, glob.custom_props, True)
        box.operator("scene.ezcameras_add_custom_prop", text="Add Global Prop", icon='ADD')

        layout.separator()
        layout.prop(glob, "search_query", icon='VIEWZOOM', placeholder="Search Cameras...")

        cameras = [obj for obj in scene.objects if obj.type == 'CAMERA']
        q = glob.search_query.strip().lower()
        if q: cameras = [c for c in cameras if q in c.name.lower()]
        cameras.sort(key=lambda c: (not c.ezcamera_settings.is_favorite, c.name.lower()))

        for cam in cameras:
            c_props = cam.ezcamera_settings
            is_active = (scene.camera == cam)
            
            box = layout.box()
            row = box.row(align=True)
            row.prop(c_props, "is_favorite", text="", icon='SOLO_ON' if c_props.is_favorite else 'SOLO_OFF', emboss=False)
            op = row.operator("scene.ezcameras_set_camera", text=cam.name, 
                               icon='OUTLINER_OB_CAMERA' if is_active else 'CAMERA_DATA', depress=is_active)
            op.camera_name = cam.name

            if is_active:
                col = box.column(align=True)
                row = col.row(align=True)
                row.prop(c_props, "use_world", text="", icon='WORLD', toggle=True)
                sub = row.row(align=True); sub.prop(c_props, "world", text=""); sub.active = c_props.use_world
                
                row = col.row(align=True)
                row.prop(c_props, "use_res", text="", icon='RENDER_RESULT', toggle=True)
                sub = row.row(align=True); sub.prop(c_props, "res_x", text="X"); sub.prop(c_props, "res_y", text="Y"); sub.active = c_props.use_res
                
                row = col.row(align=True)
                row.prop(c_props, "use_exposure", text="", icon='LIGHT', toggle=True)
                sub = row.row(align=True); sub.prop(c_props, "exposure", text="Exposure"); sub.active = c_props.use_exposure
                
                col.separator()
                col.label(text="Overrides:")
                self.draw_custom_props(col, c_props.custom_overrides, False, active_cam_name=cam.name)
                
                col.menu("EZCAMERAS_MT_add_override_menu", text="Add Override Selection", icon='DOWNARROW_HLT')

# =========================================================================
# Registration
# =========================================================================

classes = (
    CustomPropItem, 
    EZCamerasGlobalProps,
    EZCameraProps,
    SCENE_OT_ezcameras_add_custom_prop,
    SCENE_OT_ezcameras_add_specific_override,
    SCENE_OT_ezcameras_remove_custom_prop,
    SCENE_OT_ezcameras_set_camera,
    EZCAMERAS_MT_add_override_menu,
    VIEW3D_PT_ezcameras
)

def register():
    global _last_active_camera
    _last_active_camera = None
    
    for cls in classes: 
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.ezcameras_globals = bpy.props.PointerProperty(type=EZCamerasGlobalProps)
    bpy.types.Object.ezcamera_settings = bpy.props.PointerProperty(type=EZCameraProps)
    
    if ezcameras_camera_switch_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(ezcameras_camera_switch_handler)

def unregister():
    for cls in reversed(classes): 
        bpy.utils.unregister_class(cls)
        
    del bpy.types.Scene.ezcameras_globals
    del bpy.types.Object.ezcamera_settings
    
    if ezcameras_camera_switch_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(ezcameras_camera_switch_handler)

if __name__ == "__main__":
    register()
