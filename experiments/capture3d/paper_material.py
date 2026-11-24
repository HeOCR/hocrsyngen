# SPDX-License-Identifier: CC0-1.0
"""Matte, lightly transmissive office paper with UV-locked fibres and print."""

import bpy


ROUGHNESS = .91
SPECULAR = .035
TRANSLUCENCY = .12
FIBRE_RELIEF_M = .000012


def _connect(tree, value, socket):
    if isinstance(value, (int, float, tuple, list)):
        socket.default_value = value
    else:
        tree.links.new(value, socket)


def _math(tree, operation, *values):
    node = tree.nodes.new("ShaderNodeMath")
    node.operation = operation
    for value, socket in zip(values, node.inputs):
        _connect(tree, value, socket)
    return node.outputs[0]


def _vector(tree, operation, a, b):
    node = tree.nodes.new("ShaderNodeVectorMath")
    node.operation = operation
    _connect(tree, a, node.inputs[0])
    _connect(tree, b, node.inputs[1])
    return node.outputs["Value" if operation == "DOT_PRODUCT" else "Vector"]


def _image(tree, uv, path, *, data=False):
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(path, check_existing=True)
    if data:
        node.image.colorspace_settings.name = "Non-Color"
    tree.links.new(uv, node.inputs["Vector"])
    return node.outputs["Color"]


def _noise(tree, uv, scale):
    texture = tree.nodes.new("ShaderNodeTexNoise")
    tree.links.new(_vector(tree, "MULTIPLY", uv, scale), texture.inputs["Vector"])
    texture.inputs["Scale"].default_value = 1
    texture.inputs["Detail"].default_value = 1
    return texture.outputs["Fac"]


def office_paper(name, paper, stock, *, ink=None, showthrough=None):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    uv = tree.nodes.new("ShaderNodeTexCoord").outputs["UV"]
    fibre = _noise(tree, uv, (630, 231, 1))
    mottle = _noise(tree, uv, (4.3, 6.5, 1))
    tint = tuple(a * b for a, b in zip(stock, (.985, .977, .961), strict=True))
    density = _math(tree, "ADD", _math(tree, "MULTIPLY_ADD", fibre, .034, .965),
                    _math(tree, "MULTIPLY_ADD", mottle, .040, -.020))

    # A narrow reflectance change in the bent fibres, expressed in rest-sheet metres.
    nx, ny = paper.axis
    coefficients = (paper.width * nx, paper.height * ny, 0.)
    cross = _vector(tree, "DOT_PRODUCT", uv, coefficients)
    for center, _, _, crease in paper.bends:
        if crease:
            distance = _math(tree, "ABSOLUTE", _math(tree, "SUBTRACT", cross, center + .5 * sum(coefficients)))
            whitening = _math(tree, "MAXIMUM", 0., _math(tree, "MULTIPLY_ADD", distance, -1 / .00042, 1.))
            density = _math(tree, "ADD", density, _math(tree, "MULTIPLY", whitening, .083))

    stock_color = _vector(tree, "MULTIPLY", tint, density)
    if showthrough:
        duplex = _image(tree, uv, showthrough, data=True)
        diffuse_stock = _vector(tree, "MULTIPLY", stock_color, _math(tree, "MULTIPLY_ADD", duplex, .045, .955))
        transmitting_stock = _vector(tree, "MULTIPLY", stock_color, _math(tree, "MULTIPLY_ADD", duplex, .20, .80))
    else:
        diffuse_stock = transmitting_stock = stock_color

    matte = tree.nodes.get("Principled BSDF")
    matte.inputs["Roughness"].default_value = ROUGHNESS
    matte.inputs["Specular IOR Level"].default_value = SPECULAR
    if ink:
        front = _image(tree, uv, ink)
        diffuse_stock = _vector(tree, "MULTIPLY", diffuse_stock, front)
        transmitting_stock = _vector(tree, "MULTIPLY", transmitting_stock, front)
    tree.links.new(diffuse_stock, matte.inputs["Base Color"])
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .20
    bump.inputs["Distance"].default_value = FIBRE_RELIEF_M
    tree.links.new(fibre, bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], matte.inputs["Normal"])

    transmit = tree.nodes.new("ShaderNodeBsdfTranslucent")
    tree.links.new(transmitting_stock, transmit.inputs["Color"])
    mix = tree.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = TRANSLUCENCY
    tree.links.new(matte.outputs[0], mix.inputs[1])
    tree.links.new(transmit.outputs[0], mix.inputs[2])
    tree.links.new(mix.outputs[0], tree.nodes.get("Material Output").inputs["Surface"])
    return material
