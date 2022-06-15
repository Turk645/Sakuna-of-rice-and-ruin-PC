from inc_noesis import *

def registerNoesisTypes():
    handle = noesis.register("Sakuna NHTEX Images", ".nhtex")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    #noesis.logPopup()
    return 1

def noepyCheckType(data):
    return 1

def noepyLoadRGBA(data, texList):
    bs = NoeBitStream(data)
    bs.seek(0x40, NOESEEK_ABS)
    imgWidth = bs.readUInt()
    imgHeight = bs.readUInt()
    bs.seek(0x30, NOESEEK_ABS)
    imgFmt = bs.readUByte()
    bs.seek(0x50, NOESEEK_ABS)
    otest = bs.readUByte()
    if otest == 0xb:
        offset = 0x180
    elif otest == 0x01:
        offset = 0x90
    elif otest == 0x05:
        offset = 0xF0
    elif otest == 0x08:
        offset = 0x148
    elif otest == 0x0a:
        offset = 0x168
    elif otest == 0x0C:
        offset = 0x198
    else:
        offset = 0x150
    datasize = len(data) - offset
    bs.seek(offset, NOESEEK_ABS)
    data = bs.readBytes(datasize)
    #DXT1
    if imgFmt == 0x47:
        texFmt = noesis.NOESISTEX_DXT1
    elif imgFmt == 0x4D:
        texFmt = noesis.NOESISTEX_DXT5
    #DXT5 packed normal map
    elif imgFmt == 0x53:
        data = rapi.imageDecodeDXT(data, imgWidth, imgHeight, noesis.FOURCC_ATI2)
        texFmt = noesis.NOESISTEX_RGBA32
    #unknown, not handled
    elif imgFmt == 0x62:
        data = rapi.imageDecodeDXT(data, imgWidth, imgHeight, noesis.FOURCC_BC7)
        texFmt = noesis.NOESISTEX_RGBA32
    else:
        print("WARNING: Unhandled image format " + repr(imgFmt) + " - " + repr(imgWidth) + "x" + repr(imgHeight) + " - " + repr(len(data)))
        return None
    texList.append(NoeTexture(rapi.getInputName(), imgWidth, imgHeight, data, texFmt))
    return 1