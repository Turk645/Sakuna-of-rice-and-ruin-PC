bl_info = {
    "name": "Sakuna: Of Rice and Ruin Importer",
    "author": "Turk",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import-Export",
    "description": "A script to import meshes from Sakuna",
    "warning": "",
    "category": "Import-Export",
}
import sys
import bpy
import bmesh
import os
import io
import struct
import math
import mathutils
from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty
                       )
from bpy_extras.io_utils import ImportHelper

class sakunamesh(bpy.types.Operator, ImportHelper):
    bl_idname = "custom_import_scene.sakuna_import"
    bl_label = "Import"
    bl_options = {'PRESET', 'UNDO'}
    filter_glob: StringProperty(
            default="*.nhmdl",
            options={'HIDDEN'},
            )
    filepath: StringProperty(subtype='FILE_PATH',)
    files: CollectionProperty(type=bpy.types.PropertyGroup)
        
    def draw(self, context):
        return
    def execute(self, context):
        CurCollection = bpy.data.collections.new("Mesh Collection")
        bpy.context.scene.collection.children.link(CurCollection)
        
        CurFile = open(self.filepath,"rb")
        
        DataOffset = int.from_bytes(CurFile.read(8),byteorder='little') + CurFile.tell() - 8
        CurFile.seek(8,1)
        MeshDataOffset = int.from_bytes(CurFile.read(8),byteorder='little') + CurFile.tell() - 8
        CurFile.seek(MeshDataOffset)
        MeshDataOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        
        CurFile.seek(DataOffset)
        SkeletonPointer = int.from_bytes(CurFile.read(8),byteorder='little') + CurFile.tell() - 8
        SkeletonCount = int.from_bytes(CurFile.read(8),byteorder='little')
        CurFile.seek(DataOffset+0x90)
        MeshReferenceOffset = int.from_bytes(CurFile.read(8),byteorder='little') + CurFile.tell() - 8
        MeshRefCount = int.from_bytes(CurFile.read(8),byteorder='little')
        
        CurFile.seek(DataOffset+0xb8)
        SkeletonPositionIndexOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        SkeletonPositionIndexCount = int.from_bytes(CurFile.read(8),byteorder='little')
        SkeletonPositionOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        
        CurFile.seek(DataOffset+0x40)
        MatTableOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        MatTableCount = int.from_bytes(CurFile.read(8),byteorder='little')
        
        CurFile.seek(DataOffset+0x80)
        TextureTableOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        TextureTableCount = int.from_bytes(CurFile.read(8),byteorder='little')
        
        MatTable = parse_materials(CurFile,MatTableOffset,MatTableCount,TextureTableOffset,TextureTableCount,self)
        
        BoneTable,WeightRefTable,armature_obj = parse_skeleton(CurCollection,CurFile,SkeletonPointer,SkeletonCount,SkeletonPositionIndexOffset,SkeletonPositionIndexCount,SkeletonPositionOffset)

        parse_mesh(CurCollection,CurFile,MeshReferenceOffset,MeshRefCount,MeshDataOffset,BoneTable,WeightRefTable,armature_obj,MatTable)

        CurFile.close()
        return {'FINISHED'}

def parse_skeleton(CurCollection,CurFile,SkeletonPointer,SkeletonCount,SkeletonPositionIndexOffset,SkeletonPositionIndexCount,SkeletonPositionOffset):
    armature_data = bpy.data.armatures.new("Armature")
    armature_obj = bpy.data.objects.new("Armature", armature_data)
    CurCollection.objects.link(armature_obj)
    bpy.context.view_layer.objects.active = armature_obj
    BoneTable = []
    WeightRefTable = []

    for x in range(SkeletonCount):
        CurFile.seek(SkeletonPointer+0x50*x)
        BoneNameOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        BoneNameLength = int.from_bytes(CurFile.read(8),byteorder='little')
        ParentIndex = int.from_bytes(CurFile.read(4),byteorder='little',signed=True)
        CurFile.seek(12,1)
        EntryType = int.from_bytes(CurFile.read(8),byteorder='little')
        CurFile.seek(BoneNameOffset)
        BoneName = CurFile.read(BoneNameLength).decode('utf-8')
        BoneTable.append({"Name":BoneName,"Type":EntryType,"Parent":ParentIndex})
    for x in range(SkeletonPositionIndexCount):
        CurFile.seek(SkeletonPositionIndexOffset+4*x)
        PosIndex = int.from_bytes(CurFile.read(4),byteorder='little')
        WeightRefTable.append(PosIndex)
        CurFile.seek(SkeletonPositionOffset+0x40*x)
        m1 = struct.unpack('<fff', CurFile.read(4*3))
        CurFile.seek(4,1)
        m2 = struct.unpack('<fff', CurFile.read(4*3))
        CurFile.seek(4,1)
        m3 = struct.unpack('<fff', CurFile.read(4*3))
        CurFile.seek(4,1)
        Pos = struct.unpack('<fff', CurFile.read(4*3))
        Pos = (-Pos[0],-Pos[1],-Pos[2])
        RotMatrix = mathutils.Matrix([m1,m2,m3])
        Pos = mathutils.Vector(Pos)
        Pos.rotate(RotMatrix.to_euler())
        BoneTable[PosIndex]["Pos"] = Pos
        BoneTable[PosIndex]["Rot"] = RotMatrix.to_euler()
    
    utils_set_mode('EDIT')
    for x in range(SkeletonCount):
        if BoneTable[x]["Type"] == 3:
            edit_bone = armature_obj.data.edit_bones.new(BoneTable[x]["Name"])
            if BoneTable[x].get("Pos"):
                edit_bone.head = BoneTable[x]["Pos"]
                edit_bone.tail = (BoneTable[x]["Pos"][0],BoneTable[x]["Pos"][1]+10,BoneTable[x]["Pos"][2])
            if BoneTable[x]["Parent"] > -1:
                edit_bone.parent = armature_obj.data.edit_bones[BoneTable[BoneTable[x]["Parent"]]["Name"]]

    utils_set_mode('OBJECT')
    return BoneTable,WeightRefTable,armature_obj
    
def parse_mesh(CurCollection,CurFile,MeshReferenceOffset,MeshRefCount,MeshDataOffset,BoneTable,WeightRefTable,ObjArm,MatTable):
    MeshTable = []
    for x in range(MeshRefCount):
        CurFile.seek(MeshReferenceOffset+0x68*x)
        MeshNameOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        MeshNameLength = int.from_bytes(CurFile.read(8),byteorder='little')
        DataSplitFlag = int.from_bytes(CurFile.read(4),byteorder='little')
        CurFile.seek(4,1)
        MaterialIndex = int.from_bytes(CurFile.read(4),byteorder='little')
        CurFile.seek(4,1)
        VertFlags = int.from_bytes(CurFile.read(4),byteorder='little')
        VertCount = int.from_bytes(CurFile.read(4),byteorder='little')
        IndiceCount = int.from_bytes(CurFile.read(4),byteorder='little')
        
        HasWeights = VertFlags & 16
        HasVertexColors = VertFlags & 4
        
        CurFile.seek(MeshNameOffset)
        MeshName = CurFile.read(MeshNameLength).decode('utf-8')
        
        CurFile.seek(MeshDataOffset+0x30*x)
        DataOffset1 = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        CurFile.seek(8,1)
        IndiceOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        CurFile.seek(8,1)
        DataOffset2 = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        
        
        
        VertTable = []
        UVTable = []
        NormalTable = []
        WeightTable = []
        FaceTable = []
        ColorTable = []
        
        if DataSplitFlag == 2:
            CurFile.seek(DataOffset1)
            for y in range(VertCount):
                if HasVertexColors:
                    tmpColor = struct.unpack('<BBBB', CurFile.read(4))
                    ColorTable.append((tmpColor[0]/255,tmpColor[1]/255,tmpColor[2]/255,tmpColor[3]/255))
                tmpUV = struct.unpack('<ff', CurFile.read(4*2))
                UVTable.append([tmpUV[0],1-tmpUV[1]])

            CurFile.seek(DataOffset2)
            for y in range(VertCount):
                VertTable.append(struct.unpack('<fff', CurFile.read(4*3)))
                NormalTable.append(struct.unpack('<fff', CurFile.read(4*3)))
                CurFile.seek(24,1)
                if HasWeights:
                    tmpBone = struct.unpack('<BBBB', CurFile.read(4))
                    tmpWeight = []
                    for z in tmpBone[1:]:
                        if z > 0:
                            tmpWeight.append(struct.unpack('<f', CurFile.read(4))[0])
                    tmpWeight.append(1-sum(tmpWeight))
                    WeightTable.append([y,tmpBone,tmpWeight])
                
                
        elif DataSplitFlag == 0:
            CurFile.seek(DataOffset1)
            for y in range(VertCount):
                VertTable.append(struct.unpack('<fff', CurFile.read(4*3)))
                NormalTable.append(struct.unpack('<fff', CurFile.read(4*3)))
                CurFile.seek(24,1)
                if HasVertexColors:
                    tmpColor = struct.unpack('<BBBB', CurFile.read(4))
                    ColorTable.append((tmpColor[0]/255,tmpColor[1]/255,tmpColor[2]/255,tmpColor[3]/255))
                tmpUV = struct.unpack('<ff', CurFile.read(4*2))
                UVTable.append([tmpUV[0],1-tmpUV[1]])
        CurFile.seek(IndiceOffset)
        StripList = []
        for y in range(IndiceCount):
            StripList.append(int.from_bytes(CurFile.read(2),byteorder='little',signed=False))
        for f in strip2face(StripList):
            FaceTable.append(f)

            

        #build Mesh
        mesh1 = bpy.data.meshes.new("Mesh")
        mesh1.use_auto_smooth = True
        obj = bpy.data.objects.new(MeshName,mesh1)
        CurCollection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        mesh = bpy.context.object.data
        bm = bmesh.new()
        for v in VertTable:
            bm.verts.new((v[0],v[1],v[2]))
        list1 = [v for v in bm.verts]
        for f in FaceTable:
            try:
                bm.faces.new((list1[f[0]],list1[f[1]],list1[f[2]]))
            except:
                continue             
        bm.to_mesh(mesh)
        
        uv_layer = bm.loops.layers.uv.verify()
        Normals = []
        for f in bm.faces:
            f.smooth=True
            for l in f.loops:
                if NormalTable != []:
                    Normals.append(NormalTable[l.vert.index])
                luv = l[uv_layer]
                try:
                    luv.uv = UVTable[l.vert.index]
                except:
                    continue
        bm.to_mesh(mesh)
        
        if ColorTable != []:
            color_layer = bm.loops.layers.color.new("Color")
            for f in bm.faces:
                for l in f.loops:
                    l[color_layer]= ColorTable[l.vert.index]
            bm.to_mesh(mesh)

        
        bm.free()
        
        if NormalTable != []:
            mesh1.normals_split_custom_set(Normals)
        if WeightTable != []:
            for i in WeightTable:
                for v in range(len(i[2])):
                    if obj.vertex_groups.find(BoneTable[WeightRefTable[i[1][v]]]["Name"]) == -1:
                        TempVG = obj.vertex_groups.new(name = BoneTable[WeightRefTable[i[1][v]]]["Name"])
                    else:
                        TempVG = obj.vertex_groups[obj.vertex_groups.find(BoneTable[WeightRefTable[i[1][v]]]["Name"])]
                    TempVG.add([i[0]],i[2][v],'ADD')

        if len(obj.data.materials)>0:
            obj.data.materials[0]=MatTable[MaterialIndex]
        else:
            obj.data.materials.append(MatTable[MaterialIndex])


        if ObjArm:     
            ArmMod = obj.modifiers.new("Armature","ARMATURE")
            ArmMod.object = ObjArm
            obj.parent = ObjArm
            ObjArm.rotation_euler = (1.5707963705062866,0,0)
        else:
            obj.rotation_euler = (1.5707963705062866,0,0)

        
    return

def parse_materials(CurFile,MatTableOffset,MatTableCount,TextureTableOffset,TextureTableCount,self):
    MatTable = []
    TextureNameTable = []
    for x in range(TextureTableCount):
        CurFile.seek(TextureTableOffset+0x10*x)
        TexNameOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        TexNameLength = int.from_bytes(CurFile.read(8),byteorder='little')
        CurFile.seek(TexNameOffset)
        TextureName = CurFile.read(TexNameLength).decode('utf-8')
        TextureNameTable.append(TextureName)
    for x in range(MatTableCount):
        CurFile.seek(MatTableOffset+0x78*x)
        MatNameOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        MatNameLength = int.from_bytes(CurFile.read(8),byteorder='little')
        CurFile.seek(0x28,1)
        MatTexOffset = CurFile.tell() + int.from_bytes(CurFile.read(8),byteorder='little')
        MatTexCount = int.from_bytes(CurFile.read(8),byteorder='little')
        CurFile.seek(MatTexOffset)
        MainTextureIndex = int.from_bytes(CurFile.read(8),byteorder='little')

        CurFile.seek(MatNameOffset)
        MatName = CurFile.read(MatNameLength).decode('utf-8')
        mat = bpy.data.materials.get(MatName)
        if mat == None:
            mat = bpy.data.materials.new(name=MatName)
            mat.use_nodes = True
            mainDir = os.path.split(self.filepath)[0]
            matPath = os.path.join(mainDir,TextureNameTable[MainTextureIndex]+".png")
            if os.path.exists(matPath):
                Im = bpy.data.images.new(TextureNameTable[MainTextureIndex],1,1)
                Im.source = 'FILE'
                Im.filepath = matPath
                ImNode = mat.node_tree.nodes.new("ShaderNodeTexImage")
                PrNode = mat.node_tree.nodes['Principled BSDF']
                ImNode.image = Im
                mat.node_tree.links.new(ImNode.outputs['Color'],PrNode.inputs['Base Color'])
        MatTable.append(mat)

    return MatTable

def strip2face(strip):
    flipped = True
    tmpTable = []
    for x in range(len(strip)-2):
        if flipped:
            tmpTable.append((strip[x+1],strip[x+2],strip[x]))
        else:
            tmpTable.append((strip[x+2],strip[x+1],strip[x]))
        flipped = not flipped
    return tmpTable

def utils_set_mode(mode):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)

def menu_func_import(self, context):
    self.layout.operator(sakunamesh.bl_idname, text="Sakuna (.nhmdl)")
        
def register():
    bpy.utils.register_class(sakunamesh)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    
def unregister():
    bpy.utils.unregister_class(sakunamesh)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
        
if __name__ == "__main__":
    register()