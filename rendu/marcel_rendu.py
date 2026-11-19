# Marcel - rendu d'un chantier avec Blender, sans interface.
#
# Usage (depuis la racine du dépôt) :
#   /Applications/Blender.app/Contents/MacOS/Blender --background --python rendu/marcel_rendu.py -- rendu/chantier_exemple.json out/rendu
#
# Les meubles en 3D viennent de meuble3d.py (TRELLIS). Les chemins du fichier de chantier sont relatifs à ce fichier.
#
# Le fichier chantier.json décrit tout : dimensions, peinture, sol, ouvertures, meubles, vues.
# Le script écrit les images dans le dossier de sortie et affiche une ligne "RESULTAT {...}"
# qui liste les fichiers produits et les durées.
#
# Convention pour "position" (ouvertures et meubles) : distance en mètres entre le coin gauche
# du mur et le bord gauche de l'élément, quand on regarde ce mur depuis l'intérieur de la pièce.
# Murs : "fond", "avant", "gauche", "droit". La caméra des photos est côté "avant".
#
# Pièce non rectangulaire (en L, en U…) : donner "contour", la liste des angles [x, y] en mètres, murs à angle droit,
# et "murs_noms", le nom de chaque mur dans l'ordre (le mur i va de l'angle i à l'angle i+1). Sans "murs_noms" : mur1, mur2…
# "sol_pose": "chevron" pose le parquet en chevron. "papier_peint": {"nom du mur": {"image": ..., "largeur_m": ...}}.

import bpy, sys, json, math, os, time
from mathutils import Vector

t0 = time.time()
args = sys.argv[sys.argv.index("--") + 1:]
cfg = json.load(open(args[0], encoding="utf-8"))
sortie = args[1]
os.makedirs(sortie, exist_ok=True)
base = os.path.dirname(os.path.abspath(args[0]))

def chemin(p):
    """Un chemin du chantier peut être absolu, relatif au fichier de chantier, ou relatif au dossier courant."""
    if os.path.isabs(p):
        return p
    for racine in (base, os.getcwd()):
        if os.path.exists(os.path.join(racine, p)):
            return os.path.join(racine, p)
    raise FileNotFoundError("fichier introuvable : " + p)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
H = float(cfg["hauteur"])
E = 0.1  # épaisseur des murs
CONTOUR = None   # pièce non rectangulaire : les angles, recentrés sur l'origine
if cfg.get("contour"):
    _p = [(float(x), float(y)) for x, y in cfg["contour"]]
    _cx = (min(x for x, _ in _p) + max(x for x, _ in _p)) / 2; _cy = (min(y for _, y in _p) + max(y for _, y in _p)) / 2
    CONTOUR = [(x - _cx, y - _cy) for x, y in _p]
    W = max(x for x, _ in CONTOUR) * 2; D = max(y for _, y in CONTOUR) * 2   # l'encombrement de la pièce
    _n = len(CONTOUR)
    SENS = 1 if sum(CONTOUR[i][0] * CONTOUR[(i + 1) % _n][1] - CONTOUR[(i + 1) % _n][0] * CONTOUR[i][1] for i in range(_n)) > 0 else -1
else:
    W, D = float(cfg["largeur"]), float(cfg["profondeur"])

# ---------- petits outils

def rgb(hx):
    hx = hx.lstrip("#"); c = [int(hx[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c) + (1.0,)

def bsdf(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")

def matiere(nom, hx, rugosite=0.6):
    m = bpy.data.materials.new(nom); m.use_nodes = True
    b = bsdf(m); b.inputs["Base Color"].default_value = rgb(hx); b.inputs["Roughness"].default_value = rugosite
    return m

def lumineuse(nom, hx, force):
    m = bpy.data.materials.new(nom); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = rgb(hx); em.inputs["Strength"].default_value = force
    o = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(em.outputs["Emission"], o.inputs["Surface"])
    return m

def boite(nom, taille, centre, m=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
    o = bpy.context.active_object; o.name = nom; o.scale = taille
    if m: o.data.materials.append(m)
    return o

# Pour chaque mur : son centre, l'axe le long du mur, la normale vers l'intérieur,
# et la position du coin gauche vu de l'intérieur.
# "rallonge" : de combien le mur dépasse à gauche et à droite pour fermer les angles.
MURS = {
    "fond":   dict(centre=Vector((0, D / 2 + E / 2, 0)),  le_long=Vector((1, 0, 0)),  dedans=Vector((0, -1, 0)), longueur=W, rallonge=(E, E)),
    "avant":  dict(centre=Vector((0, -D / 2 - E / 2, 0)), le_long=Vector((-1, 0, 0)), dedans=Vector((0, 1, 0)),  longueur=W, rallonge=(E, E)),
    "gauche": dict(centre=Vector((-W / 2 - E / 2, 0, 0)), le_long=Vector((0, 1, 0)),  dedans=Vector((1, 0, 0)),  longueur=D, rallonge=(0, 0)),
    "droit":  dict(centre=Vector((W / 2 + E / 2, 0, 0)),  le_long=Vector((0, -1, 0)), dedans=Vector((-1, 0, 0)), longueur=D, rallonge=(0, 0)),
}
if CONTOUR:
    # Un mur par côté du contour. Vu de l'intérieur, le mur se lit de gauche à droite dans le sens inverse du tracé.
    MURS = {}
    noms = cfg.get("murs_noms") or ["mur%d" % (i + 1) for i in range(_n)]
    def _saillant(i):
        """Vrai si l'angle i est un angle « normal » de pièce (90° vu de l'intérieur), faux si c'est un angle rentrant."""
        a, b, c = Vector(CONTOUR[i - 1]), Vector(CONTOUR[i]), Vector(CONTOUR[(i + 1) % _n])
        return (b - a).cross(c - b) * SENS > 0
    for i in range(_n):
        a, b = Vector(CONTOUR[i]), Vector(CONTOUR[(i + 1) % _n]); u = (b - a).normalized()
        dedans = Vector((-u.y, u.x, 0)) * SENS; le_long = Vector((u.x, u.y, 0)) * -SENS
        milieu = (a + b) / 2
        g, d = ((i + 1) % _n, i) if SENS > 0 else (i, (i + 1) % _n)   # l'angle à gauche et l'angle à droite, vus de l'intérieur
        MURS[noms[i]] = dict(centre=Vector((milieu.x, milieu.y, 0)) - dedans * (E / 2), le_long=le_long, dedans=dedans,
                             longueur=(b - a).length, rallonge=(E if _saillant(g) else -0.002, E if _saillant(d) else -0.002))   # angle rentrant : un cheveu en retrait, sinon deux faces se superposent

def point_sur_mur(mur, position, largeur):
    """Centre, sur l'axe du mur, d'un élément dont le bord gauche est à `position` du coin gauche."""
    m = MURS[mur]
    return m["centre"] + m["le_long"] * (-m["longueur"] / 2 + position + largeur / 2)

def taille_selon_mur(mur, le_long, travers, haut):
    return (le_long, travers, haut) if abs(MURS[mur]["le_long"].x) > 0.5 else (travers, le_long, haut)

def dans_la_piece(x, y):
    """Vrai si le point est à l'intérieur du contour (ou du rectangle)."""
    if not CONTOUR:
        return abs(x) < W / 2 and abs(y) < D / 2
    dedans = False
    for i in range(_n):
        (x1, y1), (x2, y2) = CONTOUR[i], CONTOUR[(i + 1) % _n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans

def plaque(nom, z, m):
    """Sol ou plafond d'une pièce non rectangulaire : une face qui suit le contour."""
    me = bpy.data.meshes.new(nom)
    me.from_pydata([(x, y, z) for x, y in CONTOUR], [], [list(range(_n)) if SENS > 0 else list(range(_n - 1, -1, -1))]); me.update()
    o = bpy.data.objects.new(nom, me); sc.collection.objects.link(o); o.data.materials.append(m)
    return o

def noeud_calcul(nt, operation, a, b=None):
    """Un nœud de calcul ; a et b sont une sortie de nœud ou un nombre."""
    n = nt.nodes.new("ShaderNodeMath"); n.operation = operation
    for i, v in enumerate((a, b)):
        if v is None: continue
        if isinstance(v, (int, float)): n.inputs[i].default_value = v
        else: nt.links.new(v, n.inputs[i])
    return n.outputs[0]

def melange(nt, facteur, a, b):
    """Mélange de deux couleurs ; a et b sont une sortie de nœud ou une couleur."""
    n = nt.nodes.new("ShaderNodeMix"); n.data_type = "RGBA"
    e = {i.identifier: i for i in n.inputs}
    for cle, v in (("Factor_Float", facteur), ("A_Color", a), ("B_Color", b)):
        if isinstance(v, (int, float, tuple)): e[cle].default_value = v
        else: nt.links.new(v, e[cle])
    return next(o for o in n.outputs if o.identifier == "Result_Color")

def papier_peint(nom, mur, reglage):
    """Un mur tapissé : l'image du motif, répétée à sa taille réelle le long du mur."""
    if isinstance(reglage, str): reglage = {"image": reglage}
    m = bpy.data.materials.new("papier_" + nom); m.use_nodes = True
    nt = m.node_tree; b = bsdf(m); b.inputs["Roughness"].default_value = 0.9
    img = bpy.data.images.load(chemin(reglage["image"]))
    k = 1.0 / float(reglage.get("largeur_m", 1.0))
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    pv = nt.nodes.new("ShaderNodeVectorMath"); pv.operation = "DOT_PRODUCT"
    nt.links.new(geo.outputs["Position"], pv.inputs[0]); pv.inputs[1].default_value = tuple(MURS[mur]["le_long"])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(geo.outputs["Position"], sep.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(noeud_calcul(nt, "MULTIPLY", pv.outputs["Value"], k), comb.inputs[0])
    nt.links.new(noeud_calcul(nt, "MULTIPLY", sep.outputs["Z"], k * img.size[0] / max(img.size[1], 1)), comb.inputs[1])
    it = nt.nodes.new("ShaderNodeTexImage"); it.image = img
    nt.links.new(comb.outputs[0], it.inputs["Vector"]); nt.links.new(it.outputs["Color"], b.inputs["Base Color"])
    return m

# ---------- matières

peinture = matiere("peinture", cfg.get("peinture", "#F4F1EA"), 0.85)
blanc = matiere("blanc", cfg.get("plinthe", "#F4F1EA"), 0.5)
plafond_m = matiere("plafond", "#FFFFFF", 0.9)

sol_m = bpy.data.materials.new("sol"); sol_m.use_nodes = True
nt = sol_m.node_tree; b = bsdf(sol_m); b.inputs["Roughness"].default_value = 0.45
tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
if cfg.get("sol_pose") == "chevron" and not cfg.get("sol_image"):
    # Parquet en chevron (point de Hongrie) : des travées de lames coupées à 45°, qui se rejoignent en pointe.
    teintes = cfg.get("sol", ["#B98A5A", "#8E6238"])
    trav = float(cfg.get("chevron_travee_m", 0.42)); pas = float(cfg.get("chevron_lame_m", 0.09)) / math.cos(math.radians(45))
    geo = nt.nodes.new("ShaderNodeNewGeometry"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    fx = noeud_calcul(nt, "DIVIDE", sep.outputs["X"], trav)
    zig = noeud_calcul(nt, "MULTIPLY", noeud_calcul(nt, "PINGPONG", fx, 1.0), trav)          # monte puis descend d'une travée à l'autre
    v = noeud_calcul(nt, "DIVIDE", noeud_calcul(nt, "ADD", sep.outputs["Y"], zig), pas)
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(noeud_calcul(nt, "FLOOR", v), comb.inputs[0]); nt.links.new(noeud_calcul(nt, "FLOOR", fx), comb.inputs[1])
    hasard = nt.nodes.new("ShaderNodeTexWhiteNoise"); hasard.noise_dimensions = "2D"; nt.links.new(comb.outputs[0], hasard.inputs["Vector"])
    bois = melange(nt, hasard.outputs["Value"], rgb(teintes[0]), rgb(teintes[1]))
    def joint(val, demi):   # 1 près d'un bord de lame, 0 ailleurs
        return noeud_calcul(nt, "GREATER_THAN", noeud_calcul(nt, "ABSOLUTE", noeud_calcul(nt, "SUBTRACT", noeud_calcul(nt, "FRACT", val), 0.5)), 0.5 - demi)
    joints = noeud_calcul(nt, "MAXIMUM", joint(v, 0.012), joint(fx, 0.004))
    sombre = tuple(c * 0.35 for c in rgb(teintes[1])[:3]) + (1.0,)
    nt.links.new(melange(nt, joints, bois, sombre), b.inputs["Base Color"])
elif cfg.get("sol_image"):
    # La photo du produit, répétée à sa taille réelle.
    it = nt.nodes.new("ShaderNodeTexImage"); it.image = bpy.data.images.load(chemin(cfg["sol_image"]))
    k = 1.0 / float(cfg.get("sol_image_taille_m", 2.0))
    mp.inputs["Scale"].default_value = (k, k, 1.0)
    nt.links.new(mp.outputs["Vector"], it.inputs["Vector"]); nt.links.new(it.outputs["Color"], b.inputs["Base Color"])
else:
    # Pas de photo : des lames génériques dans les deux teintes données.
    teintes = cfg.get("sol", ["#B98A5A", "#8E6238"])
    br = nt.nodes.new("ShaderNodeTexBrick"); br.inputs["Scale"].default_value = 1.2; br.inputs["Mortar Size"].default_value = 0.004
    br.inputs["Color1"].default_value = rgb(teintes[0]); br.inputs["Color2"].default_value = rgb(teintes[1])
    mp.inputs["Scale"].default_value = (1.0, 7.0, 1.0)
    nt.links.new(mp.outputs["Vector"], br.inputs["Vector"]); nt.links.new(br.outputs["Color"], b.inputs["Base Color"])

# ---------- la pièce

if CONTOUR:
    plaque("sol", 0.0, sol_m); plafond = plaque("plafond", H, plafond_m)
else:
    boite("sol", (W, D, 0.05), (0, 0, -0.025), sol_m)
    plafond = boite("plafond", (W + 2 * E, D + 2 * E, 0.05), (0, 0, H + 0.025), plafond_m)
murs = {}
for nom, m in MURS.items():
    rg, rd = m["rallonge"]
    long_ = m["longueur"] + rg + rd
    cm = m["centre"] + m["le_long"] * ((rd - rg) / 2)
    teinte_mur = cfg.get("peinture_murs", {}).get(nom)   # mur d'accent : sa propre couleur
    m_mur = matiere("peinture_" + nom, teinte_mur, 0.85) if teinte_mur else peinture
    if cfg.get("papier_peint", {}).get(nom):
        m_mur = papier_peint(nom, nom, cfg["papier_peint"][nom])
    murs[nom] = boite("mur_" + nom, taille_selon_mur(nom, long_, E, H), (cm.x, cm.y, H / 2), m_mur)
    c = m["centre"] + m["dedans"] * (E / 2 + 0.0075)
    boite("plinthe_" + nom, taille_selon_mur(nom, m["longueur"], 0.015, 0.08), (c.x, c.y, 0.04), blanc)

# ---------- portes et fenêtres

ciel = lumineuse("ciel", "#CFE3F5", 1.6)
n_fenetres = 0
for i, o in enumerate(cfg.get("ouvertures", [])):
    mur = o["mur"]; m = MURS[mur]; larg = float(o["largeur"]); haut = float(o["hauteur"])
    allege = float(o.get("allege", 0.9 if o["type"] == "fenetre" else 0.0))
    c = point_sur_mur(mur, float(o["position"]), larg); zc = allege + haut / 2
    if o["type"] == "fenetre":
        n_fenetres += 1
        # Le trou dans le mur : un volume soustrait au moment du rendu.
        trou = boite("trou_%d" % i, taille_selon_mur(mur, larg, E * 3, haut), (c.x, c.y, zc))
        trou.hide_render = True; trou.display_type = "WIRE"
        mod = murs[mur].modifiers.new("fenetre_%d" % i, "BOOLEAN"); mod.operation = "DIFFERENCE"; mod.object = trou
        # Le cadre de la fenêtre.
        t = 0.05
        for dz, taille in ((haut / 2, (larg + 2 * t, 0.06, t)), (-haut / 2, (larg + 2 * t, 0.06, t))):
            boite("cadre_%d" % i, taille_selon_mur(mur, *taille), (c.x, c.y, zc + dz), blanc)
        for cote in (-1, 1):
            p = c + m["le_long"] * (cote * larg / 2)
            boite("cadre_%d" % i, taille_selon_mur(mur, t, 0.06, haut), (p.x, p.y, zc), blanc)
        boite("traverse_%d" % i, taille_selon_mur(mur, 0.035, 0.04, haut), (c.x, c.y, zc), blanc)
        # Dehors : un fond clair et une lumière du jour qui entre par la fenêtre.
        dehors = c - m["dedans"] * 0.6
        boite("dehors_%d" % i, taille_selon_mur(mur, larg * 3, 0.02, haut * 3), (dehors.x, dehors.y, zc), ciel)
        jour = bpy.data.lights.new("jour_%d" % i, "AREA"); jour.shape = "RECTANGLE"
        jour.size = larg; jour.size_y = haut; jour.energy = float(cfg.get("lumiere_du_jour", 150)); jour.color = (1.0, 0.97, 0.92)
        lj = bpy.data.objects.new("jour_%d" % i, jour); pj = c - m["dedans"] * 0.25
        lj.location = (pj.x, pj.y, zc)
        lj.rotation_euler = (Vector((0, 0, -1)).rotation_difference(m["dedans"])).to_euler()
        sc.collection.objects.link(lj)
    else:
        # Une porte : un panneau posé contre le mur, avec son cadre et sa poignée.
        p = c + m["dedans"] * (E / 2 + 0.02)
        boite("porte_%d" % i, taille_selon_mur(mur, larg, 0.04, haut), (p.x, p.y, haut / 2), matiere("porte_%d" % i, o.get("couleur", "#EFEAE0"), 0.4))
        t = 0.06; pc = c + m["dedans"] * (E / 2 + 0.01)
        boite("cadre_porte_%d" % i, taille_selon_mur(mur, larg + 2 * t, 0.03, t), (pc.x, pc.y, haut + t / 2), blanc)
        for cote in (-1, 1):
            q = pc + m["le_long"] * (cote * (larg / 2 + t / 2))
            boite("cadre_porte_%d" % i, taille_selon_mur(mur, t, 0.03, haut), (q.x, q.y, haut / 2), blanc)
        q = p + m["le_long"] * (larg / 2 - 0.09) + m["dedans"] * 0.04
        boite("poignee_%d" % i, taille_selon_mur(mur, 0.12, 0.03, 0.025), (q.x, q.y, 1.0), matiere("poignee_%d" % i, "#3A3A3A", 0.3))

# ---------- meubles

def boite_englobante(objs):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))

ANGLE = {"fond": 0.0, "avant": math.pi, "gauche": math.pi / 2, "droit": -math.pi / 2}
def angle_du_mur(mur):
    return ANGLE[mur] if mur in ANGLE else math.atan2(MURS[mur]["dedans"].x, -MURS[mur]["dedans"].y)
meubles_poses = []
emprises = []   # empreinte au sol de chaque meuble (x0, y0, x1, y1) : la caméra s'en écarte
for i, f in enumerate(cfg.get("meubles", [])):
    if "modele" in f:
        # Un objet 3D (fichier GLB, par exemple produit par TRELLIS) : on le met à l'échelle,
        # on le tourne face à la pièce et on le pose contre son mur.
        avant_import = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=chemin(f["modele"]))
        nouveaux = [o for o in bpy.data.objects if o not in avant_import]
        pivot = bpy.data.objects.new("meuble_%d" % i, None); sc.collection.objects.link(pivot)
        for o in nouveaux:
            if o.parent is None: o.parent = pivot
        mur = f.get("mur", "fond"); m = MURS[mur]
        pivot.rotation_euler = (0, 0, angle_du_mur(mur) + math.radians(float(f.get("rotation", 0))))
        lo, hi = boite_englobante(nouveaux)
        etendue = abs((hi - lo).dot(m["le_long"]))
        if f.get("largeur_m") and etendue > 0:
            s = float(f["largeur_m"]) / etendue; pivot.scale = (s, s, s)
            lo, hi = boite_englobante(nouveaux)
        larg = abs((hi - lo).dot(m["le_long"])); prof = abs((hi - lo).dot(m["dedans"]))
        cible = point_sur_mur(mur, float(f.get("position", (m["longueur"] - larg) / 2)), larg) + m["dedans"] * (E / 2 + 0.02 + prof / 2)
        centre = (lo + hi) / 2
        # "hauteur_pose_m" : pour un élément accroché au mur (étagère murale), sinon posé au sol.
        pivot.location = Vector((cible.x - centre.x, cible.y - centre.y, -lo.z + float(f.get("hauteur_pose_m", 0)))) + pivot.location
        lo, hi = boite_englobante(nouveaux)
        emprises.append((lo.x, lo.y, hi.x, hi.y, hi.z))
        meubles_poses.append({"nom": f.get("nom", f["modele"]), "largeur_m": round(larg, 3), "profondeur_m": round(prof, 3), "hauteur_m": round(hi.z - lo.z, 3)})
    elif "mur" in f:
        # Pas de modèle, mais un mur : un volume simple (largeur, profondeur, hauteur) posé contre ce mur.
        mur = f["mur"]; m = MURS[mur]; larg, prof, haut = [float(v) for v in f["taille"]]
        c = point_sur_mur(mur, float(f.get("position", (m["longueur"] - larg) / 2)), larg) + m["dedans"] * (E / 2 + 0.02 + prof / 2)
        boite(f.get("nom", "meuble_%d" % i), taille_selon_mur(mur, larg, prof, haut), (c.x, c.y, haut / 2 + float(f.get("hauteur_pose_m", 0))),
              matiere("m_%d" % i, f.get("couleur", "#D8CBB5"), 0.6))
        tx, ty, _ = taille_selon_mur(mur, larg, prof, haut)
        emprises.append((c.x - tx / 2, c.y - ty / 2, c.x + tx / 2, c.y + ty / 2, haut + float(f.get("hauteur_pose_m", 0))))
        meubles_poses.append({"nom": f.get("nom", "meuble_%d" % i), "largeur_m": larg, "profondeur_m": prof, "hauteur_m": haut, "volume_simple": True})
    else:
        # Pas de modèle ni de mur : un volume simple placé par ses coordonnées.
        sx, sy, sz = f["taille"]; z = f.get("z", 0.0)
        px, py = (f["pos"][0] - _cx, f["pos"][1] - _cy) if CONTOUR else f["pos"]   # avec un contour, la position se lit dans le repère du plan
        boite(f.get("nom", "meuble_%d" % i), (sx, sy, sz), (px, py, z + sz / 2), matiere("m_%d" % i, f.get("couleur", "#E9E4DA"), 0.6))
        if CONTOUR:
            emprises.append((px - sx / 2, py - sy / 2, px + sx / 2, py + sy / 2, z + sz))

# ---------- lumière

pl = bpy.data.lights.new("plafonnier", "AREA"); pl.size = 1.0; pl.color = (1.0, 0.94, 0.86)
pl.energy = 35 if n_fenetres else 110
plo = bpy.data.objects.new("plafonnier", pl); plo.location = (0, 0, H - 0.08); sc.collection.objects.link(plo)
GRILLE = []   # des points répartis dans la pièce : ils servent à placer les lumières et les caméras d'une pièce non rectangulaire
if CONTOUR:
    k = 0.3
    GRILLE = [(i * k, j * k) for i in range(int(-W / 2 / k) - 1, int(W / 2 / k) + 2) for j in range(int(-D / 2 / k) - 1, int(D / 2 / k) + 2)
              if all(dans_la_piece(i * k + dx, j * k + dy) for dx in (-0.45, 0.45) for dy in (-0.45, 0.45))]
    _hors = [(i * 0.3, j * 0.3) for i in range(-30, 31) for j in range(-30, 31) if not dans_la_piece(i * 0.3, j * 0.3)]
    def au_large(p):   # distance au mur le plus proche, à 0,3 m près
        return min((math.hypot(p[0] - q[0], p[1] - q[1]) for q in _hors), default=9.0)
    c1 = max(GRILLE, key=au_large); plo.location = (c1[0], c1[1], H - 0.08)
    c2 = max(GRILLE, key=lambda p: math.hypot(p[0] - c1[0], p[1] - c1[1]))
    if math.hypot(c2[0] - c1[0], c2[1] - c1[1]) > 2.5:   # une pièce en L a deux zones : une lumière dans chacune
        pl2 = pl.copy(); o2 = bpy.data.objects.new("plafonnier_2", pl2); o2.location = (c2[0], c2[1], H - 0.08); sc.collection.objects.link(o2)
monde = bpy.data.worlds.new("monde"); sc.world = monde; monde.use_nodes = True
fond = next(n for n in monde.node_tree.nodes if n.type == "BACKGROUND")
fond.inputs["Color"].default_value = (1, 1, 1, 1); fond.inputs["Strength"].default_value = 0.1

# ---------- rendu

finale = cfg.get("qualite", "rapide") == "finale"
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.engine = "CYCLES"; sc.cycles.use_denoising = True
cam = bpy.data.cameras.new("cam"); co = bpy.data.objects.new("cam", cam); sc.collection.objects.link(co); sc.camera = co

def viser(position, cible):
    co.location = position
    co.rotation_euler = (Vector(cible) - Vector(position)).to_track_quat("-Z", "Y").to_euler()

def rendre(nom, largeur, hauteur, echantillons, jpeg=False):
    t = time.time()
    sc.render.resolution_x, sc.render.resolution_y = largeur, hauteur; sc.cycles.samples = echantillons
    sc.render.image_settings.file_format = "JPEG" if jpeg else "PNG"
    if jpeg: sc.render.image_settings.quality = 88
    f = os.path.join(sortie, nom); sc.render.filepath = f
    bpy.ops.render.render(write_still=True)
    return {"fichier": os.path.basename(f), "secondes": round(time.time() - t, 1)}

vues = cfg.get("vues", ["photo1", "photo2", "dessus", "maquette"])
res = (1600, 1000, 64) if finale else (1120, 700, 32)
fichiers = []
marge = 0.3

def degagement(x, y):
    """Distance au sol entre la caméra et le meuble le plus proche (grande s'il n'y en a pas)."""
    d = 99.0
    for x0, y0, x1, y1, z1 in emprises:
        if z1 < 1.0:   # un meuble bas (lit, table basse) ne bouche pas la vue d'une caméra à 1,50 m
            continue
        dx = max(x0 - x, 0, x - x1); dy = max(y0 - y, 0, y - y1)
        d = min(d, math.hypot(dx, dy))
    return d

# Les photos sont prises depuis un coin, vers le coin opposé. Par défaut les deux coins côté « avant » ;
# si un meuble est collé à l'un d'eux, on prend le coin le plus dégagé (sinon le meuble bouche l'image).
COINS = [(1, -1), (-1, -1), (1, 1), (-1, 1)]   # (signe x, signe y) : avant droit, avant gauche, fond droit, fond gauche
def score(c):
    return min(degagement(c[0] * (W / 2 - marge), c[1] * (D / 2 - marge)), 2.5)   # au-delà de 2,5 m, rien ne gêne
coins = sorted(COINS, key=lambda c: -score(c))   # tri stable : à égalité, l'ordre par défaut est gardé
prises = [((sx * (W / 2 - marge), sy * (D / 2 - marge)), (-sx * (W / 2 - 0.9), -sy * (D / 2 - 0.5))) for sx, sy in coins[:2]]
if CONTOUR:
    # Pièce non rectangulaire : on se place dans les angles d'où l'on voit le plus de pièce, et on vise le milieu de ce qu'on voit.
    def visible(a, b):
        return all(dans_la_piece(a[0] + (b[0] - a[0]) * t / 20, a[1] + (b[1] - a[1]) * t / 20) for t in range(1, 20))
    candidats = []
    for i in range(_n):
        if not _saillant(i):
            continue
        avant_, apres_ = MURS[noms[i - 1]]["dedans"], MURS[noms[i]]["dedans"]
        p = (CONTOUR[i][0] + (avant_.x + apres_.x) * marge, CONTOUR[i][1] + (avant_.y + apres_.y) * marge)
        vus = [g for g in GRILLE if visible(p, g)]
        if vus:
            cible = (sum(g[0] for g in vus) / len(vus), sum(g[1] for g in vus) / len(vus))
            candidats.append((len(vus) * min(degagement(*p), 2.0), p, cible))
    candidats.sort(key=lambda c: -c[0])
    prises = [(c[1], c[2]) for c in candidats[:1]]
    # La seconde photo : un autre angle, le plus éloigné possible du premier tout en voyant beaucoup de pièce.
    loin = lambda c: math.hypot(c[1][0] - prises[0][0][0], c[1][1] - prises[0][0][1])
    prises += [(c[1], c[2]) for c in sorted(candidats[1:], key=lambda c: -c[0] * loin(c)) if loin(c) > 2.0][:1]
for nom_vue, (pos, cible) in zip(["photo1", "photo2"], prises):
    if nom_vue not in vues:
        continue
    cam.type = "PERSP"; cam.lens = 15
    viser((pos[0], pos[1], 1.5), (cible[0], cible[1], 1.05))
    fichiers.append(rendre(nom_vue + ".png", *res))
if "dessus" in vues:
    # Vue de dessus, sans plafond, pour montrer le calepinage du sol.
    plafond.hide_render = True
    cam.type = "PERSP"; cam.lens = 28; co.location = (0, 0, max(W, D) * 1.55); co.rotation_euler = (0, 0, 0)
    fichiers.append(rendre("dessus.png", *res))
    plafond.hide_render = False
if "panorama" in vues:
    # Vue à 360 degrés depuis le centre : une seule image, lisible par une visionneuse de panorama.
    cam.type = "PANO"
    try: cam.panorama_type = "EQUIRECTANGULAR"
    except Exception: cam.cycles.panorama_type = "EQUIRECTANGULAR"
    p = cfg.get("panorama_depuis", list(plo.location[:2]) if CONTOUR else [0.0, -D / 4])
    co.location = (p[0], p[1], 1.55); co.rotation_euler = (math.radians(90), 0, 0)
    fichiers.append(rendre("panorama_360.jpg", *((4096, 2048, 48) if finale else (2048, 1024, 24)), jpeg=True))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(sortie, "scene.blend"))

def exporter_maquette(chemin):
    """Maquette 3D à faire tourner dans le site (fichier .glb) : la même pièce, vue en « maison de poupée ».
    Sans plafond ; les murs perdent leur face extérieure, donc on voit l'intérieur depuis n'importe quel côté ;
    le sol calculé par Blender est « cuit » dans une image, seul format qu'un fichier 3D sait transporter."""
    from mathutils import Vector
    import bmesh
    dg = bpy.context.evaluated_depsgraph_get()
    garder = []
    for o in list(sc.objects):
        if o.type != "MESH" or not o.visible_get() or o.name.startswith(("plafond", "dehors", "trou")):
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))  # trous des portes et fenêtres appliqués
        n = bpy.data.objects.new(o.name + "_maquette", me); n.matrix_world = o.matrix_world.copy()
        sc.collection.objects.link(n); garder.append(n)
    for o in garder:
        if not o.name.startswith("mur_"):
            continue
        bm = bmesh.new(); bm.from_mesh(o.data)
        mw = o.matrix_world; rot = mw.to_3x3()
        dehors = []
        for f in bm.faces:
            nrm = (rot @ f.normal).normalized(); c = mw @ f.calc_center_median()
            v = Vector((c.x, c.y, 0))  # la pièce est centrée sur l'origine
            if CONTOUR:   # pièce non rectangulaire : la face extérieure est celle qui tourne le dos à l'intérieur de son mur
                if abs(nrm.z) < 0.5 and nrm.dot(MURS[o.name[len("mur_"):-len("_maquette")]]["dedans"]) < -0.5:
                    dehors.append(f)
            elif v.length > 1e-6 and abs(nrm.z) < 0.5 and nrm.dot(v.normalized()) > 0.5:
                dehors.append(f)
        bmesh.ops.delete(bm, geom=dehors, context="FACES"); bm.to_mesh(o.data); bm.free()
    for m in bpy.data.materials:
        m.use_backface_culling = True
    sols = [o for o in garder if o.name.startswith("sol")]
    if sols:
        s = sols[0]
        bpy.ops.object.select_all(action="DESELECT"); s.select_set(True); bpy.context.view_layer.objects.active = s
        bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.cube_project(cube_size=max(W, D)); bpy.ops.object.mode_set(mode="OBJECT")
        for slot in s.material_slots:
            m = slot.material
            if not (m and m.use_nodes):
                continue
            nt = m.node_tree
            img = bpy.data.images.new("sol_cuit", 2048, 2048)
            noeud = nt.nodes.new("ShaderNodeTexImage"); noeud.image = img; nt.nodes.active = noeud
            sc.cycles.samples = 4
            bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=4)
            b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if b:
                for l in list(b.inputs["Base Color"].links):
                    nt.links.remove(l)
                nt.links.new(noeud.outputs["Color"], b.inputs["Base Color"])
            img.pack()
    bpy.ops.object.select_all(action="DESELECT")
    for o in garder:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=chemin, export_format="GLB", use_selection=True, export_apply=True,
                              export_cameras=False, export_lights=False, export_image_format="JPEG")

if "maquette" in vues:
    t = time.time()
    try:
        exporter_maquette(os.path.join(sortie, "maquette.glb"))
        fichiers.append({"fichier": "maquette.glb", "secondes": round(time.time() - t, 1)})
    except Exception as e:  # la maquette est un bonus : son échec ne bloque pas les images
        print(f"MAQUETTE ECHEC {type(e).__name__}: {e}")

print("RESULTAT " + json.dumps({"images": fichiers, "meubles": meubles_poses, "total_secondes": round(time.time() - t0, 1)}, ensure_ascii=False))
