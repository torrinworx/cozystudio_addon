import bpy

# def test_add_cube_operator():
#     print("HELLO THERE", bpy.ops.cozystudio.COZYSTUDIO_PT_panel)

#     # Ensure scene starts clean
#     bpy.ops.object.select_all(action="SELECT")
#     bpy.ops.object.delete()
#     # Run the operator under test
#     bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
#     # Verify a cube exists
#     cubes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
#     assert len(cubes) == 1
#     assert cubes[0].name.startswith("Cube")
