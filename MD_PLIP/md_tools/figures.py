from plip.visualization.visualize import PyMOLVisualizer
from plip.basic.remote import VisualizerData
from plip.basic.supplemental import start_pymol
from .utils import set_to_neutral_pH
from pymol import cmd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import cairo
from rdkit import Chem
from rdkit.Chem import AllChem
from openbabel import pybel
import tempfile
import os


def save_pymol(my_mol, my_id, outdir):
    complex = VisualizerData(my_mol, my_id)
    vis = PyMOLVisualizer(complex)
    lig_members = complex.lig_members
    chain = complex.chain

    ligname = vis.ligname
    hetid = complex.hetid

    metal_ids = complex.metal_ids
    metal_ids_str = '+'.join([str(i) for i in metal_ids])

    start_pymol(run=True, options='-pcq', quiet=True)
    vis.set_initial_representations()

    cmd.load(complex.sourcefile)

    current_name = cmd.get_object_list(selection='(all)')[0]

    current_name = cmd.get_object_list(selection='(all)')[0]
    cmd.set_name(current_name, complex.pdbid)

    cmd.hide('everything', 'all')
    cmd.select(ligname, 'resn %s and chain %s and resi %s*' % (hetid, chain, complex.position))


    # Visualize and color metal ions if there are any
    if not len(metal_ids) == 0:
        vis.select_by_ids(ligname, metal_ids, selection_exists=True)
        cmd.show('spheres', 'id %s and %s' % (metal_ids_str))

    # Additionally, select all members of composite ligands
    if len(lig_members) > 1:
        for member in lig_members:
            resid, chain, resnr = member[0], member[1], str(member[2])
            cmd.select(ligname, '%s or (resn %s and chain %s and resi %s)' % (ligname, resid, chain, resnr))

    cmd.show('sticks', ligname)
    cmd.color('myblue')
    cmd.color('myorange', ligname)
    cmd.util.cnc('all')
    if not len(metal_ids) == 0:
        cmd.color('hotpink', 'id %s' % metal_ids_str)
        cmd.hide('sticks', 'id %s' % metal_ids_str)
        cmd.set('sphere_scale', 0.3, ligname)
    cmd.deselect()

    vis.make_initial_selections()

    vis.show_hydrophobic()  # Hydrophobic Contacts
    vis.show_hbonds()  # Hydrogen Bonds
    vis.show_halogen()  # Halogen Bonds
    vis.show_stacking()  # pi-Stacking Interactions
    vis.show_cationpi()  # pi-Cation Interactions
    vis.show_sbridges()  # Salt Bridges
    vis.show_wbridges()  # Water Bridges
    vis.show_metal()  # Metal Coordination
    vis.refinements()
    vis.zoom_to_ligand()
    vis.selections_cleanup()
    vis.selections_group()
    vis.additional_cleanup()
    vis.save_session(outdir)


def plot_HPI(hp_dists, dirname, plot_thresh, save_files=True):

    presence = pd.DataFrame((hp_dists < 0.4).sum(axis=0)/len(hp_dists), index = hp_dists.columns, columns=["Presence"]).sort_values("Presence", ascending=False)
    presence = presence.iloc[np.where(presence.Presence > plot_thresh)[0]]
    hp_dists=hp_dists[presence.index]

    for j in range(int(np.ceil(len(hp_dists.T)/8))):
        batch_len = len(hp_dists.T.iloc[j*8:j*8+8])
        width = batch_len*14/4 if batch_len <= 4 else 14
        height = int(np.ceil(batch_len/4)*6)
        nrows = int(np.ceil(batch_len/4)*3)
        ncols = batch_len if batch_len <=4 else 4

        fig = plt.figure(figsize=(width,height), layout="constrained")
        for i in range(len(hp_dists.T.iloc[j*8:j*8+8])):
            row = hp_dists.T.iloc[i+j*8]
            ax = fig.add_subplot(nrows,ncols,int((i%4+1)+12*np.floor(i/4)))
            ax.scatter(row.index, (row*10),color="black",marker="x")
            ax.axhline(np.mean(row*10), 0, 1, color="red")
            ax.set_title(row.name)
            ax.set_ylabel("Distance (Å)")

            ax = fig.add_subplot(nrows,ncols,int((i%4+ncols*1+1)+12*np.floor(i/4)))
            ax.hist(row*10, density=True,color="black")
            ax.set_xlabel("Distance (Å)")
            ax.set_ylabel("Density")
            ax.axvline(np.mean(row*10), 0, 1, color="red")

            ax = fig.add_subplot(nrows,ncols,int((i%4+ncols*2+1)+12*np.floor(i/4)))
            for index, condition in ((row < 0.4))[::2].items():
                if condition:
                    ax.axvline(x=index, color='black', linestyle='-', linewidth=0.5, alpha=0.7)
            ax.text(0.95,0.1,"{:.2f}%".format((row < 0.4).sum()*100/len(row)),backgroundcolor="white", transform=ax.transAxes, horizontalalignment='right')
            ax.set_title("HPI Presence")
            ax.set_xlabel("Frame")
        if save_files:
            plt.savefig(dirname+"/plots/HPI_plots_{}.png".format(j))
        else:
            plt.show()

def plot_HB(hb_dists,hb_angles, dirname, plot_thresh, save_files):

    presence = pd.DataFrame(((hb_dists < 0.25) & (hb_angles > 120)).sum(axis=0)/len(hb_dists), index = hb_dists.columns, columns=["Presence"]).sort_values("Presence", ascending=False)
    presence = presence.iloc[np.where(presence.Presence > plot_thresh)[0]]
    hb_dists=hb_dists[presence.index]
    hb_angles=hb_angles[presence.index]

    for j in range(int(np.ceil(len(hb_dists.T)/8))):
        batch_len = len(hb_dists.T.iloc[j*8:j*8+8])
        width = batch_len*14/4 if batch_len <= 4 else 14
        height = int(np.ceil(batch_len/4)*6)
        nrows = int(np.ceil(batch_len/4)*3)
        ncols = batch_len if batch_len <=4 else 4

        fig = plt.figure(figsize=(width,height), layout="constrained")
        for i in range(len(hb_dists.T.iloc[j*8:j*8+8])):
            row = hb_dists.T.iloc[i+j*8]
            row_ang = hb_angles.T.iloc[i+j*8]
            ax = fig.add_subplot(nrows,ncols,int((i%4+1)+12*np.floor(i/4)))
            ax.scatter(row.index, (row*10),color="black",marker="x")
            ax.axhline(np.mean(row*10), 0, 1, color="red")
            ax.set_title(row.name)
            ax.set_ylabel("Distance (Å)")

            ax = fig.add_subplot(nrows,ncols,int((i%4+ncols*1+1)+12*np.floor(i/4)))
            ax.scatter(row.index, row_ang, color="black", marker="x")
            ax.set_ylabel("Angle")
            ax.axhline(np.mean(row_ang), 0, 1, color="red")

            ax = fig.add_subplot(nrows,ncols,int((i%4+ncols*2+1)+12*np.floor(i/4)))
            for index, condition in ((row < 0.25) & (row_ang > 120))[::2].items():
                if condition:
                    ax.axvline(x=index, color='black', linestyle='-', linewidth=0.5, alpha=0.7)
            ax.text(0.95,0.1,"{:.2f}%".format(((row < 0.25)*(row_ang > 120)).sum()*100/len(row)),backgroundcolor="white", transform=ax.transAxes, horizontalalignment='right')
            ax.set_title("HB Presence")
            ax.set_xlabel("Frame")
        if save_files:
            plt.savefig(dirname+"/plots/HB_plots_{}.png".format(j))
        else:
            plt.show()

def plot_PS(ps_dists, ps_offset, ps_angles, dirname, plot_thresh, save_files):

    presence = pd.DataFrame(((ps_dists < 0.55) & (ps_offset < 0.2)).sum(axis=0)/len(ps_dists), index = ps_dists.columns, columns=["Presence"]).sort_values("Presence", ascending=False)
    presence = presence.iloc[np.where(presence.Presence > plot_thresh)[0]]
    ps_dists=ps_dists[presence.index]
    ps_offset=ps_offset[presence.index]
    ps_angles=ps_angles[presence.index]

    for i in range(len(ps_dists.T)):
        distance = ps_dists.T.iloc[i]
        angles = ps_angles.T.iloc[i]
        offset = ps_offset.T.iloc[i]

        fig = plt.figure(figsize=(8,6), layout="constrained")

        ax = fig.add_subplot(2,2,1)
        ax.scatter(distance.index, distance*10, marker="x", color="black")
        ax.axhline(np.mean(distance*10),0,1, color="red")
        ax.set_title("Pi Stacking Distance")
        ax.set_ylabel("Distance (Å)")
        
        ax = fig.add_subplot(2,2,2)
        ax.set_title("Planar Angle")
        ax.scatter(distance.index, angles, marker="x", color="black")   
        ax.axhline(np.mean(angles),0,1, color="red")
        ax.set_ylabel("Angle (degrees)")
        
        ax = fig.add_subplot(2,2,3)
        ax.set_title("COM offset")
        ax.scatter(distance.index, offset*10, marker="x", color="black")
        ax.axhline(np.mean(offset*10),0,1, color="red")
        ax.set_ylabel("Distance (Å)")
        
        ax = fig.add_subplot(2,2,4)
        ax.set_title("Pi Stacking Present")
        for index, condition in ((distance < 0.55)*(angles < 45)*(offset < 0.2))[::2].items():
            if index == 0:
                ax.axvline(0,0,0, color='red', linestyle='-', linewidth=0.5, alpha=0.7, label="parallel")
            if condition:
                ax.axvline(x=index, color='red', linestyle='-', linewidth=0.5, alpha=0.7)

        for index, condition in ((distance < 0.55)*(angles >= 45)*(offset < 0.2))[::2].items():
            if index == 0:
                ax.axvline(0,0,0, color='blue', linestyle='-', linewidth=0.5, alpha=0.7, label="t-shaped")
            if condition:
                ax.axvline(x=index, color='blue', linestyle='-', linewidth=0.5, alpha=0.7)

        ax.legend(loc="upper right")
        ax.text(0.95,0.1,"Total Pi stacking: {:.2f}%".format(((distance < 0.55)*(offset < 0.2)).sum()*100/len(distance)),backgroundcolor="white", transform=ax.transAxes, horizontalalignment='right')
        fig.suptitle(ps_dists.columns[i], fontsize=15)
        if save_files:
            plt.savefig(dirname+"/plots/PS_plot_{}.png".format(i))
        else:
            plt.show()

def plot_PC(pc_dists, dirname, plot_thresh, save_files):

    presence = pd.DataFrame((pc_dists < 0.6).sum(axis=0)/len(pc_dists), index = pc_dists.columns, columns=["Presence"]).sort_values("Presence", ascending=False)
    presence = presence.iloc[np.where(presence.Presence > plot_thresh)[0]]
    pc_dists=pc_dists[presence.index]

    for j in range(int(np.ceil(len(pc_dists.T)/8))):
        batch_len = len(pc_dists.T.iloc[j*8:j*8+8])
        width = batch_len*14/4 if batch_len <= 4 else 14
        height = int(np.ceil(batch_len/4)*6)
        nrows = int(np.ceil(batch_len/4)*3)
        ncols = batch_len if batch_len <=4 else 4

        fig = plt.figure(figsize=(width,height), layout="constrained")
        for i in range(len(pc_dists.T.iloc[j*8:j*8+8])):
            row = pc_dists.T.iloc[i+j*8]
            ax = fig.add_subplot(nrows,ncols,int((i%4+1)+12*np.floor(i/4)))
            ax.scatter(row.index, (row*10),color="black",marker="x")
            ax.axhline(np.mean(row*10), 0, 1, color="red")
            ax.set_title(row.name)
            ax.set_ylabel("Distance (Å)")

            ax = fig.add_subplot(nrows,ncols,int((i%4+ncols*1+1)+12*np.floor(i/4)))
            ax.hist(row*10, density=True,color="black")
            ax.set_xlabel("Distance (Å)")
            ax.set_ylabel("Density")
            ax.axvline(np.mean(row*10), 0, 1, color="red")

            ax = fig.add_subplot(nrows,ncols,int((i%4+ncols*2+1)+12*np.floor(i/4)))
            for index, condition in ((row < 0.6))[::2].items():
                if condition:
                    ax.axvline(x=index, color='black', linestyle='-', linewidth=0.2, alpha=0.7)
            ax.text(0.95,0.1,"{:.2f}%".format((row < 0.6).sum()*100/len(row)),backgroundcolor="white", transform=ax.transAxes, horizontalalignment='right')
            ax.set_title("PC Presence")
            ax.set_xlabel("Frame")
        if save_files:
            plt.savefig(dirname+"/plots/PC_plots_{}.png".format(j))
        else:
            plt.show()

def plot_SB(sb_dists, dirname, plot_thresh, save_files):

    presence = pd.DataFrame((sb_dists < 0.55).sum(axis=0)/len(sb_dists), index = sb_dists.columns, columns=["Presence"]).sort_values("Presence", ascending=False)
    presence = presence.iloc[np.where(presence.Presence > plot_thresh)[0]]
    sb_dists=sb_dists[presence.index]
    
    for j in range(int(np.ceil(len(sb_dists.T)/8))):
        batch_len = len(sb_dists.T.iloc[j*8:j*8+8])
        width = batch_len*14/4 if batch_len <= 4 else 14
        height = int(np.ceil(batch_len/4)*6)
        nrows = int(np.ceil(batch_len/4)*3)
        ncols = batch_len if batch_len <=4 else 4

        fig = plt.figure(figsize=(width,height), layout="constrained")
        for i in range(len(sb_dists.T.iloc[j*8:j*8+8])):
            row = sb_dists.T.iloc[i+j*8]
            ax = fig.add_subplot(nrows,ncols,int((i%4+1)+12*np.floor(i/4)))
            ax.scatter(row.index, (row*10),color="black",marker="x")
            ax.axhline(np.mean(row*10), 0, 1, color="red")
            ax.set_title(row.name)
            ax.set_ylabel("Distance (Å)")

            ax = fig.add_subplot(nrows,ncols,int((i%4+ncols*1+1)+12*np.floor(i/4)))
            ax.hist(row*10, density=True,color="black")
            ax.set_xlabel("Distance (Å)")
            ax.set_ylabel("Density")
            ax.axvline(np.mean(row*10), 0, 1, color="red")

            ax = fig.add_subplot(nrows,ncols,int((i%4+ncols*2+1)+12*np.floor(i/4)))
            for index, condition in ((row < 0.55))[::2].items():
                if condition:
                    ax.axvline(x=index, color='black', linestyle='-', linewidth=0.2, alpha=0.7)
            ax.text(0.95,0.1,"{:.2f}%".format((row < 0.55).sum()*100/len(row)),backgroundcolor="white", transform=ax.transAxes, horizontalalignment='right')
            ax.set_title("SB Presence")
            ax.set_xlabel("Frame")
        if save_files:
            plt.savefig(dirname+"/plots/SB_plots_{}.png".format(j))
        else:
            plt.show()

def draw_interaction_Graph(self, plot_thresh=0, canvas_height=800, canvas_width=1000,  padding=40, save_png = False, out_name=None):

    with tempfile.TemporaryDirectory() as temp_dir:
        pdb_file_path = os.path.join(temp_dir, "lig.pdb")

        self.t.atom_slice(self.topology.select("resname {}".format(self.bsid.split(":")[0])))[0].save_pdb(pdb_file_path)

        mol = [x for x in pybel.readfile("pdb",pdb_file_path)][0]
        mol.write("pdb",pdb_file_path, overwrite=True)

        mol = Chem.MolFromPDBFile(pdb_file_path,removeHs=False)
    AllChem.EmbedMolecule(mol)
    set_to_neutral_pH(mol)

    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 1:
            bound_atom = atom.GetBonds()[0].GetBeginAtom()
            if bound_atom.GetIdx == atom.GetIdx():
                bound_atom = atom.GetBonds()[0].GetEndAtom()

            if bound_atom.GetSymbol() in ["O","N","S"]:
                atom.SetAtomicNum(100)


    mol=Chem.RemoveHs(mol)

    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 100:
            atom.SetAtomicNum(1)

    Chem.rdDepictor.Compute2DCoords(mol)

    atom_info = []
    charge_info = []
    bonds = []
    for i,atom in enumerate(mol.GetAtoms()):
        coords = mol.GetConformer().GetAtomPosition(i)
        atom_info.append((coords.x, coords.y, atom.GetSymbol(), atom.GetPDBResidueInfo().GetName().strip()))

        if atom.GetFormalCharge() < 0:
            charge_info.append((coords.x+0.5, coords.y-0.3, "–", "Charge"))
        if atom.GetFormalCharge() > 0:
            charge_info.append((coords.x+0.5, coords.y-0.3, "+", "Charge"))
            
        startatoms = [bond.GetBeginAtomIdx() for bond in atom.GetBonds()]
        endatoms = [bond.GetEndAtomIdx() for bond in atom.GetBonds()]
        bond_type = [str(bond.GetBondType()).split(".")[-1] for bond in atom.GetBonds()]

        for a,b,c in zip(startatoms,endatoms,bond_type):
            if (a,b,c) not in bonds and (b,a,c) not in bonds:
                bonds.append((a,b,c))

    coord_dict = {}
    for entry in atom_info:
        coord_dict[entry[3]] = (entry[0],entry[1])

    interactions = []
    centroids = []
    centroid_counter = 0

    for i,row in self.hydrophobic.hydrophobic_df.drop_duplicates(subset=["LIGCARBONIDX","RESTYPE","RESNR","RESCHAIN"]).iterrows():
        if row["fpresent"] < plot_thresh:
            continue
        int_atom = str(self.topology.atom(row["LIGCARBONIDX"]-1)).split("-")[-1]
        interactions.append((int_atom, row["RESTYPE"]+str(row["RESNR"])+"_"+row["RESCHAIN"], "HPI"))#, presence_df[int_name]))

    for i,row in self.hbond.hbond_df.iterrows():
        if row["fpresent"] < plot_thresh:
            continue
        if row["protisdon"]:
            int_atom = str(self.topology.atom(row["a_orig_idx"]-1)).split("-")[-1]
        else:
            int_atom = str(self.topology.atom(row["d_orig_idx"]-1)).split("-")[-1]
        if (int_atom, row["restype"]+str(row["resnr"])+"_"+row["reschain"],"HB") not in interactions:
            interactions.append((int_atom, row["restype"]+str(row["resnr"])+"_"+row["reschain"],"HB"))

    for df, int_type in zip([self.pi_stacking.pi_stacking_df,self.pi_cation.pi_cation_df,self.saltbridge.saltbridge_df],
                                    ["PS","PC","SB"]):
        for i,row in df.drop_duplicates(subset=["LIG_IDX_LIST","RESTYPE","RESNR","RESCHAIN"]).iterrows():
            if row["fpresent"] < plot_thresh:
                continue
            com = np.stack([coord_dict[str(self.topology.atom(x-1)).split("-")[-1]] for x in np.array(row["LIG_IDX_LIST"].split(","), dtype=int)]).mean(axis=0)
            if (com[0],com[1],"centroid","centroid_{}".format(i)) not in centroids:
                centroids.append((com[0],com[1],"centroid","centroid_{}".format(centroid_counter)))
                coord_dict["centroid_{}".format(centroid_counter)] = (com[0],com[1])
                centroid_counter += 1
                interactions.append(("centroid_{}".format(centroid_counter-1), row["RESTYPE"]+str(row["RESNR"])+"_"+row["RESCHAIN"],int_type))
            else:
                centroid_index = centroids.index((com[0],com[1],"centroid","centroid_{}".format(i)))
                interactions.append(("centroid_{}".format(centroid_index), row["RESTYPE"]+str(row["RESNR"])+"_"+row["RESCHAIN"],int_type))

    used_res = np.unique(np.array([x[1] for x in interactions]))

    max_x = max([coord_dict[x][0] for x in coord_dict.keys()])
    min_x = min([coord_dict[x][0] for x in coord_dict.keys()])
    max_y = max([coord_dict[x][1] for x in coord_dict.keys()])
    min_y = min([coord_dict[x][1] for x in coord_dict.keys()])
    x_center = np.mean([coord_dict[x][0] for x in coord_dict.keys()])
    y_center = np.mean([coord_dict[x][1] for x in coord_dict.keys()])

    res_info = []
    for res in used_res:
        res_ints = [x[0] for x in interactions if x[1] == res]
        com = np.array([coord_dict[x] for x in res_ints]).mean(axis=0)-np.array([x_center, y_center])
        _com = com
        min_dist = np.min(np.sqrt(((np.array([np.array(coord_dict[key]) for key in coord_dict.keys()])-com)**2).sum(axis=1)))
        while min_dist < 3.5:
            com = com + (0.05*_com)
            min_dist = np.min(np.sqrt(((np.array([np.array(coord_dict[key]) for key in coord_dict.keys()])-com)**2).sum(axis=1)))
        res_info.append((com[0],com[1],"residue",res))

        
    # Sort the label coordinates by y-value
    res_info = sorted(res_info, key=lambda x: x[1])

    # Ensure minimum spacing of 2.5 units between labels
    min_spacing = 2.0

    for i in range(len(res_info)):
        current_x, current_y, label_type, label_name = res_info[i]
        
        # Check spacing between current label and the previous ones
        for j in range(len(res_info)):
            prev_x, prev_y, prev_type, prev_label = res_info[j]
            if abs(current_y - prev_y) < min_spacing and abs(current_x - prev_x) < 5 and j != i:
                if current_y > prev_y:
                    current_y = prev_y + min_spacing
                    res_info[i] = (current_x, current_y, label_type, label_name)
                else:
                    prev_y = current_y+min_spacing
                    res_info[j] = (prev_x, prev_y, prev_type, prev_label)

        # Update the y-value
        res_info[i] = (current_x, current_y, label_type, label_name)

    atom_info = atom_info + centroids
    lines = []
    for i in range(len(res_info)):
        res = res_info[i][3]
        for j in range(len(interactions)):
            if interactions[j][1] == res:
                atom = interactions[j][0]
                atom_index = [x[3] for x in atom_info].index(atom)
                lines.append((i+len(atom_info), atom_index, interactions[j][2]))

    atom_info = atom_info + res_info + charge_info

    connections = bonds + lines

    # Define padding
    padding = 40

    color_dict = {"O":(1, 0, 0),
                    "N":(0,0,1.0),
                    "S":(0.9,0.775,0.25),
                    "P":(1.0,0.5,0),
                    "B":(1.0,0.71,0.71)}

    # Set canvas size including padding
    # canvas_width, canvas_height = canvas_height + 2 * padding, 800 + 2 * padding
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, canvas_width, canvas_height)
    ctx = cairo.Context(surface)

    # Set background color
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()

    # Set line width
    ctx.set_line_width(4)

    # Draw a simple graph with labels and bond types
    data_points = atom_info
    # connections = bonds  # Format: (start_index, end_index, bond_type)

    # Calculate scaling factors to fit within the canvas
    min_x, min_y = min(point[0] for point in data_points), min(point[1] for point in data_points)
    max_x, max_y = max(point[0] for point in data_points), max(point[1] for point in data_points)

    x_scale = y_scale = min((canvas_width - 2 * padding) / (max_x - min_x), (canvas_height - 2 * padding) / (max_y - min_y))

    # Draw connections with different line styles based on bond type
    for start, end, bond_type in connections:
        start_x, start_y, _, _ = data_points[start]
        end_x, end_y, _, _ = data_points[end]
        jitter = np.random.uniform(-10,10)

        # Apply scaling and padding to coordinates
        start_x = (start_x - min_x) * x_scale + padding
        start_y = (start_y - min_y) * y_scale + padding
        end_x = (end_x - min_x) * x_scale + padding
        end_y = (end_y - min_y) * y_scale + padding

        # Set line style based on bond type
        if bond_type == "SINGLE":
            ctx.set_source_rgb(0, 0, 0)  # Black color
            ctx.set_line_width(2)  # Adjust line width for double bond
            ctx.move_to(start_x, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_line_width(0)

        elif bond_type == "DOUBLE":
            ctx.set_source_rgb(0,0,0)  # White color
            ctx.set_line_width(6)  # Adjust line width for double bond
            ctx.move_to(start_x, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_source_rgb(1,1,1)  # Black color
            ctx.set_line_width(2)  # Reset line width
            ctx.move_to(start_x, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_line_width(0)

        elif bond_type == "AROMATIC":
            ctx.set_source_rgb(0,0,0)  # White color
            ctx.set_line_width(6)  # Adjust line width for aromatic bond
            ctx.set_dash([10, 5], 0)  # Set dash pattern for aromatic bond
            ctx.move_to(start_x, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_source_rgb(1,1,1)  # Black color
            ctx.set_dash([], 0)  # Reset dash pattern
            ctx.set_line_width(2)  # Reset line width
            ctx.move_to(start_x, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_line_width(0)

        elif bond_type == "TRIPLE":
            ctx.set_source_rgb(0,0,0)  # White color
            ctx.set_line_width(10)  # Adjust line width for double bond
            ctx.move_to(start_x, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_source_rgb(1,1,1)  # Black color
            ctx.set_line_width(6)  # Reset line width
            ctx.move_to(start_x, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_source_rgb(0,0,0)  # Black color
            ctx.set_line_width(2)  # Reset line width
            ctx.move_to(start_x, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_line_width(0)
        
        elif bond_type == "HPI":
            ctx.set_source_rgba(0.5,0.5,0.5, 0.5)  # Grey color
            ctx.set_line_width(2) 
            ctx.set_dash([10, 5], 0)  # Set dash pattern for aromatic bond
            ctx.move_to(start_x+jitter, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_line_width(0)
        elif bond_type == "HB":
            ctx.set_source_rgba(0, 0, 1, 0.5)  # Blue color
            ctx.set_line_width(2) 
            ctx.set_dash([10, 5], 0)  # Set dash pattern for aromatic bond
            ctx.move_to(start_x+jitter, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_line_width(0)
        elif bond_type == "PS":
            ctx.set_source_rgba(0, 0.6, 0, 0.5)  # Black color
            ctx.set_line_width(2) 
            ctx.set_dash([10, 5], 0)  # Set dash pattern for aromatic bond
            ctx.move_to(start_x+jitter, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_line_width(0)
        elif bond_type == "PC":
            ctx.set_source_rgba(1, 0.7, 0, 0.5)  # Black color
            ctx.set_line_width(2) 
            ctx.set_dash([10, 5], 0)  # Set dash pattern for aromatic bond
            ctx.move_to(start_x+jitter, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_line_width(0)
        elif bond_type == "SB":
            ctx.set_source_rgba(1, 0, 1, 0.5)  # Black color
            ctx.set_line_width(2) 
            ctx.set_dash([10, 5], 0)  # Set dash pattern for aromatic bond
            ctx.move_to(start_x+jitter, start_y)
            ctx.line_to(end_x, end_y)
            ctx.stroke()
            ctx.set_line_width(0)



    # Draw filled circles and labels with padding
    for x, y, label, res in data_points:
        if label in ["C", "centroid"]:
            continue

        # Draw a filled white circle at each data point
        ctx.set_source_rgb(1, 1, 1)  # White color
        ctx.arc((x - min_x) * x_scale + padding, (y - min_y) * y_scale + padding, 7, 0, 2 * 3.14)
        ctx.fill_preserve()  # Preserve the path for stroking
        ctx.stroke()
            
        # Set text alignment to center
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(12)

        # Calculate text width and height
        text_extents = ctx.text_extents(res if label == "residue" else label)
        text_width = text_extents[2]
        text_height = text_extents[3]

        # Position text at the center of the point with padding
        text_x = (x - min_x) * x_scale + padding - text_width / 2
        text_y = (y - min_y) * y_scale + padding + text_height / 2
        ctx.move_to(text_x, text_y)

        if label == "residue":
            # Draw a white rectangle behind the text for label "residue"
            ctx.rectangle(text_x - 2, text_y - text_height, text_width + 4, text_height + 2)
            ctx.set_source_rgba(1,1,1,1)  # White color
            ctx.fill()
        
        if label in ["O","N","S","P","B"]:
            color = color_dict[label]
            ctx.set_source_rgba(color[0],color[1],color[2],1)

        else:
            ctx.set_source_rgba(0, 0, 0, 1)
        ctx.move_to(text_x, text_y)
        ctx.text_path(res if label == "residue" else label)
        ctx.fill()

    legend_x, legend_y = padding, canvas_height - padding

    # Define legend items
    legend_items = [
        ("Hydrophobic", (0.5,0.5,0.5)),
        ("H-bond", (0, 0, 1)),
        ("Pi-Stacking", (0,0.6,0)),
        ("Pi-cation", (1,0.7,0)),
        ("Salt-bridge", (1,0,1)),
    ]

    # Calculate legend size
    legend_width = 150
    legend_height = len(legend_items) * 20

    # Draw legend rectangle
    ctx.set_source_rgb(0,0,0)  # Black color
    ctx.set_line_width(2)
    ctx.set_dash([], 0)  # Set dash pattern for aromatic bond

    ctx.rectangle(legend_x-5, legend_y - legend_height + 10, legend_width, legend_height)
    ctx.stroke_preserve()
    ctx.set_source_rgb(1,1,1)
    ctx.fill()

    # Draw legend items
    for label, color in legend_items:
        ctx.set_line_width(2)
        ctx.set_source_rgba(color[0], color[1], color[2],0.8)  # Black color
        ctx.set_dash([10, 5], 0)  # Set dash pattern for aromatic bond


        # Draw legend line
        ctx.move_to(legend_x, legend_y)
        ctx.line_to(legend_x + 30, legend_y)
        ctx.stroke()

        # Draw legend label
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(legend_x + 40, legend_y + 5)
        ctx.show_text(label)

        # Move down for the next legend item
        legend_y -= 20

    # Save the image to a file
    if save_png:
        surface.write_to_png(out_name)

    try:
        from IPython.display import display, Image
        import io
        image_stream = io.BytesIO()
        surface.write_to_png(image_stream)
        display(Image(data=image_stream.getvalue(), format="png"))
    except:
        None